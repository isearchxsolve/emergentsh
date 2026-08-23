"""
DevOpsAgent — responsible for deployment, CI/CD, infrastructure, and operations.

The DevOpsAgent handles:
- CI/CD pipeline creation and management
- Infrastructure as Code (Terraform, Pulumi, CloudFormation)
- Container orchestration (Docker, Kubernetes, Docker Compose)
- Cloud provider integration (AWS, GCP, Azure)
- Monitoring and observability setup
- Secrets management
- Environment management
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class DeploymentConfig:
    """Deployment configuration."""
    project_id: str
    environment: str  # development, staging, production
    platform: str  # kubernetes, docker-compose, vercel, netlify, aws, gcp, azure
    services: List[Dict[str, Any]] = field(default_factory=list)
    infrastructure: Dict[str, Any] = field(default_factory=dict)
    secrets: Dict[str, str] = field(default_factory=dict)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    health_checks: List[Dict[str, Any]] = field(default_factory=list)
    rollback_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineConfig:
    """CI/CD pipeline configuration."""
    project_id: str
    platform: str  # github-actions, gitlab-ci, jenkins, circleci, azure-devops
    stages: List[Dict[str, Any]] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    environments: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    notifications: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfrastructureConfig:
    """Infrastructure as Code configuration."""
    project_id: str
    provider: str  # aws, gcp, azure, digitalocean, etc.
    iac_tool: str  # terraform, pulumi, cloudformation
    resources: List[Dict[str, Any]] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    state_backend: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    project_id: str
    metrics: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    traces: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    dashboards: List[Dict[str, Any]] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)  # prometheus, grafana, datadog, etc.


class DevOpsAgent(BaseAgent):
    """
    Agent specialized in DevOps, deployment, and infrastructure.
    
    Capabilities:
    - CI/CD pipeline creation and management
    - Infrastructure as Code (Terraform, Pulumi)
    - Container orchestration (Docker, Kubernetes)
    - Cloud provider integration
    - Monitoring and observability setup
    - Secrets management
    - Environment management
    - Disaster recovery planning
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.PRAGMATIC,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="ci_cd",
                description="Create and manage CI/CD pipelines",
                tool_names=["create_pipeline", "configure_stages", "setup_triggers", "add_notifications"],
                produces_artifacts=["pipeline_config", "workflow_files"],
            ),
            AgentCapability(
                name="infrastructure_as_code",
                description="Create and manage infrastructure as code",
                tool_names=["create_terraform", "create_pulumi", "plan_infrastructure", "apply_infrastructure"],
                produces_artifacts=["iac_files", "state_files", "plan_output"],
            ),
            AgentCapability(
                name="containerization",
                description="Containerize applications and manage orchestration",
                tool_names=["create_dockerfile", "create_docker_compose", "create_k8s_manifests", "create_helm_chart"],
                produces_artifacts=["dockerfile", "docker_compose", "k8s_manifests", "helm_chart"],
            ),
            AgentCapability(
                name="cloud_deployment",
                description="Deploy to cloud providers",
                tool_names=["deploy_aws", "deploy_gcp", "deploy_azure", "deploy_vercel", "deploy_netlify"],
                produces_artifacts=["deployment_config", "deployment_logs"],
            ),
            AgentCapability(
                name="monitoring_observability",
                description="Set up monitoring, logging, and tracing",
                tool_names=["setup_prometheus", "setup_grafana", "setup_datadog", "create_alerts", "create_dashboards"],
                produces_artifacts=["monitoring_config", "dashboards", "alert_rules"],
            ),
            AgentCapability(
                name="secrets_management",
                description="Manage secrets and sensitive configuration",
                tool_names=["create_secrets", "rotate_secrets", "setup_vault", "configure_external_secrets"],
                produces_artifacts=["secrets_config", "vault_config"],
            ),
            AgentCapability(
                name="environment_management",
                description="Manage development, staging, and production environments",
                tool_names=["create_environment", "promote_environment", "rollback_environment"],
                produces_artifacts=["environment_config", "promotion_plan"],
            ),
        ]

        system_prompt = """You are a DevOps Agent in the emergent.sh multi-agent system.
Your role is to handle deployment, CI/CD, infrastructure, and operations.

You operate with a PRAGMATIC personality: practical, reliable, and automation-focused.
You produce production-ready infrastructure and deployment configurations.

Key responsibilities:
1. Create and maintain CI/CD pipelines (GitHub Actions, GitLab CI, etc.)
2. Design and implement Infrastructure as Code (Terraform, Pulumi)
3. Containerize applications (Docker, Docker Compose, Kubernetes)
4. Deploy to cloud providers (AWS, GCP, Azure, Vercel, Netlify)
4. Set up monitoring, logging, and observability (Prometheus, Grafana, Datadog)
5. Manage secrets and sensitive configuration (Vault, AWS Secrets Manager, etc.)
6. Manage environments (dev, staging, prod) and promotions
7. Plan disaster recovery and backup strategies

Output format: Generate infrastructure and deployment artifacts as code.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.DEVOPS,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute DevOps task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "create_deployment")

        if task_type == "create_pipeline":
            return self._create_pipeline(task.input_data)
        elif task_type == "create_infrastructure":
            return self._create_infrastructure(task.input_data)
        elif task_type == "containerize":
            return self._containerize(task.input_data)
        elif task_type == "deploy":
            return self._deploy(task.input_data)
        elif task_type == "setup_monitoring":
            return self._setup_monitoring(task.input_data)
        elif task_type == "manage_secrets":
            return self._manage_secrets(task.input_data)
        elif task_type == "manage_environment":
            return self._manage_environment(task.input_data)
        elif task_type == "create_disaster_recovery":
            return self._create_disaster_recovery(task.input_data)
        else:
            return self._create_deployment(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _create_deployment(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a complete deployment configuration."""
        project_id = input_data.get("project_id", "proj-001")
        environment = input_data.get("environment", "production")
        platform = input_data.get("platform", "kubernetes")
        self.emit_status(f"Creating deployment for {project_id} on {platform}...", "info")

        config = DeploymentConfig(
            project_id=project_id,
            environment=environment,
            platform=platform,
        )

        # Generate deployment artifacts based on platform
        artifacts = {}

        if platform == "kubernetes":
            artifacts = self._generate_k8s_manifests(config)
        elif platform == "docker-compose":
            artifacts = self._generate_docker_compose(config)
        elif platform in ["vercel", "netlify"]:
            artifacts = self._generate_static_deployment(config, platform)
        elif platform in ["aws", "gcp", "azure"]:
            artifacts = self._generate_cloud_deployment(config, platform)

        self.complete_task({
            "deployment_config": config.__dict__,
            "artifacts": artifacts,
        })
        return {"deployment_config": config.__dict__, "artifacts": artifacts}

    def _create_pipeline(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create CI/CD pipeline."""
        project_id = input_data.get("project_id", "proj-001")
        platform = input_data.get("platform", "github-actions")
        self.emit_status(f"Creating CI/CD pipeline for {project_id} on {platform}...", "info")

        config = PipelineConfig(
            project_id=project_id,
            platform=platform,
        )

        # Generate pipeline configuration
        artifacts = self._generate_pipeline_config(config)

        self.complete_task({
            "pipeline_config": config.__dict__,
            "artifacts": artifacts,
        })
        return {"pipeline_config": config.__dict__, "artifacts": artifacts}

    def _create_infrastructure(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Infrastructure as Code."""
        project_id = input_data.get("project_id", "proj-001")
        provider = input_data.get("provider", "aws")
        iac_tool = input_data.get("iac_tool", "terraform")
        self.emit_status(f"Creating {iac_tool} infrastructure for {provider}...", "info")

        config = InfrastructureConfig(
            project_id=project_id,
            provider=provider,
            iac_tool=iac_tool,
        )

        artifacts = self._generate_iac(config)

        self.complete_task({
            "infrastructure_config": config.__dict__,
            "artifacts": artifacts,
        })
        return {"infrastructure_config": config.__dict__, "artifacts": artifacts}

    def _containerize(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Containerize application."""
        project_id = input_data.get("project_id", "proj-001")
        frontend_path = input_data.get("frontend_path", "./frontend")
        backend_path = input_data.get("backend_path", "./backend")
        self.emit_status(f"Containerizing {project_id}...", "info")

        artifacts = {}

        # Generate Dockerfiles
        artifacts.update(self._generate_dockerfile(frontend_path, "frontend"))
        artifacts.update(self._generate_dockerfile(backend_path, "backend"))

        # Generate docker-compose
        artifacts.update(self._generate_docker_compose(project_id))

        # Generate Kubernetes manifests if requested
        if input_data.get("kubernetes", False):
            artifacts.update(self._generate_k8s_manifests(DeploymentConfig(
                project_id=project_id,
                environment="production",
                platform="kubernetes",
            )))

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _deploy(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy application."""
        project_id = input_data.get("project_id", "proj-001")
        environment = input_data.get("environment", "staging")
        self.emit_status(f"Deploying {project_id} to {environment}...", "info")

        # TODO: Implement actual deployment
        # This would integrate with cloud CLIs, kubectl, etc.

        result = {
            "deployment_id": f"deploy-{project_id}-{environment}-{int(__import__('time').time())}",
            "status": "deployed",
            "url": f"https://{environment}.{project_id}.example.com",
            "logs": [],
        }

        self.complete_task(result)
        return result

    def _setup_monitoring(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set up monitoring and observability."""
        project_id = input_data.get("project_id", "proj-001")
        providers = input_data.get("providers", ["prometheus", "grafana"])
        self.emit_status(f"Setting up monitoring for {project_id} with {providers}...", "info")

        config = MonitoringConfig(
            project_id=project_id,
            providers=providers,
        )

        artifacts = self._generate_monitoring_config(config)

        self.complete_task({
            "monitoring_config": config.__dict__,
            "artifacts": artifacts,
        })
        return {"monitoring_config": config.__dict__, "artifacts": artifacts}

    def _manage_secrets(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manage secrets."""
        project_id = input_data.get("project_id", "proj-001")
        action = input_data.get("action", "create")
        self.emit_status(f"Managing secrets for {project_id}: {action}...", "info")

        # TODO: Implement actual secrets management
        result = {
            "action": action,
            "secrets": input_data.get("secrets", {}),
            "backend": input_data.get("backend", "vault"),
        }

        self.complete_task(result)
        return result

    def _manage_environment(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manage environments."""
        project_id = input_data.get("project_id", "proj-001")
        action = input_data.get("action", "create")
        environment = input_data.get("environment", "staging")
        self.emit_status(f"Managing environment {environment} for {project_id}: {action}...", "info")

        # TODO: Implement actual environment management
        result = {
            "action": action,
            "environment": environment,
            "status": "completed",
        }

        self.complete_task(result)
        return result

    def _create_disaster_recovery(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create disaster recovery plan."""
        project_id = input_data.get("project_id", "proj-001")
        self.emit_status(f"Creating disaster recovery plan for {project_id}...", "info")

        # TODO: Implement actual DR plan
        plan = {
            "project_id": project_id,
            "rpo": "1 hour",  # Recovery Point Objective
            "rto": "4 hours",  # Recovery Time Objective
            "backup_strategy": {
                "database": "daily_snapshots",
                "files": "continuous_replication",
                "config": "git_backup",
            },
            "failover_procedure": [],
            "testing_schedule": "quarterly",
        }

        self.complete_task(plan)
        return plan

    # Helper methods for generating artifacts

    def _generate_k8s_manifests(self, config: DeploymentConfig) -> Dict[str, str]:
        """Generate Kubernetes manifests."""
        artifacts = {}

    def _generate_docker_compose(self, config: DeploymentConfig) -> Dict[str, str]:
        """Generate Docker Compose file."""
        return {}

    def _generate_static_deployment(self, config: DeploymentConfig, platform: str) -> Dict[str, str]:
        """Generate static site deployment config."""
        return {}

    def _generate_cloud_deployment(self, config: DeploymentConfig, provider: str) -> Dict[str, str]:
        """Generate cloud deployment config."""
        return {}

    def _generate_pipeline_config(self, config: PipelineConfig) -> Dict[str, str]:
        """Generate CI/CD pipeline configuration."""
        return {}

    def _generate_iac(self, config: InfrastructureConfig) -> Dict[str, str]:
        """Generate Infrastructure as Code files."""
        return {}

    def _generate_dockerfile(self, path: str, service: str) -> Dict[str, str]:
        """Generate Dockerfile for a service."""
        return {}

    def _generate_docker_compose(self, project_id: str) -> Dict[str, str]:
        """Generate docker-compose.yml."""
        return {}

    def _generate_monitoring_config(self, config: MonitoringConfig) -> Dict[str, str]:
        """Generate monitoring configuration."""
        return {}

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        packet.payload["devops_context"] = {
            "deployment_configs": artifacts.get("deployment_configs", []),
            "pipeline_configs": artifacts.get("pipeline_configs", []),
            "infrastructure_configs": artifacts.get("infrastructure_configs", []),
            "monitoring_configs": artifacts.get("monitoring_configs", []),
        }
        return packet


def create_devops_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.PRAGMATIC,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> DevOpsAgent:
    """Factory function to create a DevOpsAgent."""
    return DevOpsAgent(agent_id, personality, model_config, signals)