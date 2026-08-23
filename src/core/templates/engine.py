"""
Template Engine — Jinja2-based code generation with custom filters,
helpers, and stack-specific template loading.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from jinja2 import (
    BaseLoader,
    Environment,
    FileSystemLoader,
    Template,
    TemplateNotFound,
    select_autoescape,
)


# ════════════════════════════════════════════════════════════════════════════
# Custom Filters
# ════════════════════════════════════════════════════════════════════════════

def to_pascal_case(value: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    parts = value.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts if p)


def to_camel_case(value: str) -> str:
    """Convert snake_case or kebab-case to camelCase."""
    pascal = to_pascal_case(value)
    return pascal[0].lower() + pascal[1:] if pascal else ""


def to_kebab_case(value: str) -> str:
    """Convert snake_case or PascalCase to kebab-case."""
    # Handle PascalCase
    result = ""
    for i, c in enumerate(value):
        if c.isupper() and i > 0:
            result += "-"
        result += c.lower()
    return result.replace("_", "-")


def to_snake_case(value: str) -> str:
    """Convert kebab-case or PascalCase to snake_case."""
    result = ""
    for i, c in enumerate(value):
        if c.isupper() and i > 0:
            result += "_"
        result += c.lower()
    return result.replace("-", "_")


def to_upper_snake_case(value: str) -> str:
    """Convert to UPPER_SNAKE_CASE."""
    return to_snake_case(value).upper()


def pluralize(value: str) -> str:
    """Simple English pluralization."""
    if value.endswith("y"):
        return value[:-1] + "ies"
    if value.endswith(("s", "x", "z", "ch", "sh")):
        return value + "es"
    return value + "s"


def singularize(value: str) -> str:
    """Simple English singularization."""
    if value.endswith("ies"):
        return value[:-3] + "y"
    if value.endswith("es"):
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


def indent(text: str, spaces: int = 4) -> str:
    """Indent each line of text by the given number of spaces."""
    prefix = " " * spaces
    return "\n".join(prefix + line if line else "" for line in text.split("\n"))


def comment_block(text: str, prefix: str = "// ") -> str:
    """Wrap text in comment lines."""
    lines = text.strip().split("\n")
    return "\n".join(f"{prefix}{line}" for line in lines)


# ════════════════════════════════════════════════════════════════════════════
# Template Engine
# ════════════════════════════════════════════════════════════════════════════

class TemplateEngine:
    """
    Jinja2-based template engine with stack-specific template directories.

    Features:
    - Auto-discovery of templates per tech stack
    - Custom filters for naming conventions
    - Built-in helpers for common codegen tasks
    - Template inheritance and includes
    """

    def __init__(self, template_root: Optional[str] = None):
        if template_root is None:
            template_root = str(Path(__file__).parent)

        self._template_root = Path(template_root)
        self._env = Environment(
            loader=FileSystemLoader(str(self._template_root)),
            autoescape=select_autoescape(["html", "xml", "jsx", "tsx"]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

        # Register custom filters
        self._env.filters.update({
            "pascal": to_pascal_case,
            "camel": to_camel_case,
            "kebab": to_kebab_case,
            "snake": to_snake_case,
            "upper_snake": to_upper_snake_case,
            "plural": pluralize,
            "singular": singularize,
            "indent": indent,
            "comment": comment_block,
        })

        # Register global helpers
        self._env.globals.update({
            "now": lambda: __import__("datetime").datetime.now().isoformat(),
            "uuid": lambda: __import__("uuid").uuid4().hex[:8],
            "uuid_full": lambda: str(__import__("uuid").uuid4()),
        })

    def get_template(self, name: str) -> Template:
        """Load a template by name (relative to template root)."""
        try:
            return self._env.get_template(name)
        except TemplateNotFound as e:
            raise TemplateNotFound(f"Template not found: {name}") from e

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with the given context."""
        template = self.get_template(template_name)
        return template.render(**context)

    def render_to_file(
        self,
        template_name: str,
        context: Dict[str, Any],
        output_path: str,
        make_dirs: bool = True,
    ) -> str:
        """Render template and write to file."""
        content = self.render(template_name, context)
        path = Path(output_path)
        if make_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return content

    def list_templates(self, stack: Optional[str] = None) -> List[str]:
        """List available templates, optionally filtered by stack."""
        if stack:
            stack_dir = self._template_root / stack
            if not stack_dir.exists():
                return []
            base = stack_dir
        else:
            base = self._template_root

        templates = []
        for root, dirs, files in os.walk(base):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.endswith((".j2", ".jinja2", ".tmpl")):
                    rel_root = Path(root).relative_to(self._template_root)
                    templates.append(str(rel_root / f))
        return sorted(templates)


