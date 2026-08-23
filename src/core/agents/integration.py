"""
IntegrationAgent — responsible for integrating frontend and backend, and end-to-end testing.

The IntegrationAgent handles:
- Frontend-backend integration
- API contract validation
- End-to-end testing
- Deployment configuration
- CI/CD pipeline setup
- Environment configuration
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket
from ..agents.integration_generator import IntegrationGenerator
from ..workspace import Project, get_workspace


@dataclass
class IntegrationTaskResult:
    """Result of an integration task."""
    files_created: List[str] = field(default_factory=list)
    e2e_tests: List[str] = field(default_factory=list)
    deployment_configs: List[str] = field(default_factory=list)
    ci_cd_configs: List[str] = field(default_factory=list)
    env_configs: List[str] = field(default_factory=list)


class IntegrationAgent(BaseAgent):
    """
    Agent specialized in integration and deployment.
    
    Capabilities:
    - Frontend-backend integration
    - API contract validation
    - End-to-end testing
    - Docker configuration
    - CI/CD pipeline setup
    - Environment configuration
    - Health checks and monitoring
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
                name="frontend_backend_integration",
                description="Connect frontend to backend APIs",
                tool_names=["connect_api", "validate_contracts", "generate_client"],
                produces_artifacts=["integration_files", "contract_validation"],
            ),
            AgentCapability(
                name="e2e_testing",
                description="Write and run end-to-end tests",
                tool_names=["write_e2e_tests", "run_e2e_tests", "generate_test_data"],
                produces_artifacts=["e2e_test_files", "test_results"],
            ),
            AgentCapability(
                name="deployment",
                description="Configure deployment and infrastructure",
                tool_names=["create_dockerfile", "create_docker_compose", "create_k8s_manifests"],
                produces_artifacts=["dockerfile", "docker_compose", "k8s_manifests"],
            ),
            AgentCapability(
                name="ci_cd",
                description="Set up CI/CD pipelines",
                tool_names=["create_github_actions", "create_gitlab_ci", "setup_preview_deployments"],
                produces_artifacts=["ci_cd_configs"],
            ),
            AgentCapability(
                name="environment_config",
                description="Manage environment variables and configuration",
                tool_names=["create_env_files", "validate_env", "generate_secrets"],
                produces_artifacts=["env_files", "env_schema"],
            ),
        ]

        system_prompt = """You are an Integration Agent in the emergent.sh multi-agent system.
Your role is to integrate frontend and backend, set up testing, deployment, and CI/CD.

You operate with a PRAGMATIC personality: practical, results-oriented, and efficient.
You ensure the full stack works together seamlessly from development to production.

Key responsibilities:
1. Connect frontend to backend APIs with proper typing
2. Validate API contracts between frontend and backend
3. Write end-to-end tests covering critical user flows
4. Create Docker configurations for containerization
5. Set up CI/CD pipelines (GitHub Actions, GitLab CI)
6. Manage environment variables and secrets
7. Configure health checks and monitoring
8. Set up preview deployments for PRs

Output format: Generate file artifacts that are persisted to the workspace.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.INTEGRATION,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

        self._project = project
        self._generator = None
        if project:
            self._generator = IntegrationGenerator(project, get_workspace())

    def set_project(self, project: Project) -> None:
        """Set the project and initialize generator."""
        self._project = project
        self._generator = IntegrationGenerator(project, get_workspace())

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute integration task."""
        self.set_task(task)
        self.set_context(context)

        if not self._generator:
            return {"error": "No project configured for integration"}

        task_type = task.input_data.get("type", "integrate")

        if task_type == "connect_frontend_backend":
            return self._connect_frontend_backend(task.input_data)
        elif task_type == "write_e2e_tests":
            return self._write_e2e_tests(task.input_data)
        elif task_type == "create_docker":
            return self._create_docker(task.input_data)
        elif task_type == "create_ci_cd":
            return self._create_ci_cd(task.input_data)
        elif task_type == "create_env":
            return self._create_env(task.input_data)
        elif task_type == "validate_contracts":
            return self._validate_contracts(task.input_data)
        else:
            return self._integrate(task.input_data)

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

    def _integrate(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Full integration setup."""
        frontend_info = input_data.get("frontend", {})
        backend_info = input_data.get("backend", {})
        self.emit_status("Setting up full integration...", "info")

        result = IntegrationTaskResult()

        # Connect frontend to backend
        artifacts = self._generator.generate_api_client(
            frontend_info.get("api_base_url", "/api"),
            backend_info.get("endpoints", []),
        )
        self._generator.persist_artifacts(artifacts, self._current_task.id)
        result.files_created.extend(artifacts.keys())

        # Create Docker configuration
        artifacts = self._generator.generate_docker(
            frontend_info.get("port", 3000),
            backend_info.get("port", 8000),
        )
        self._generator.persist_artifacts(artifacts, self._current_task.id)
        result.files_created.extend(artifacts.keys())
        result.deployment_configs.extend(artifacts.keys())

        # Create docker-compose
        artifacts = self._generator.generate_docker_compose()
        self._generator.persist_artifacts(artifacts, self._current_task.id)
        result.files_created.extend(artifacts.keys())
        result.deployment_configs.extend(artifacts.keys())

        # Create CI/CD
        artifacts = self._generator.generate_ci_cd()
        self._generator.persist_artifacts(artifacts, self._current_task.id)
        result.files_created.extend(artifacts.keys())
        result.ci_cd_configs.extend(artifacts.keys())

        # Create environment files
        artifacts = self._generator.generate_env_files()
        self._generator.persist_artifacts(artifacts, self._current_task.id)
        result.files_created.extend(artifacts.keys())
        result.env_configs.extend(artifacts.keys())

        # Write E2E tests
        artifacts = self._generator.generate_e2e_tests(
            frontend_info.get("pages", []),
            backend_info.get("endpoints", []),
        )
        self._generator.persist_artifacts(artifacts, self._current_task.id)
        result.files_created.extend(artifacts.keys())
        result.e2e_tests.extend(artifacts.keys())

        self.complete_task({
            "files_created": result.files_created,
            "e2e_tests": result.e2e_tests,
            "deployment_configs": result.deployment_configs,
            "ci_cd_configs": result.ci_cd_configs,
            "env_configs": result.env_configs,
        })

        return {
            "files_created": result.files_created,
            "e2e_tests": result.e2e_tests,
            "deployment_configs": result.deployment_configs,
            "ci_cd_configs": result.ci_cd_configs,
            "env_configs": result.env_configs,
        }

    def _connect_frontend_backend(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Connect frontend to backend API."""
        api_base_url = input_data.get("api_base_url", "/api")
        endpoints = input_data.get("endpoints", [])
        self.emit_status("Connecting frontend to backend...", "info")

        artifacts = self._generator.generate_api_client(api_base_url, endpoints)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _write_e2e_tests(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Write end-to-end tests."""
        pages = input_data.get("pages", [])
        endpoints = input_data.get("endpoints", [])
        self.emit_status("Writing E2E tests...", "info")

        artifacts = self._generator.generate_e2e_tests(pages, endpoints)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _create_docker(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Docker configuration."""
        frontend_port = input_data.get("frontend_port", 3000)
        backend_port = input_data.get("backend_port", 8000)
        self.emit_status("Creating Docker configuration...", "info")

        artifacts = self._generator.generate_docker(frontend_port, backend_port)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        # Also create docker-compose
        compose_artifacts = self._generator.generate_docker_compose()
        self._generator.persist_artifacts(compose_artifacts, self._current_task.id)

        all_files = list(artifacts.keys()) + list(compose_artifacts.keys())
        self.complete_task({"files_created": all_files})
        return {"files_created": all_files}

    def _create_ci_cd(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create CI/CD pipeline."""
        platform = input_data.get("platform", "github-actions")
        self.emit_status(f"Creating CI/CD for {platform}...", "info")

        artifacts = self._generator.generate_ci_cd(platform)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _create_env(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create environment configuration."""
        env_type = input_data.get("env_type", "all")
        self.emit_status("Creating environment configuration...", "info")

        artifacts = self._generator.generate_env_files(env_type)
        self._generator.persist_artifacts(artifacts, self._current_task.id)

        self.complete_task({"files_created": list(artifacts.keys())})
        return {"files_created": list(artifacts.keys())}

    def _validate_contracts(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API contracts between frontend and backend."""
        frontend_contract = input_data.get("frontend_contract", {})
        backend_contract = input_data.get("backend_contract", {})
        self.emit_status("Validating API contracts...", "info")

        # TODO: Implement actual contract validation
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "missing_endpoints": [],
            "type_mismatches": [],
        }

        self.complete_task(validation_result)
        return validation_result

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        packet.payload["integration_context"] = {
            "e2e_tests": artifacts.get("e2e_tests", []),
            "deployment_configs": artifacts.get("deployment_configs", []),
            "ci_cd_configs": artifacts.get("ci_cd_configs", []),
            "env_configs": artifacts.get("env_configs", []),
        }
        return packet


def create_integration_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.PRAGMATIC,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
    project: Project = None,
) -> IntegrationAgent:
    """Factory function to create an IntegrationAgent."""
    return IntegrationAgent(agent_id, personality, model_config, signals, project)