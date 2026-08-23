"""
FrontendGenerator — code generation engine for the FrontendAgent.

Generates React/Next.js components, pages, hooks, and types from structured
specs. This is the codegen layer invoked by the FrontendAgent; it does not
call the LLM directly — it materializes file artifacts from specs produced
by the agent's reasoning loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ComponentSpec:
    """Specification for a single React component."""
    name: str
    path: str
    props: Dict[str, str] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)
    styling: str = "tailwind"
    description: str = ""


@dataclass
class PageSpec:
    """Specification for a single page/route."""
    name: str
    route: str
    path: str
    components: List[str] = field(default_factory=list)
    layout: str = "default"
    metadata: Dict[str, str] = field(default_factory=dict)


class FrontendGenerator:
    """Generates frontend file artifacts from ComponentSpec/PageSpec lists."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def generate_component(self, spec: ComponentSpec) -> str:
        """Render a single component file's contents."""
        props_str = ", ".join(f"{k}: {v}" for k, v in spec.props.items())
        return (
            f"// {spec.description or spec.name}\n"
            f"export function {spec.name}({ '{{' }{props_str}{ '}}' }: {{ {props_str} }}) {{\n"
            f"  return (\n    <div>{spec.name}</div>\n  );\n"
            f"}}\n"
        )

    def generate_page(self, spec: PageSpec) -> str:
        """Render a single page file's contents."""
        return (
            f"// Page: {spec.name} at {spec.route}\n"
            f"export default function {spec.name}Page() {{\n"
            f"  return <div>{spec.name}</div>;\n"
            f"}}\n"
        )

    def generate(self, components: List[ComponentSpec], pages: List[PageSpec]) -> List[str]:
        """Materialize all specs into files under project_root. Returns file paths."""
        created: List[str] = []
        for c in components:
            p = self.project_root / c.path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.generate_component(c), encoding="utf-8")
            created.append(str(p))
        for pg in pages:
            p = self.project_root / pg.path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.generate_page(pg), encoding="utf-8")
            created.append(str(p))
        return created
