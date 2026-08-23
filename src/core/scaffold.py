"""
ScaffoldGenerator — generates complete project scaffolds from templates.

Takes a Project specification and produces a complete file tree with:
- Package.json / pyproject.toml / Cargo.toml
- Configuration files (tsconfig, eslint, prettier, etc.)
- Source folder structure
- Docker files
- CI/CD pipelines
- Documentation
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .templates.engine import (
    TemplateEngine,
    StackTemplateLoader,
    build_project_context,
    get_stack_loader,
)


# ════════════════════════════════════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class GeneratedFile:
    """Represents a generated file."""
    path: str
    content: str
    is_binary: bool = False
    executable: bool = False


@dataclass
class ScaffoldResult:
    """Result of a scaffold generation."""
    project_name: str
    tech_stack: str
    target_dir: str
    files: List[GeneratedFile] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_size(self) -> int:
        return sum(len(f.content.encode("utf-8")) for f in self.files if not f.is_binary)

    def get_tree(self) -> str:
        """Get a tree representation of generated files."""
        paths = sorted(f.path for f in self.files)
        return "\n".join(paths)


# ════════════════════════════════════════════════════════════════════════════
# Scaffold Generator
# ════════════════════════════════════════════════════════════════════════════

class ScaffoldGenerator:
    """
    Generates project scaffolds from templates.

    Usage:
        generator = ScaffoldGenerator()
        result = generator.generate(
            project_name="my-app",
            tech_stack="nextjs-tailwind",
            target_dir="/path/to/output",
            project_description="A todo app",
        )
    """

    # Stack key -> template directory mapping
    STACK_TEMPLATE_DIRS = {
        "nextjs-tailwind": "nextjs-tailwind",
        "nextjs-shadcn": "nextjs-shadcn",
        "vite-react-tailwind": "vite-react-tailwind",
        "expo-react-native": "expo-react-native",
        "fastapi-react": "fastapi-react",
        "django-react": "django-react",
        "sveltekit-tailwind": "sveltekit-tailwind",
        "nuxt-tailwind": "nuxt-tailwind",
        "remix-tailwind": "remix-tailwind",
    }

    # Files to always generate (common across stacks)
    BASE_TEMPLATES = [
        "base/git/.gitignore.j2",
        "base/docker/Dockerfile.j2",
        "base/docker/docker-compose.yml.j2",
        "base/docker/.dockerignore.j2",
        "base/vscode/settings.json.j2",
        "base/vscode/extensions.json.j2",
        "base/vscode/launch.json.j2",
        "base/config/.editorconfig.j2",
        "base/config/.prettierrc.j2",
        "base/config/.eslintrc.cjs.j2",
        "base/docs/README.md.j2",
        "base/docs/CONTRIBUTING.md.j2",
    ]

    def __init__(self, template_root: Optional[str] = None):
        self._engine = TemplateEngine(template_root)

    def _get_stack_config(self, tech_stack: str) -> Dict[str, Any]:
        """Get the default configuration for a tech stack."""
        configs = {
            "nextjs-tailwind": {
                "frontend": "nextjs",
                "styling": "tailwind",
                "backend": "nextjs-api",
                "database": "postgresql",
                "auth": "nextauth",
                "deployment": "vercel",
            },
            "nextjs-shadcn": {
                "frontend": "nextjs",
                "styling": "tailwind",
                "backend": "nextjs-api",
                "database": "postgresql",
                "auth": "nextauth",
                "deployment": "vercel",
            },
            "vite-react-tailwind": {
                "frontend": "vite-react",
                "styling": "tailwind",
                "backend": "fastapi",
                "database": "postgresql",
                "auth": "jwt",
                "deployment": "netlify",
            },
            "expo-react-native": {
                "frontend": "expo",
                "styling": "nativewind",
                "backend": "fastapi",
                "database": "postgresql",
                "auth": "jwt",
                "deployment": "eas",
            },
            "fastapi-react": {
                "frontend": "vite-react",
                "styling": "tailwind",
                "backend": "fastapi",
                "database": "postgresql",
                "auth": "jwt",
                "deployment": "fly",
            },
            "django-react": {
                "frontend": "vite-react",
                "styling": "tailwind",
                "backend": "django",
                "database": "postgresql",
                "auth": "django-auth",
                "deployment": "railway",
            },
            "sveltekit-tailwind": {
                "frontend": "sveltekit",
                "styling": "tailwind",
                "backend": "sveltekit-api",
                "database": "sqlite",
                "auth": "lucia",
                "deployment": "vercel",
            },
            "nuxt-tailwind": {
                "frontend": "nuxt",
                "styling": "tailwind",
                "backend": "nuxt-server",
                "database": "postgresql",
                "auth": "nuxt-auth",
                "deployment": "vercel",
            },
            "remix-tailwind": {
                "frontend": "remix",
                "styling": "tailwind",
                "backend": "remix",
                "database": "postgresql",
                "auth": "remix-auth",
                "deployment": "fly",
            },
        }
        return configs.get(tech_stack, {})

    def generate(
        self,
        project_name: str,
        tech_stack: str,
        target_dir: str,
        *,
        project_description: str = "",
        target: str = "web",
        database: Optional[Dict[str, Any]] = None,
        auth: Optional[Dict[str, Any]] = None,
        api: Optional[Dict[str, Any]] = None,
        deployment: Optional[Dict[str, Any]] = None,
        features: Optional[List[str]] = None,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> ScaffoldResult:
        """
        Generate a complete project scaffold.

        Args:
            project_name: Name of the project (used for folder and package names)
            tech_stack: One of the supported stack keys
            target_dir: Output directory (project folder will be created inside)
            project_description: Description for README
            target: "web", "mobile", or "both"
            database: Database configuration
            auth: Authentication configuration
            api: API configuration
            deployment: Deployment configuration
            features: List of feature flags
            overwrite: Overwrite existing files
            dry_run: Don't write files, just return result

        Returns:
            ScaffoldResult with generated files
        """
        result = ScaffoldResult(
            project_name=project_name,
            tech_stack=tech_stack,
            target_dir=target_dir,
        )

        # Validate stack
        if tech_stack not in self.STACK_TEMPLATE_DIRS:
            result.errors.append(f"Unknown tech stack: {tech_stack}")
            return result

        # Build context
        stack_config = self._get_stack_config(tech_stack)
        context = build_project_context(
            project_name=project_name,
            project_description=project_description,
            tech_stack=stack_config,
            target=target,
            database=database or {},
            auth=auth or {},
            api=api or {},
            deployment=deployment or {},
            features=features or [],
        )

        # Get stack-specific loader
        stack_loader = StackTemplateLoader(self._engine, tech_stack)

        # Determine output directory
        output_dir = Path(target_dir) / context["project_name_kebab"]
        if output_dir.exists() and not overwrite:
            result.warnings.append(f"Directory {output_dir} already exists")
            if not dry_run:
                return result

        # Generate base templates
        self._render_templates(
            result, context, self.BASE_TEMPLATES, output_dir, dry_run
        )

        # Generate stack-specific templates
        stack_templates = self._get_stack_templates(tech_stack)
        self._render_templates(
            result, context, stack_templates, output_dir, dry_run, stack_loader
        )

        # Generate package.json / pyproject.toml
        self._generate_package_files(result, context, output_dir, dry_run, stack_loader)

        return result

    def _render_templates(
        self,
        result: ScaffoldResult,
        context: Dict[str, Any],
        template_names: List[str],
        output_dir: Path,
        dry_run: bool,
        loader: Optional[StackTemplateLoader] = None,
    ) -> None:
        """Render a list of templates to files."""
        for template_name in template_names:
            try:
                # Determine output path by removing .j2 extension
                rel_path = template_name
                if rel_path.endswith(".j2"):
                    rel_path = rel_path[:-3]

                # Remove "base/" prefix for base templates
                if rel_path.startswith("base/"):
                    rel_path = rel_path[5:]  # Remove "base/"

                output_path = output_dir / rel_path

                # Render template
                if loader:
                    content = loader.render_to_file(
                        template_name, context, str(output_path), make_dirs=True, dry_run=dry_run
                    )
                else:
                    content = self._engine.render(template_name, context)
                    if not dry_run:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_text(content, encoding="utf-8")

                result.files.append(GeneratedFile(
                    path=str(rel_path),
                    content=content,
                ))

            except Exception as e:
                result.errors.append(f"Failed to render {template_name}: {e}")

    def _get_stack_templates(self, tech_stack: str) -> List[str]:
        """Get the list of templates for a specific tech stack."""
        # This would ideally scan the template directory
        # For now, return common templates per stack type

        # Common templates for most stacks
        common = [
            "package.json.j2",
            "tsconfig.json.j2",
            "next.config.js.j2",
            "tailwind.config.ts.j2",
            "postcss.config.js.j2",
            "src/app/layout.tsx.j2",
            "src/app/globals.css.j2",
            "src/lib/utils.ts.j2",
            "src/components/ui/button.tsx.j2",
            ".env.example.j2",
            ".gitignore.j2",
            "README.md.j2",
        ]

        # Stack-specific additions
        if "nextjs" in tech_stack:
            common.extend([
                "src/app/api/health/route.ts.j2",
                "src/middleware.ts.j2",
            ])
        if tech_stack == "expo-react-native":
            common.extend([
                "app.json.j2",
                "babel.config.js.j2",
                "metro.config.js.j2",
            ])
        if "fastapi" in tech_stack or "django" in tech_stack:
            common.extend([
                "pyproject.toml.j2",
                "backend/main.py.j2",
                "backend/requirements.txt.j2",
            ])

        return common

    def _generate_package_files(
        self,
        result: ScaffoldResult,
        context: Dict[str, Any],
        output_dir: Path,
        dry_run: bool,
        loader: Optional[StackTemplateLoader] = None,
    ) -> None:
        """Generate package.json, pyproject.toml, or Cargo.toml as appropriate."""
        tech_stack = context.get("tech_stack", {})
        stack_key = result.tech_stack

        # Generate package.json for Node.js projects
        if tech_stack.get("frontend") in ("nextjs", "vite-react", "expo", "remix", "sveltekit", "nuxt"):
            self._render_templates(
                result, context,
                ["package.json.j2"],
                output_dir, dry_run, loader
            )

        # Generate pyproject.toml for Python backends
        if tech_stack.get("backend") in ("fastapi", "django"):
            self._render_templates(
                result, context,
                ["pyproject.toml.j2"],
                output_dir, dry_run, loader
            )

        # Generate Cargo.toml for Rust projects
        # if tech_stack.get("backend") == "axum":
        #     self._render_templates(...)


# ════════════════════════════════════════════════════════════════════════════
# Singleton
# ════════════════════════════════════════════════════════════════════════════

_GENERATOR: Optional[ScaffoldGenerator] = None


def get_scaffold_generator(template_root: Optional[str] = None) -> ScaffoldGenerator:
    """Get the global scaffold generator instance."""
    global _GENERATOR
    if _GENERATOR is None:
        _GENERATOR = ScaffoldGenerator(template_root)
    return _GENERATOR