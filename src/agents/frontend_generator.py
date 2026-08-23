"""
FrontendGenerator — generates frontend code for various frameworks.

Supports: Next.js (App Router), Vite+React, SvelteKit, Nuxt, Expo/React Native.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..core.scaffold import ScaffoldGenerator, get_scaffold_generator
from ..core.templates.engine import (
    StackTemplateLoader,
    build_component_context,
    build_project_context,
    get_stack_loader,
)
from ..core.workspace import WorkspaceManager, get_workspace, Project, Artifact


@dataclass
class ComponentSpec:
    """Specification for a component to generate."""
    name: str
    type: str  # "component", "page", "hook", "layout", "provider"
    props: List[Dict[str, Any]] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    description: str = ""
    file_path: Optional[str] = None  # Override default path


@dataclass
class PageSpec:
    """Specification for a page to generate."""
    route: str  # e.g., "/dashboard", "/posts/[id]"
    name: str
    description: str = ""
    components: List[str] = field(default_factory=list)  # Component names to use
    data_fetching: str = "client"  # "client", "server", "static"
    auth_required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class FrontendGenerator:
    """
    Generates frontend code artifacts for specialist agents.

    Used by the FrontendAgent to produce:
    - Components (UI, forms, data display)
    - Pages (route segments)
    - Hooks (data fetching, state, effects)
    - Layouts (shell, sidebar, auth)
    - Providers (theme, auth, query)
    - Styles (Tailwind, CSS Modules, styled-components)
    - Types (TypeScript interfaces)
    """

    def __init__(
        self,
        project: Project,
        workspace: Optional[WorkspaceManager] = None,
        template_root: Optional[str] = None,
    ):
        self._project = project
        self._workspace = workspace or get_workspace()
        self._template_root = template_root
        self._stack_loader = get_stack_loader(project.tech_stack.get("frontend", "nextjs"))
        self._scaffold_gen = ScaffoldGenerator(template_root)

    # ----------------------------------------------------------------------
    # Component Generation
    # ----------------------------------------------------------------------
    def generate_component(self, spec: ComponentSpec) -> Dict[str, str]:
        """
        Generate a React/Vue/Svelte component.

        Returns:
            Dict mapping file paths to content.
        """
        context = build_component_context(
            name=spec.name,
            props=spec.props,
            hooks=spec.hooks,
            imports=spec.imports,
        )
        # Add project context
        context.update(build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        ))

        # Determine output path
        ext = self._get_component_extension()
        if spec.file_path:
            output_path = spec.file_path
        else:
            output_path = f"src/components/{spec.type}s/{spec.name}.{ext}"

        # Get template
        template_name = self._get_component_template(spec.type)
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            # Fallback to base component template
            content = self._render_base_component(spec, context)

        return {output_path: content}

    def generate_page(self, spec: PageSpec) -> Dict[str, str]:
        """Generate a page (route segment) with optional layout."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "page_name": spec.name,
            "page_route": spec.route,
            "page_description": spec.description,
            "data_fetching": spec.data_fetching,
            "auth_required": spec.auth_required,
            "components": spec.components,
            "metadata": spec.metadata,
        })

        ext = self._get_page_extension()
        output_path = f"src/app{spec.route}/page.{ext}"

        template_name = self._get_page_template(spec.data_fetching)
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_page(spec, context)

        return {output_path: content}

    def generate_hook(self, name: str, hook_type: str, params: Dict[str, Any]) -> Dict[str, str]:
        """Generate a custom React hook (useQuery, useMutation, useState, etc.)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "hook_name": name,
            "hook_type": hook_type,
            "params": params,
        })

        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "js"
        output_path = f"src/hooks/use{name}.{ext}"

        template_name = f"hooks/use{hook_type}.{ext}.j2"
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_hook(name, hook_type, context)

        return {output_path: content}

    def generate_layout(self, name: str, children: str, props: Dict[str, Any] = None) -> Dict[str, str]:
        """Generate a layout component."""
        context = build_component_context(
            name=name,
            props=props or {},
        )
        context.update(build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        ))

        ext = self._get_component_extension()
        output_path = f"src/app/(layout)/{name}/layout.{self._get_component_extension()}"

        try:
            content = self._stack_loader.render("layout.tsx.j2", context)
        except Exception:
            content = self._render_base_layout(name, context)

        return {output_path: content}

    def generate_provider(self, name: str, provider_type: str, config: Dict[str, Any]) -> Dict[str, str]:
        """Generate a context provider (Theme, Auth, Query, etc.)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "provider_name": name,
            "provider_type": provider_type,
            "config": config,
        })

        ext = self._get_component_extension()
        output_path = f"src/providers/{name}Provider.{ext}"

        try:
            content = self._stack_loader.render(f"providers/{provider_type}.{ext}.j2", context)
        except Exception:
            content = self._render_base_provider(name, provider_type, context)

        return {output_path: content}

    def generate_types(self, types: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        """Generate TypeScript type definitions."""
        output_path = "src/types/index.ts"
        content = "// Auto-generated types\n\n"
        for name, definition in types.items():
            content += f"export interface {name} {{\n"
            for prop, prop_type in definition.items():
                content += f"  {prop}: {prop_type};\n"
            content += "}\n\n"
        return {output_path: content}

    def generate_api_client(self, endpoints: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate a typed API client (TanStack Query / Axios / Fetch)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context["endpoints"] = endpoints

        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "js"
        output_path = f"src/lib/api.{ext}"

        try:
            content = self._stack_loader.render(f"lib/api-client.{ext}.j2", context)
        except Exception:
            content = self._render_base_api_client(endpoints, context)

        return {output_path: content}

    def persist_artifacts(self, artifacts: Dict[str, str], task_id: str) -> None:
        """Persist generated artifacts to workspace and project."""
        if not self._workspace:
            return

        for path, content in artifacts.items():
            full_path = Path(self._project.root_dir) / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

            # Record in workspace
            artifact = Artifact(
                id=f"art-{abs(hash(f'{task_id}:{path}')) % 1000000:06d}",
                project_id=self._project.id,
                task_id=task_id,
                agent_role="frontend",
                kind="file",
                path=path,
                content=content,
                metadata={},
            )
            self._workspace.save_artifact(artifact)

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _get_component_extension(self) -> str:
        frontend = self._project.tech_stack.get("frontend", "")
        if "svelte" in frontend:
            return "svelte"
        if "vue" in frontend or "nuxt" in frontend:
            return "vue"
        return "tsx"  # default: React/Next.js

    def _get_page_extension(self) -> str:
        return self._get_component_extension()

    def _get_component_template(self, component_type: str) -> str:
        """Map component type to template name."""
        ext = self._get_component_extension()
        templates = {
            "component": f"components/ui/base.{ext}.j2",
            "form": f"components/forms/form.{ext}.j2",
            "table": f"components/data/table.{ext}.j2",
            "card": f"components/ui/card.{ext}.j2",
            "modal": f"components/ui/modal.{ext}.j2",
        }
        return templates.get(component_type, templates["component"])

    def _get_page_template(self, data_fetching: str) -> str:
        ext = self._get_page_extension()
        templates = {
            "server": f"pages/server-page.{ext}.j2",
            "client": f"pages/client-page.{ext}.j2",
            "static": f"pages/static-page.{ext}.j2",
        }
        return templates.get(data_fetching, templates["client"])

    def _render_base_component(self, spec: ComponentSpec, context: Dict) -> str:
        """Fallback base component template."""
        ext = self._get_component_extension()
        props_str = ", ".join(f"{p['name']}: {p['type']}" for p in spec.props) if spec.props else ""
        return f"""import {{ {', '.join(spec.imports) if spec.imports else ''} }} from '...'

interface {spec.name}Props {{
  {props_str}
}}

export function {spec.name}({{ {props_str} }}: {spec.name}Props) {{
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold">{spec.name}</h2>
      <p className="text-muted-foreground">{spec.description or 'Component description'}</p>
    </div>
  )
}}
"""

    def _render_base_page(self, spec: PageSpec, context: Dict) -> str:
        """Fallback base page template."""
        ext = self._get_page_extension()
        return f"""import {{ Metadata }} from 'next'

export const metadata: Metadata = {{
  title: '{spec.name}',
  description: '{spec.description}',
}}

export default function {spec.name.replace('/', '')}Page() {{
  return (
    <div className="container mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-6">{spec.name}</h1>
      <p className="text-muted-foreground">{spec.description or 'Page description'}</p>
    </div>
  )
}}
"""

    def _render_base_hook(self, name: str, hook_type: str, context: Dict) -> str:
        """Fallback base hook template."""
        return f"""import {{ useState, useEffect }} from 'react'

export function use{name}() {{
  const [data, setData] = useState<{name}Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {{
    async function fetchData() {{
      try {{
        setLoading(true)
        // TODO: Implement data fetching
        // const response = await fetch('/api/{name.lower()}')
        // const json = await response.json()
        // setData(json)
      }} catch (err) {{
        setError(err as Error)
      }} finally {{
        setLoading(false)
      }}
    }}

    fetchData()
  }}, [])

  return {{ data, loading, error }}
}}

interface {name}Data {{
  // TODO: Define data shape
}}
"""

    def _render_base_layout(self, name: str, context: Dict) -> str:
        """Fallback base layout template."""
        ext = self._get_component_extension()
        return f"""export default function {name}Layout({{
  children,
}}: {{
  children: React.ReactNode
}}) {{
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b p-4">
        <nav className="container mx-auto flex justify-between">
          <a href="/" className="font-bold text-xl">{context.get('project_name', 'App')}</a>
          <nav className="flex gap-4">
            <a href="/dashboard">Dashboard</a>
            <a href="/settings">Settings</a>
          </nav>
        </nav>
      </header>
      <main className="flex-1 container mx-auto py-8 px-4">
        {{children}}
      </main>
      <footer className="border-t p-4 text-center text-muted-foreground">
        © {2024} {context.get('project_name', 'App')}
      </footer>
    </div>
  )
}}
"""

    def _render_base_provider(self, name: str, provider_type: str, context: Dict) -> str:
        """Fallback base provider template."""
        return f"""import {{ createContext, useContext, useState, ReactNode }} from 'react'

interface {name}ContextType {{
  // TODO: Define context shape
}}

const {name}Context = createContext<{name}ContextType | undefined>(undefined)

export function {name}Provider({{ children }}: {{ children: ReactNode }}) {{
  const [state, setState] = useState<{name}ContextType>()

  return (
    <{name}Context.Provider value={{{{ state, setState }}}}>
      {{children}}
    </{name}Context.Provider>
  )
}}

export function use{name}() {{
  const context = useContext({name}Context)
  if (!context) {{
    throw new Error('use{name} must be used within a {name}Provider')
  }}
  return context
}}
"""

    def _render_base_api_client(self, endpoints: List[Dict], context: Dict) -> str:
        """Fallback base API client template."""
        return f"""import {{ useQuery, useMutation, useQueryClient }} from '@tanstack/react-query'
import axios from 'axios'

const api = axios.create({{
  baseURL: process.env.NEXT_PUBLIC_API_URL || '/api',
  headers: {{
    'Content-Type': 'application/json',
  }},
}})

{{
  for ep in endpoints:
    print(f"export function {ep['name']}() {{")
    print(f"  return useQuery({{ queryKey: ['{ep['path']}'], queryFn: () => api.{ep['method'].lower()}('{ep['path']}') }})")
    print(f"  return useMutation({{ mutationFn: (data) => api.{ep['method'].lower()}('{ep['path']}', data) }})")
}}
"""


# Convenience function
def create_frontend_generator(
    project: Project,
    workspace: Optional[WorkspaceManager] = None,
    template_root: Optional[str] = None,
) -> FrontendGenerator:
    return FrontendGenerator(project, workspace, template_root)