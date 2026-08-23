"""
BackendGenerator — code generation engine for the BackendAgent.

Generates FastAPI routes, Pydantic models, and service modules from structured
specs. Materializes file artifacts from specs produced by the agent's reasoning
loop; does not call the LLM directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RouteSpec:
    """Specification for a single FastAPI route."""
    path: str
    method: str
    handler: str
    request_model: str = ""
    response_model: str = ""
    description: str = ""


@dataclass
class ModelSpec:
    """Specification for a single Pydantic/Mongo model."""
    name: str
    fields: Dict[str, str] = field(default_factory=dict)
    collection: str = ""


@dataclass
class ServiceSpec:
    """Specification for a service module."""
    name: str
    path: str
    methods: List[str] = field(default_factory=list)


class BackendGenerator:
    """Generates backend file artifacts from Route/Model/Service specs."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def generate_route(self, spec: RouteSpec) -> str:
        decorator = f"@router.{spec.method.lower()}('{spec.path}')"
        sig = ""
        if spec.request_model:
            sig = f", payload: {spec.request_model}"
        ret = f" -> {spec.response_model}" if spec.response_model else ""
        return (
            f"from fastapi import APIRouter\nrouter = APIRouter()\n\n"
            f"{decorator}\n"
            f"async def {spec.handler}({sig}){ret}:\n"
            f"    return {{ 'ok': True }}\n"
        )

    def generate_model(self, spec: ModelSpec) -> str:
        fields = "\n".join(f"    {k}: {v}" for k, v in spec.fields.items())
        return (
            f"from pydantic import BaseModel\n\n"
            f"class {spec.name}(BaseModel):\n{fields}\n"
        )

    def generate(self, routes: List[RouteSpec], models: List[ModelSpec], services: List[ServiceSpec]) -> List[str]:
        created: List[str] = []
        for r in routes:
            p = self.project_root / f"routes/{r.handler}.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.generate_route(r), encoding="utf-8")
            created.append(str(p))
        for m in models:
            p = self.project_root / f"models/{m.name.lower()}.py"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self.generate_model(m), encoding="utf-8")
            created.append(str(p))
        return created