# ════════════════════════════════════════════════════════════════════════════
# Stack-Specific Template Loading
# ════════════════════════════════════════════════════════════════════════════

class StackTemplateLoader:
    """
    Loads templates for a specific tech stack with fallback to base templates.
    """

    def __init__(self, engine: TemplateEngine, stack: str):
        self._engine = engine
        self._stack = stack
        # Check stack directory FIRST, then base as fallback
        self._base_dirs = [
            engine._template_root / stack,
            engine._template_root / "base",
        ]

    def get_template(self, name: str) -> Template:
        """Try to load template from stack dir, then base dir."""
        for base_dir in self._base_dirs:
            template_path = base_dir / name
            if template_path.exists():
                rel_path = template_path.relative_to(self._engine._template_root)
                # Use forward slashes for Jinja2 FileSystemLoader (cross-platform)
                return self._engine.get_template(str(rel_path).replace("\\", "/"))
        raise TemplateNotFound(f"Template {name} not found for stack {self._stack}")

    def render(self, name: str, context: Dict[str, Any]) -> str:
        return self.get_template(name).render(**context)

    def render_to_file(
        self,
        name: str,
        context: Dict[str, Any],
        output_path: str,
        make_dirs: bool = True,
        dry_run: bool = False,
    ) -> str:
        template = self.get_template(name)
        content = template.render(**context)
        if not dry_run:
            path = Path(output_path)
            if make_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return content


# ════════════════════════════════════════════════════════════════════════════
# Template Context Builders
# ════════════════════════════════════════════════════════════════════════════

def build_project_context(
    *,
    project_name: str,
    project_description: str = "",
    tech_stack: Dict[str, str],
    target: str = "web",
    features: Optional[List[str]] = None,
    database: Optional[Dict[str, Any]] = None,
    auth: Optional[Dict[str, Any]] = None,
    api: Optional[Dict[str, Any]] = None,
    deployment: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a comprehensive context for project template rendering."""
    ctx = {
        "project_name": project_name,
        "project_name_pascal": to_pascal_case(project_name),
        "project_name_camel": to_camel_case(project_name),
        "project_name_kebab": to_kebab_case(project_name),
        "project_name_snake": to_snake_case(project_name),
        "project_description": project_description,
        "tech_stack": tech_stack,
        "target": target,
        "features": features or [],
        "database": database or {},
        "auth": auth or {},
        "api": api or {},
        "deployment": deployment or {},
        "frontend": tech_stack.get("frontend", ""),
        "backend": tech_stack.get("backend", ""),
        "styling": tech_stack.get("styling", ""),
        "has_backend": bool(tech_stack.get("backend")),
        "has_database": bool(tech_stack.get("database") or database),
        "has_auth": bool(tech_stack.get("auth") or auth),
        "is_mobile": target in ("mobile", "both"),
        "is_web": target in ("web", "both"),
        "is_fullstack": bool(tech_stack.get("backend")),
        **extra,
    }
    return ctx


def build_component_context(
    *,
    name: str,
    props: Optional[List[Dict[str, Any]]] = None,
    hooks: Optional[List[str]] = None,
    imports: Optional[List[str]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build context for a React/Vue/Svelte component template."""
    return {
        "name": name,
        "name_pascal": to_pascal_case(name),
        "name_camel": to_camel_case(name),
        "name_kebab": to_kebab_case(name),
        "props": props or [],
        "hooks": hooks or [],
        "imports": imports or [],
        **extra,
    }


def build_api_route_context(
    *,
    path: str,
    method: str,
    handler_name: str,
    request_model: Optional[str] = None,
    response_model: Optional[str] = None,
    auth_required: bool = False,
    **extra: Any,
) -> Dict[str, Any]:
    """Build context for an API route template."""
    return {
        "path": path,
        "method": method.upper(),
        "handler_name": handler_name,
        "request_model": request_model,
        "response_model": response_model,
        "auth_required": auth_required,
        **extra,
    }


# ════════════════════════════════════════════════════════════════════════════
# Singleton
# ════════════════════════════════════════════════════════════════════════════

_ENGINE: Optional[TemplateEngine] = None


def get_template_engine(template_root: Optional[str] = None) -> TemplateEngine:
    """Get the global template engine instance."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = TemplateEngine(template_root)
    return _ENGINE


def get_stack_loader(stack: str, template_root: Optional[str] = None) -> StackTemplateLoader:
    """Get a stack-specific template loader."""
    engine = get_template_engine(template_root)
    return StackTemplateLoader(engine, stack)