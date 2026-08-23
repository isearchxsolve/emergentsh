"""
BackendGenerator — generates backend code for various frameworks.

Supports: FastAPI, Express.js, Django, NestJS, Go (Gin/Echo), Next.js API routes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..core.templates.engine import (
    StackTemplateLoader,
    build_api_route_context,
    build_project_context,
    get_stack_loader,
)
from ..core.workspace import WorkspaceManager, get_workspace, Project, Artifact


@dataclass
class RouteSpec:
    """Specification for an API route/endpoint."""
    path: str  # e.g., "/api/posts", "/api/posts/{id}"
    method: str  # GET, POST, PUT, PATCH, DELETE
    name: str  # e.g., "getPosts", "createPost"
    description: str = ""
    request_model: Optional[str] = None  # Pydantic/Zod schema name
    response_model: Optional[str] = None
    auth_required: bool = True
    permissions: List[str] = field(default_factory=list)
    query_params: List[Dict[str, Any]] = field(default_factory=list)
    path_params: List[Dict[str, Any]] = field(default_factory=list)
    status_code: int = 200
    summary: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class ModelSpec:
    """Specification for a database model/entity."""
    name: str
    fields: List[Dict[str, Any]]  # name, type, constraints
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[List[str]] = field(default_factory=list)
    unique_constraints: List[List[str]] = field(default_factory=list)
    table_name: Optional[str] = None
    description: str = ""


@dataclass
class ServiceSpec:
    """Specification for a service/business logic module."""
    name: str
    methods: List[Dict[str, Any]]  # name, params, return_type, description
    dependencies: List[str] = field(default_factory=list)
    description: str = ""


class BackendGenerator:
    """
    Generates backend code artifacts for specialist agents.

    Used by the BackendAgent to produce:
    - API routes/endpoints (REST, GraphQL, tRPC)
    - Database models (Prisma, SQLAlchemy, Django ORM, TypeORM, Prisma)
    - Services/business logic
    - Middleware (auth, logging, rate limiting)
    - Validators (Zod, Pydantic, class-validator)
    - Database migrations
    - Tests (unit, integration)
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
        self._stack_loader = get_stack_loader(project.tech_stack.get("backend", "fastapi"))

    # ----------------------------------------------------------------------
    # Route/Endpoint Generation
    # ----------------------------------------------------------------------
    def generate_route(self, spec: RouteSpec) -> Dict[str, str]:
        """
        Generate an API route/endpoint.

        Returns:
            Dict mapping file paths to content.
        """
        context = build_api_route_context(
            path=spec.path,
            method=spec.method,
            handler_name=spec.name,
            request_model=spec.request_model,
            response_model=spec.response_model,
            auth_required=spec.auth_required,
            permissions=spec.permissions,
            query_params=spec.query_params,
            path_params=spec.path_params,
            status_code=spec.status_code,
            summary=spec.summary,
            tags=spec.tags,
        )
        context.update(build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        ))

        # Determine output path based on framework
        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if "nextjs" in backend:
            output_path = f"src/app/api{spec.path}/route.{ext}"
        elif "fastapi" in backend:
            output_path = f"backend/api/routes/{spec.name}.{ext}"
        elif "express" in backend:
            output_path = f"backend/src/routes/{spec.name}.{ext}"
        elif "django" in backend:
            output_path = f"backend/{spec.name}_views.{ext}"
        else:
            output_path = f"backend/routes/{spec.name}.{ext}"

        template_name = self._get_route_template(backend, spec.method)
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_route(spec, context, backend)

        return {output_path: content}

    def generate_model(self, spec: ModelSpec) -> Dict[str, str]:
        """Generate a database model/entity."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "model_name": spec.name,
            "table_name": spec.table_name or spec.name.lower(),
            "fields": spec.fields,
            "relationships": spec.relationships,
            "indexes": spec.indexes,
            "unique_constraints": spec.unique_constraints,
            "description": spec.description,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if "prisma" in str(self._project.tech_stack.get("database", "")).lower() or "prisma" in backend:
            output_path = f"prisma/schema.prisma"
            template_name = "models/prisma-model.prisma.j2"
        elif "fastapi" in backend or "sqlalchemy" in backend:
            output_path = f"backend/models/{spec.name.lower()}.{ext}"
            template_name = f"models/sqlalchemy-model.{ext}.j2"
        elif "django" in backend:
            output_path = f"backend/{spec.name.lower()}_models.{ext}"
            template_name = f"models/django-model.{ext}.j2"
        elif "express" in backend and "typeorm" in str(self._project.tech_stack).lower():
            output_path = f"backend/src/entities/{spec.name}.{ext}"
            template_name = f"models/typeorm-entity.{ext}.j2"
        else:
            output_path = f"backend/models/{spec.name.lower()}.{ext}"
            template_name = f"models/base-model.{ext}.j2"

        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_model(spec, context, backend)

        return {output_path: content}

    def generate_service(self, spec: ServiceSpec) -> Dict[str, str]:
        """Generate a service/business logic module."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "service_name": spec.name,
            "methods": spec.methods,
            "dependencies": spec.dependencies,
            "description": spec.description,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if "fastapi" in backend:
            output_path = f"backend/services/{spec.name.lower()}_service.{ext}"
        elif "express" in backend:
            output_path = f"backend/src/services/{spec.name.lower()}.service.{ext}"
        else:
            output_path = f"backend/services/{spec.name.lower()}.{ext}"

        template_name = f"services/{spec.name.lower()}.{ext}.j2"
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_service(spec, context, backend)

        return {output_path: content}

    def generate_middleware(self, name: str, middleware_type: str, config: Dict[str, Any]) -> Dict[str, str]:
        """Generate middleware (auth, logging, rate limiting, CORS, etc.)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "middleware_name": name,
            "middleware_type": middleware_type,
            "config": config,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if "fastapi" in backend:
            output_path = f"backend/middleware/{name.lower()}.{ext}"
        elif "express" in backend:
            output_path = f"backend/src/middleware/{name.lower()}.{ext}"
        else:
            output_path = f"backend/middleware/{name.lower()}.{ext}"

        template_name = f"middleware/{middleware_type}.{ext}.j2"
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_middleware(name, middleware_type, context, backend)

        return {output_path: content}

    def generate_validator(self, name: str, schema: Dict[str, Any]) -> Dict[str, str]:
        """Generate a validator (Zod, Pydantic, class-validator, Joi)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "validator_name": name,
            "schema": schema,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if "pydantic" in str(self._project.tech_stack).lower() or "fastapi" in backend:
            output_path = f"backend/validators/{name.lower()}.{ext}"
            template_name = "validators/pydantic-validator.py.j2"
        elif "zod" in str(self._project.tech_stack).lower() or "nextjs" in backend:
            output_path = f"src/validators/{name.lower()}.ts"
            template_name = "validators/zod-validator.ts.j2"
        elif "express" in backend:
            output_path = f"backend/src/validators/{name.lower()}.ts"
            template_name = "validators/zod-validator.ts.j2"
        else:
            output_path = f"backend/validators/{name.lower()}.{ext}"
            template_name = f"validators/base.{ext}.j2"

        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_validator(name, schema, backend)

        return {output_path: content}

    def generate_migration(self, name: str, operations: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate a database migration."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "migration_name": name,
            "operations": operations,
            "timestamp": __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S"),
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if "prisma" in str(self._project.tech_stack).lower():
            output_path = f"prisma/migrations/{context['timestamp']}_{name}/migration.sql"
        elif "alembic" in str(self._project.tech_stack).lower() or "fastapi" in backend:
            output_path = f"backend/migrations/{context['timestamp']}_{name}.{ext}"
        elif "django" in backend:
            output_path = f"backend/migrations/{context['timestamp']}_{name}.{ext}"
        else:
            output_path = f"backend/migrations/{context['timestamp']}_{name}.sql"

        template_name = "migrations/base-migration.j2"
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_migration(name, operations, backend)

        return {output_path: content}

    def generate_test(self, route_spec: RouteSpec, test_type: str = "integration") -> Dict[str, str]:
        """Generate tests for an endpoint (unit, integration, contract)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "route": route_spec,
            "test_type": test_type,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = self._get_extension(backend)

        if test_type == "unit":
            output_path = f"backend/tests/unit/test_{route_spec.name.lower()}.{ext}"
        elif test_type == "integration":
            output_path = f"backend/tests/integration/test_{route_spec.name.lower()}.{ext}"
        elif test_type == "contract":
            output_path = f"backend/tests/contracts/test_{route_spec.name.lower()}.{ext}"
        else:
            output_path = f"backend/tests/test_{route_spec.name.lower()}.{ext}"

        template_name = f"tests/{test_type}-test.{ext}.j2"
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_test(route_spec, test_type, backend)

        return {output_path: content}

    def persist_artifacts(self, artifacts: Dict[str, str], task_id: str) -> None:
        """Persist generated artifacts to workspace and project."""
        if not self._workspace:
            return

        for path, content in artifacts.items():
            full_path = Path(self._project.root_dir) / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

            artifact = Artifact(
                id=f"art-{abs(hash(f'{task_id}:{path}')) % 1000000:06d}",
                project_id=self._project.id,
                task_id=task_id,
                agent_role="backend",
                kind="file",
                path=path,
                content=content,
                metadata={},
            )
            self._workspace.save_artifact(artifact)

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _get_extension(self, backend: str) -> str:
        if "fastapi" in backend or "django" in backend:
            return "py"
        if "express" in backend or "nest" in backend or "nextjs" in backend:
            return "ts"
        if "go" in backend or "gin" in backend or "echo" in backend:
            return "go"
        return "py"  # default

    def _get_route_template(self, backend: str, method: str) -> str:
        ext = self._get_extension(backend)
        templates = {
            "fastapi": f"routes/fastapi-{method.lower()}.{ext}.j2",
            "express": f"routes/express-{method.lower()}.{ext}.j2",
            "nextjs": f"routes/nextjs-route.{ext}.j2",
            "django": f"routes/django-view.{ext}.j2",
        }
        return templates.get(backend, f"routes/base-{method.lower()}.{ext}.j2")

    def _render_base_route(self, spec: RouteSpec, context: Dict, backend: str) -> str:
        """Fallback base route template."""
        if "fastapi" in backend:
            return self._render_fastapi_route(spec)
        elif "express" in backend:
            return self._render_express_route(spec)
        elif "nextjs" in backend:
            return self._render_nextjs_route(spec)
        return ""

    def _render_fastapi_route(self, spec: RouteSpec) -> str:
        request_model = f", request: {spec.request_model}" if spec.request_model else ""
        response_model = f" -> {spec.response_model}" if spec.response_model else ""
        auth = "current_user: User = Depends(get_current_user)" if spec.auth_required else ""

        return f'''from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

router = APIRouter(prefix="/api", tags={spec.tags})

@router.{spec.method.lower()}("{spec.path}", response_model={spec.response_model or "dict"}, status_code={spec.status_code})
async def {spec.name}({auth}{request_model}):
    """
    {spec.description or spec.summary}
    """
    # TODO: Implement {spec.name}
    # Example:
    # if {spec.method} == "GET":
    #     return await service.get_all()
    # elif {spec.method} == "POST":
    #     return await service.create(request)
    raise HTTPException(status_code=501, detail="Not implemented")
'''

    def _render_express_route(self, spec: RouteSpec) -> str:
        return f'''import {{ Request, Response, NextFunction }} from 'express'
import {{ {spec.request_model or ''} }} from '../validators/{spec.name}'

export const {spec.name} = async (
  req: Request,
  res: Response,
  next: NextFunction
) => {{
  try {{
    // TODO: Implement {spec.name}
    // const data = await service.{spec.name}(req.body)
    // res.status({spec.status_code}).json(data)
    res.status(501).json({{ error: 'Not implemented' }})
  }} catch (error) {{
    next(error)
  }}
}}
'''

    def _render_nextjs_route(self, spec: RouteSpec) -> str:
        return f'''import {{ NextRequest, NextResponse }} from 'next/server'

export async function {spec.method.upper()}(request: NextRequest) {{
  try {{
    // TODO: Implement {spec.name}
    // const body = await request.json()
    // const data = await service.{spec.name}(body)
    return NextResponse.json({{ error: 'Not implemented' }}, {{ status: 501 }})
  }} catch (error) {{
    return NextResponse.json({{ error: 'Internal Server Error' }}, {{ status: 500 }})
  }}
}}
'''

    def _render_base_model(self, spec: ModelSpec, context: Dict, backend: str) -> str:
        if "prisma" in str(self._project.tech_stack).lower():
            return self._render_prisma_model(spec)
        elif "fastapi" in backend:
            return self._render_sqlalchemy_model(spec)
        elif "django" in backend:
            return self._render_django_model(spec)
        return ""

    def _render_prisma_model(self, spec: ModelSpec) -> str:
        fields = []
        for f in spec.fields:
            field_def = f"  {f['name']} {f['type']}"
            if f.get("optional"):
                field_def += "?"
            if f.get("unique"):
                field_def += " @unique"
            if f.get("default"):
                field_def += f" @default({f['default']})"
            if f.get("relation"):
                field_def += f" @relation({f['relation']})"
            fields.append(field_def)

        relations = []
        for r in spec.relationships:
            relations.append(f"  {r['name']} {r['type']} @relation(\"{r['relation_name']}\")")

        return f"""model {spec.name} {{
{chr(10).join(fields)}
{chr(10).join(relations) if relations else ''}
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  @@map("{spec.table_name or spec.name.lower()}")
}}"""

    def _render_sqlalchemy_model(self, spec: ModelSpec) -> str:
        fields = []
        for f in spec.fields:
            col_type = f["type"].replace("String", "String").replace("Int", "Integer").replace("Bool", "Boolean")
            nullable = "nullable=True" if f.get("optional") else "nullable=False"
            unique = "unique=True" if f.get("unique") else ""
            default = f"default={f['default']}" if f.get("default") else ""
            args = ", ".join(filter(None, [nullable, unique, default]))
            fields.append(f"    {f['name']} = Column({col_type}, {args})")

        relationships = []
        for r in spec.relationships:
            relationships.append(f"    {r['name']} = relationship(\"{r['type']}\", back_populates=\"{r.get('back_populates', '')}\")")

        return f"""from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class {spec.name}(Base):
    __tablename__ = "{spec.table_name or spec.name.lower()}"

{chr(10).join(fields)}
{chr(10).join(relationships) if relationships else ''}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
"""

    def _render_django_model(self, spec: ModelSpec) -> str:
        fields = []
        for f in spec.fields:
            dj_type = f["type"].replace("String", "CharField").replace("Int", "IntegerField").replace("Bool", "BooleanField")
            args = []
            if f.get("optional"):
                args.append("null=True, blank=True")
            if f.get("unique"):
                args.append("unique=True")
            if f.get("default"):
                args.append(f"default={f['default']}")
            fields.append(f"    {f['name']} = models.{dj_type}({', '.join(args)})")

        return f"""from django.db import models

class {spec.name}(models.Model):
{chr(10).join(fields)}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "{spec.table_name or spec.name.lower()}"
"""

    def _render_base_service(self, spec: ServiceSpec, context: Dict, backend: str) -> str:
        if "fastapi" in backend:
            return f'''from typing import List, Optional
from sqlalchemy.orm import Session

class {spec.name}Service:
    def __init__(self, db: Session):
        self.db = db

    # TODO: Implement methods
    # {chr(10).join(f"    async def {m['name']}(self, {', '.join(m.get('params', []))}) -> {m.get('return_type', 'Any')}: pass" for m in spec.methods)}
'''
        elif "express" in backend:
            return f'''import {{ Injectable }} from '@nestjs/common'

@Injectable()
export class {spec.name}Service {{
  // TODO: Implement methods
  // {chr(10).join(f"  async {m['name']}({', '.join(m.get('params', []))}): Promise<{m.get('return_type', 'any')}> {{ }}" for m in spec.methods)}
}}
'''
        return ""

    def _render_base_middleware(self, name: str, middleware_type: str, context: Dict, backend: str) -> str:
        if "fastapi" in backend:
            return f'''from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class {name}Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # TODO: Implement {middleware_type} logic
        response = await call_next(request)
        return response
'''
        elif "express" in backend:
            return f'''import {{ Request, Response, NextFunction }} from 'express'

export const {name}Middleware = (
  req: Request,
  res: Response,
  next: NextFunction
) => {{
  // TODO: Implement {middleware_type} logic
  next()
}}
'''
        return ""

    def _render_base_validator(self, name: str, schema: Dict, backend: str) -> str:
        if "pydantic" in str(self._project.tech_stack).lower():
            return f'''from pydantic import BaseModel, Field
from typing import Optional

class {name}Validator(BaseModel):
    # TODO: Define fields based on schema
    pass
'''
        elif "zod" in str(self._project.tech_stack).lower():
            return f'''import {{ z }} from 'zod'

export const {name}Schema = z.object({{
  // TODO: Define schema based on {schema}
}})

export type {name}Input = z.infer<typeof {name}Schema>
'''
        return ""

    def _render_base_migration(self, name: str, operations: List[Dict], backend: str) -> str:
        if "prisma" in str(self._project.tech_stack).lower():
            return f"""-- Migration: {name}
-- Generated at: {__import__('datetime').datetime.now().isoformat()}

-- TODO: Add migration operations
-- {chr(10).join(f"-- {op}" for op in operations)}
"""
        elif "alembic" in str(self._project.tech_stack).lower():
            return f'''"""Migration: {name}"""
from alembic import op
import sqlalchemy as sa

revision = '{__import__("uuid").uuid4().hex[:12]}'
down_revision = None

def upgrade():
    # TODO: Add upgrade operations
    pass

def downgrade():
    # TODO: Add downgrade operations
    pass
'''
        return ""

    def _render_base_test(self, route_spec: RouteSpec, test_type: str, backend: str) -> str:
        if "fastapi" in backend:
            return f'''import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_{route_spec.name}_returns_200():
    response = client.{route_spec.method.lower()}("{route_spec.path}")
    assert response.status_code == 200

def test_{route_spec.name}_validates_input():
    # TODO: Add validation tests
    pass
'''
        return ""


# Convenience function
def create_backend_generator(
    project: Project,
    workspace: Optional[WorkspaceManager] = None,
    template_root: Optional[str] = None,
) -> BackendGenerator:
    return BackendGenerator(project, workspace, template_root)