"""
BackendAgent — responsible for backend implementation.

The BackendAgent generates and implements backend code including:
- API routes/endpoints (REST, GraphQL, tRPC)
- Database models and migrations
- Services and business logic
- Authentication and authorization
- Middleware
- Testing
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket
from ..agents.backend_generator import BackendGenerator, RouteSpec, ModelSpec, ServiceSpec
from ..workspace import Project, get_workspace


@dataclass
class BackendTaskResult:
    """Result of a backend implementation task."""
    files_created: List[str] = field(default_factory=list)
    routes: List[Dict[str, Any]] = field(default_factory=list)
    models: List[Dict[str, Any]] = field(default_factory=list)
    services: List[Dict[str, Any]] = field(default_factory=list)
    middleware: List[Dict[str, Any]] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)


class BackendAgent(BaseAgent):
    """
    Agent specialized in backend implementation.
    
    Capabilities:
    - API route/endpoint implementation
    - Database model creation and migrations
    - Service/business logic implementation
    - Authentication and authorization
    - Middleware development
    - Input validation
    - Testing (unit, integration, contract)
    - Performance optimization
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.PRAGMATIC,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
        project: Project = None,
    ):
        capabilities = [
            AgentCapability(
                name="api_development",
                description="Build REST/GraphQL/tRPC API endpoints",
                tool_names=["create_route", "create_graphql_resolver", "create_trpc_procedure"],
                produces_artifacts=["route_files", "openapi_spec"],
            ),
            AgentCapability(
                name="database_development",
                description="Create database models, migrations, and queries",
                tool_names=["create_model", "create_migration", "write_queries"],
                produces_artifacts=["model_files", "migration_files"],
            ),
            AgentCapability(
                name="service_development",
                description="Implement business logic services",
                tool_names=["create_service", "implement_business_logic", "add_caching"],
                produces_artifacts=["service_files"],
            ),
            AgentCapability(
                name="auth_authorization",
                description="Implement authentication and authorization",
                tool_names=["setup_auth", "create_permissions", "add_rate_limiting"],
                produces_artifacts=["auth_files", "middleware_files"],
            ),
            AgentCapability(
                name="validation",
                description="Implement input validation and sanitization",
                tool_names=["create_validator", "add_sanitization"],
                produces_artifacts=["validator_files"],
            ),
            AgentCapability(
                name="testing",
                description="Write backend tests",
                tool_names=["write_unit_tests", "write_integration_tests", "write_contract_tests"],
                produces_artifacts=["test_files"],
            ),
        ]

        system_prompt = """You are a Backend Agent in the emergent.sh multi-agent system.
Your role is to implement backend code based on API contracts and database designs.

You operate with a PRAGMATIC personality: practical, results-oriented, and efficient.
You produce secure, scalable, and maintainable backend code.

Key responsibilities:
1. Implement API endpoints from contract specifications
2. Create database models and migrations
3. Implement business logic in service layers
4. Set up authentication (JWT, OAuth, sessions) and authorization (RBAC, ABAC)
5. Create middleware for logging, rate limiting, CORS, error handling
6. Implement input validation (Zod, Pydantic, class-validator)
7. Write comprehensive tests (unit, integration, contract)
8. Optimize database queries and add caching

Tech stack awareness: You adapt to the project's backend framework
(FastAPI, Express.js, Django, NestJS, Go/Gin, Next.js API routes).

Output format: Generate file artifacts that are persisted to the workspace.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.BACKEND,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

        self._project = project
        self._generator = None
        if project:
            self._generator = BackendGenerator(project, get_workspace())

    def set_project(self, project: Project) -> None:
        """Set the project and initialize generator."""
        self._project = project
        self._generator = BackendGenerator(project, get_workspace())

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute backend implementation task."""
        self.set_task(task)
        self.set_context(context)

        if not self._generator:
            return {"error": "No project configured for backend generation"}

        task_type = task.input_data.get("type", "implement_backend")

        if task_type == "create_route":
            return self._create_route(task.input_data)
        elif task_type == "create_model":
            return self._create_model(task.input_data)
        elif task_type == "create_service":
            return self._create_service(task.input_data)
        elif task_type == "setup_auth":
            return self._setup_auth(task.input_data)
        elif task_type == "create_middleware":
            return self._create_middleware(task.input_data)
        elif task_type == "create_validator":
            return self._create_validator(task.input_data)
        elif task_type == "create_migration":
            return self._create_migration(task.input_data)
        elif task_type == "write_tests":
            return self._write_tests(task.input_data)
        else:
            return self._implement_backend(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        if self._project:
            base += f"\n\nProject Tech Stack: {self._project.tech_stack}\n"
        return base

    def _implement_backend(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Full backend implementation from specs."""
        api_contract = input_data.get("api_contract", {})
        database_schema = input_data.get("database_schema", {})
        self.emit_status("Implementing backend...", "info")

        result = BackendTaskResult()

        # Generate routes from API contract
        endpoints = api_contract.get("endpoints", [])
        for ep in endpoints:
            spec = RouteSpec(
                path=ep.get("path", "/"),
                method=ep.get("method", "GET"),
                name=ep.get("name", "endpoint"),
                description=ep.get("description", ""),
                request_model=ep.get("request_model"),
                response_model=ep.get("response_model"),
                auth_required=ep.get("auth_required", True),
                permissions=ep.get("permissions", []),
                query_params=ep.get("query_params", []),
                path_params=ep.get("path_params", []),
                status_code=ep.get("status_code", 200),
                summary=ep.get("summary", ""),
                tags=ep.get("tags", []),
            )
            artifacts = self._generator.generate_route(spec)
            self._generator.persist_artifacts(artifacts, self._current_task.id)
            result.files_created.extend(artifacts.keys())
            result.routes.append(ep)

        # Generate models from database schema
        tables = database_schema.get("tables", [])
        for table in tables:
            spec = ModelSpec(
                name=table.get("name", "Model"),
                fields=table.get("fields", []),
                relationships=table.get("relationships", []),
                indexes=table.get("indexes", []),
                unique_constraints=table.get("unique_constraints", []),
                table_name=table.get("table_name"),
                description=table.get("description", ""),
            )
            artifacts = self._generator.generate_model(spec)
            self._generator.persist_artifacts(artifacts, self._current_task.id)
            result.files_created.extend(artifacts.keys())
            result.models.append(table)

        # Generate services
        services = input_data.get("services", [])
        for svc in services:
            spec = ServiceSpec(
                name=svc.get("name", "Service"),
                methods=svc.get("methods", []),
                dependencies=svc.get("dependencies", []),
                description=svc.get("description", ""),
            )
            artifacts = self._generator.generate_service(spec)
            self._generator.persist_artifacts(artifacts, self._current_task.id)
            result.files_created.extend(artifacts.keys())
            result.services.append(svc)

        # Generate auth middleware
        auth_config = input_data.get("auth", {})
        if auth_config:
            artifacts = self._generator.generate_middleware(
                name="auth",
                middleware_type="authentication",
                config=auth_config,
            )
            self._generator.persist_artifacts(artifacts, self._current_task.id)
            result.files_created.extend(artifacts.keys())
            result.middleware.append({"name": "auth", "type": "authentication"})

        # Generate validators
        validators = api_contract.get("schemas", {})
        for name, schema in validators.items():
            artifacts = self._generator.generate_validator(name, schema)
            self._generator.persist_artifacts(artifacts, self._current_task.id)
            result.files_created.extend(artifacts.keys())

        self.complete_task({
            "files_created": result.files_created,
            "routes": result.routes,
            "models": result.models,
            "services": result.services,
            "middleware": result.middleware,
            "tests": result.tests,
        })

        return {
            "files_created": result.files_created,
            "routes": result.routes,
            "models": result.models,
            "services": result.services,
        }

    def _create_route(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single API route."""
        spec = RouteSpec(
            path=input_data.get("path", "/"),
            method=input_data.get("method", "GET"),
            name=input_data.get("name", "endpoint"),
            description=input_data.get("description", ""),
            request_model=input_data.get("request_model"),
            response_model=input_data.get("response_model"),
            auth_required=input_data.get("auth_required", True),
            permissions=input_data.get("permissions", []),
            query_params=input_data.get("query_params", []),
            path_params=input_data.get("path_params", []),
            status_code=input_data.get("status_code", 200),
            summary=input_data.get("summary", ""),
            tags=input_data.get("tags", []),
        )
        self.emit_status(f"Creating route {spec.method} {spec.path}...", "info")

        artifacts = self._generator.generate_route(spec)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys()), "route": spec.__dict__}

    def _create_model(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a database model."""
        spec = ModelSpec(
            name=input_data.get("name", "Model"),
            fields=input_data.get("fields", []),
            relationships=input_data.get("relationships", []),
            indexes=input_data.get("indexes", []),
            unique_constraints=input_data.get("unique_constraints", []),
            table_name=input_data.get("table_name"),
            description=input_data.get("description", ""),
        )
        self.emit_status(f"Creating model {spec.name}...", "info")

        artifacts = self._generator.generate_model(spec)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys()), "model": spec.__dict__}

    def _create_service(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a service."""
        spec = ServiceSpec(
            name=input_data.get("name", "Service"),
            methods=input_data.get("methods", []),
            dependencies=input_data.get("dependencies", []),
            description=input_data.get("description", ""),
        )
        self.emit_status(f"Creating service {spec.name}...", "info")

        artifacts = self._generator.generate_service(spec)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys()), "service": spec.__dict__}

    def _setup_auth(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set up authentication."""
        auth_type = input_data.get("auth_type", "jwt")
        config = input_data.get("config", {})
        self.emit_status(f"Setting up {auth_type} authentication...", "info")

        artifacts = self._generator.generate_middleware(
            name="auth",
            middleware_type="authentication",
            config={"type": auth_type, **config},
        )
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _create_middleware(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create middleware."""
        name = input_data.get("name", "custom")
        middleware_type = input_data.get("type", "custom")
        config = input_data.get("config", {})
        self.emit_status(f"Creating {middleware_type} middleware...", "info")

        artifacts = self._generator.generate_middleware(name, middleware_type, config)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _create_validator(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a validator."""
        name = input_data.get("name", "Validator")
        schema = input_data.get("schema", {})
        self.emit_status(f"Creating validator {name}...", "info")

        artifacts = self._generator.generate_validator(name, schema)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _create_migration(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a database migration."""
        name = input_data.get("name", "migration")
        operations = input_data.get("operations", [])
        self.emit_status(f"Creating migration {name}...", "info")

        artifacts = self._generator.generate_migration(name, operations)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _write_tests(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Write backend tests."""
        test_type = input_data.get("test_type", "integration")
        routes = input_data.get("routes", [])
        self.emit_status(f"Writing {test_type} tests...", "info")

        test_files = []
        for route in routes:
            spec = RouteSpec(**route)
            artifacts = self._generator.generate_test(spec, test_type)
            self._generator.persist_artifacts(artifacts, self._current_task.id)
            test_files.extend(artifacts.keys())

        self.complete_task({"files_created": test_files})
        return {"files_created": test_files}

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        packet.payload["backend_context"] = {
            "routes_created": artifacts.get("routes", []),
            "models_created": artifacts.get("models", []),
            "services_created": artifacts.get("services", []),
            "api_base_url": "/api",
        }
        return packet


def create_backend_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.PRAGMATIC,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
    project: Project = None,
) -> BackendAgent:
    """Factory function to create a BackendAgent."""
    return BackendAgent(agent_id, personality, model_config, signals, project)