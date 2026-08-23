"""
ArchitectAgent — responsible for system architecture, technical design, and high-level decisions.

The ArchitectAgent handles:
- System architecture design and documentation
- Technology stack selection and evaluation
- API design and specification
- Database schema design
- Infrastructure architecture
- Security architecture
- Performance and scalability planning
- Technical debt assessment
- Architecture decision records (ADRs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class ArchitectureDecision:
    """Architecture Decision Record (ADR)."""
    id: str
    title: str
    status: str  # proposed, accepted, deprecated, superseded
    context: str
    decision: str
    consequences: List[str] = field(default_factory=list)
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    date: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)


@dataclass
class SystemArchitecture:
    """System architecture definition."""
    name: str
    description: str
    components: List[Dict[str, Any]] = field(default_factory=list)
    interfaces: List[Dict[str, Any]] = field(default_factory=list)
    data_flow: List[Dict[str, Any]] = field(default_factory=list)
    deployment: Dict[str, Any] = field(default_factory=dict)
    security: Dict[str, Any] = field(default_factory=dict)
    scalability: Dict[str, Any] = field(default_factory=dict)
    observability: Dict[str, Any] = field(default_factory=dict)
    adrs: List[ArchitectureDecision] = field(default_factory=list)


@dataclass
class TechnologyStack:
    """Technology stack definition."""
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)
    messaging: List[str] = field(default_factory=list)
    caching: List[str] = field(default_factory=list)
    infrastructure: List[str] = field(default_factory=list)
    monitoring: List[str] = field(default_factory=list)
    ci_cd: List[str] = field(default_factory=list)
    testing: List[str] = field(default_factory=list)
    rationale: Dict[str, str] = field(default_factory=dict)


@dataclass
class APISpecification:
    """API specification."""
    name: str
    version: str
    base_path: str
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    schemas: Dict[str, Any] = field(default_factory=dict)
    authentication: Dict[str, Any] = field(default_factory=dict)
    rate_limiting: Dict[str, Any] = field(default_factory=dict)
    documentation: str = ""


@dataclass
class DatabaseSchema:
    """Database schema definition."""
    name: str
    type: str  # sql, nosql, graph, timeseries
    tables: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    migrations: List[str] = field(default_factory=list)


class ArchitectAgent(BaseAgent):
    """
    Agent specialized in system architecture and technical design.
    
    Capabilities:
    - System architecture design
    - Technology stack selection
    - API design and specification
    - Database schema design
    - Infrastructure architecture
    - Security architecture
    - Performance and scalability planning
    - Architecture decision records (ADRs)
    - Technical debt assessment
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.ANALYTICAL,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="architecture_design",
                description="Design system architecture",
                tool_names=["create_architecture", "define_components", "design_interfaces", "plan_data_flow"],
                produces_artifacts=["architecture_doc", "component_diagram", "sequence_diagram"],
            ),
            AgentCapability(
                name="technology_selection",
                description="Select and evaluate technology stack",
                tool_names=["evaluate_tech", "compare_alternatives", "create_tech_stack", "document_rationale"],
                produces_artifacts=["tech_stack", "evaluation_matrix", "adr"],
            ),
            AgentCapability(
                name="api_design",
                description="Design APIs and interfaces",
                tool_names=["design_rest_api", "design_graphql_api", "design_grpc_api", "create_openapi_spec"],
                produces_artifacts=["api_spec", "openapi_yaml", "postman_collection"],
            ),
            AgentCapability(
                name="database_design",
                description="Design database schemas",
                tool_names=["design_schema", "create_migrations", "optimize_queries", "plan_sharding"],
                produces_artifacts=["schema_sql", "er_diagram", "migration_files"],
            ),
            AgentCapability(
                name="infrastructure_architecture",
                description="Design infrastructure architecture",
                tool_names=["design_cloud_architecture", "plan_networking", "design_security_groups", "plan_scaling"],
                produces_artifacts=["infra_diagram", "terraform_modules", "k8s_manifests"],
            ),
            AgentCapability(
                name="security_architecture",
                description="Design security architecture",
                tool_names=["threat_model", "design_auth", "plan_encryption", "define_policies"],
                produces_artifacts=["threat_model", "security_policy", "auth_design"],
            ),
            AgentCapability(
                name="performance_planning",
                description="Plan for performance and scalability",
                tool_names=["capacity_planning", "load_test_design", "cache_strategy", "cdn_strategy"],
                produces_artifacts=["capacity_plan", "load_test_plan", "scaling_strategy"],
            ),
            AgentCapability(
                name="adr_management",
                description="Manage Architecture Decision Records",
                tool_names=["create_adr", "update_adr", "supersede_adr", "list_adrs"],
                produces_artifacts=["adr_documents"],
            ),
        ]

        system_prompt = """You are an Architect Agent in the emergent.sh multi-agent system.
Your role is to design system architecture, make technical decisions, and create technical specifications.

You operate with a STRATEGIC personality: forward-thinking, holistic, and principle-driven.
You produce comprehensive architecture documents, ADRs, and technical specifications.

Key responsibilities:
1. Design system architecture (components, interfaces, data flow, deployment)
2. Select and evaluate technology stacks with clear rationale
3. Design APIs (REST, GraphQL, gRPC) with proper specifications
4. Design database schemas (SQL, NoSQL, graph, time-series)
5. Design infrastructure architecture (cloud, networking, security, scaling)
6. Design security architecture (threat modeling, auth, encryption, policies)
7. Plan for performance, scalability, and observability
8. Create and maintain Architecture Decision Records (ADRs)
9. Assess and manage technical debt

Output format: Generate architecture documents, diagrams (Mermaid), specifications, and ADRs as code/markdown.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ARCHITECT,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute architect task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "create_architecture")

        if task_type == "create_architecture":
            return self._create_architecture(task.input_data)
        elif task_type == "select_tech_stack":
            return self._select_tech_stack(task.input_data)
        elif task_type == "design_api":
            return self._design_api(task.input_data)
        elif task_type == "design_database":
            return self._design_database(task.input_data)
        elif task_type == "design_infrastructure":
            return self._design_infrastructure(task.input_data)
        elif task_type == "design_security":
            return self._design_security(task.input_data)
        elif task_type == "plan_performance":
            return self._plan_performance(task.input_data)
        elif task_type == "create_adr":
            return self._create_adr(task.input_data)
        elif task_type == "assess_tech_debt":
            return self._assess_tech_debt(task.input_data)
        else:
            return self._create_architecture(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _create_architecture(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create system architecture."""
        project_id = input_data.get("project_id", "proj-001")
        requirements = input_data.get("requirements", {})
        self.emit_status(f"Creating architecture for {project_id}...", "info")

        architecture = SystemArchitecture(
            name=f"{project_id}-architecture",
            description=requirements.get("description", "System architecture"),
        )

        # Generate architecture artifacts
        artifacts = {
            "architecture_doc": self._generate_architecture_doc(architecture, requirements),
            "component_diagram": self._generate_component_diagram(architecture),
            "sequence_diagram": self._generate_sequence_diagram(architecture),
            "deployment_diagram": self._generate_deployment_diagram(architecture),
            "adrs": [],
        }

        self.complete_task({
            "architecture": architecture.__dict__,
            "artifacts": artifacts,
        })
        return {"architecture": architecture.__dict__, "artifacts": artifacts}

    def _select_tech_stack(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Select technology stack."""
        project_id = input_data.get("project_id", "proj-001")
        requirements = input_data.get("requirements", {})
        constraints = input_data.get("constraints", {})
        self.emit_status(f"Selecting tech stack for {project_id}...", "info")

        tech_stack = TechnologyStack(
            languages=requirements.get("languages", ["TypeScript", "Python"]),
            frameworks=requirements.get("frameworks", ["React", "FastAPI"]),
            databases=requirements.get("databases", ["PostgreSQL", "Redis"]),
            messaging=requirements.get("messaging", ["RabbitMQ"]),
            caching=requirements.get("caching", ["Redis"]),
            infrastructure=requirements.get("infrastructure", ["Kubernetes", "Docker"]),
            monitoring=requirements.get("monitoring", ["Prometheus", "Grafana"]),
            ci_cd=requirements.get("ci_cd", ["GitHub Actions"]),
            testing=requirements.get("testing", ["pytest", "vitest", "playwright"]),
            rationale={},
        )

        # Generate rationale for each choice
        for category, choices in tech_stack.__dict__.items():
            if isinstance(choices, list):
                for choice in choices:
                    tech_stack.rationale[choice] = f"Selected for {category} based on requirements"

        artifacts = {
            "tech_stack": tech_stack.__dict__,
            "evaluation_matrix": self._generate_evaluation_matrix(tech_stack, requirements),
            "adr": self._generate_tech_stack_adr(tech_stack),
        }

        self.complete_task(artifacts)
        return artifacts

    def _design_api(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design API specification."""
        project_id = input_data.get("project_id", "proj-001")
        api_type = input_data.get("api_type", "rest")
        requirements = input_data.get("requirements", {})
        self.emit_status(f"Designing {api_type.upper()} API for {project_id}...", "info")

        api_spec = APISpecification(
            name=f"{project_id}-api",
            version="1.0.0",
            base_path="/api/v1",
            endpoints=requirements.get("endpoints", []),
            schemas=requirements.get("schemas", {}),
            authentication=requirements.get("auth", {"type": "bearer", "scheme": "JWT"}),
            rate_limiting=requirements.get("rate_limiting", {"requests": 100, "window": "1m"}),
        )

        artifacts = {
            "api_spec": api_spec.__dict__,
            "openapi_yaml": self._generate_openapi_spec(api_spec),
            "postman_collection": self._generate_postman_collection(api_spec),
        }

        self.complete_task(artifacts)
        return artifacts

    def _design_database(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design database schema."""
        project_id = input_data.get("project_id", "proj-001")
        db_type = input_data.get("db_type", "postgresql")
        requirements = input_data.get("requirements", {})
        self.emit_status(f"Designing {db_type} database for {project_id}...", "info")

        schema = DatabaseSchema(
            name=f"{project_id}_db",
            type=db_type,
            tables=requirements.get("tables", []),
            relationships=requirements.get("relationships", []),
            indexes=requirements.get("indexes", []),
        )

        artifacts = {
            "schema": schema.__dict__,
            "sql_ddl": self._generate_sql_ddl(schema),
            "er_diagram": self._generate_er_diagram(schema),
            "migrations": self._generate_migrations(schema),
        }

        self.complete_task(artifacts)
        return artifacts

    def _design_infrastructure(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design infrastructure architecture."""
        project_id = input_data.get("project_id", "proj-001")
        cloud = input_data.get("cloud", "aws")
        requirements = input_data.get("requirements", {})
        self.emit_status(f"Designing {cloud} infrastructure for {project_id}...", "info")

        artifacts = {
            "infra_architecture": {
                "cloud": cloud,
                "regions": requirements.get("regions", ["us-east-1"]),
                "vpc": requirements.get("vpc", {}),
                "compute": requirements.get("compute", {}),
                "storage": requirements.get("storage", {}),
                "networking": requirements.get("networking", {}),
                "security": requirements.get("security", {}),
            },
            "terraform_modules": self._generate_terraform_modules(project_id, cloud, requirements),
            "k8s_manifests": self._generate_k8s_manifests(project_id, requirements),
            "network_diagram": self._generate_network_diagram(requirements),
        }

        self.complete_task(artifacts)
        return artifacts

    def _design_security(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design security architecture."""
        project_id = input_data.get("project_id", "proj-001")
        requirements = input_data.get("requirements", {})
        self.emit_status(f"Designing security architecture for {project_id}...", "info")

        artifacts = {
            "threat_model": self._generate_threat_model(project_id, requirements),
            "auth_design": self._generate_auth_design(requirements),
            "encryption_plan": self._generate_encryption_plan(requirements),
            "security_policies": self._generate_security_policies(requirements),
            "compliance_mapping": self._generate_compliance_mapping(requirements),
        }

        self.complete_task(artifacts)
        return artifacts

    def _plan_performance(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan for performance and scalability."""
        project_id = input_data.get("project_id", "proj-001")
        requirements = input_data.get("requirements", {})
        self.emit_status(f"Planning performance for {project_id}...", "info")

        artifacts = {
            "capacity_plan": self._generate_capacity_plan(requirements),
            "load_test_plan": self._generate_load_test_plan(requirements),
            "scaling_strategy": self._generate_scaling_strategy(requirements),
            "cache_strategy": self._generate_cache_strategy(requirements),
            "cdn_strategy": self._generate_cdn_strategy(requirements),
            "observability_plan": self._generate_observability_plan(requirements),
        }

        self.complete_task(artifacts)
        return artifacts

    def _create_adr(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Architecture Decision Record."""
        adr = ArchitectureDecision(
            id=input_data.get("id", f"adr-{int(__import__('time').time())}"),
            title=input_data.get("title", "Architecture Decision"),
            status=input_data.get("status", "proposed"),
            context=input_data.get("context", ""),
            decision=input_data.get("decision", ""),
            consequences=input_data.get("consequences", []),
            alternatives=input_data.get("alternatives", []),
            tags=input_data.get("tags", []),
        )

        artifacts = {
            "adr": adr.__dict__,
            "adr_markdown": self._generate_adr_markdown(adr),
        }

        self.complete_task(artifacts)
        return artifacts

    def _assess_tech_debt(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess technical debt."""
        project_id = input_data.get("project_id", "proj-001")
        codebase_path = input_data.get("codebase_path", ".")
        self.emit_status(f"Assessing technical debt for {project_id}...", "info")

        # TODO: Implement actual tech debt analysis
        artifacts = {
            "tech_debt_report": {
                "project_id": project_id,
                "overall_score": 75,
                "categories": {
                    "code_quality": {"score": 80, "issues": []},
                    "architecture": {"score": 70, "issues": []},
                    "testing": {"score": 60, "issues": []},
                    "documentation": {"score": 65, "issues": []},
                    "dependencies": {"score": 85, "issues": []},
                    "security": {"score": 90, "issues": []},
                },
                "recommendations": [],
            },
        }

        self.complete_task(artifacts)
        return artifacts

    # Helper methods for generating artifacts

    def _generate_architecture_doc(self, arch: SystemArchitecture, req: Dict) -> str:
        return f"""# {arch.name} Architecture

## Overview
{arch.description}

## Components
{self._format_components(arch.components)}

## Interfaces
{self._format_interfaces(arch.interfaces)}

## Data Flow
{self._format_data_flow(arch.data_flow)}

## Deployment
{arch.deployment}

## Security
{arch.security}

## Scalability
{arch.scalability}

## Observability
{arch.observability}
"""

    def _generate_component_diagram(self, arch: SystemArchitecture) -> str:
        mermaid = "```mermaid\ngraph TD\n"
        for comp in arch.components:
            mermaid += f"    {comp.get('id', 'comp')}[{comp.get('name', 'Component')}]\n"
        for iface in arch.interfaces:
            mermaid += f"    {iface.get('from', 'A')} -->|{iface.get('protocol', 'HTTP')}| {iface.get('to', 'B')}\n"
        mermaid += "```"
        return mermaid

    def _generate_sequence_diagram(self, arch: SystemArchitecture) -> str:
        return "```mermaid\nsequenceDiagram\n    participant Client\n    participant API\n    participant Service\n    Client->>API: Request\n    API->>Service: Process\n    Service-->>API: Response\n    API-->>Client: Response\n```"

    def _generate_deployment_diagram(self, arch: SystemArchitecture) -> str:
        return "```mermaid\ngraph TB\n    subgraph Cloud\n        LB[Load Balancer]\n        subgraph K8s\n            Pod1[Pod]\n            Pod2[Pod]\n        end\n        DB[(Database)]\n        Cache[(Cache)]\n    end\n    Client --> LB\n    LB --> Pod1\n    LB --> Pod2\n    Pod1 --> DB\n    Pod1 --> Cache\n```"

    def _generate_evaluation_matrix(self, stack: TechnologyStack, req: Dict) -> List[Dict]:
        return [
            {"criteria": "Performance", "weight": 0.3, "scores": {}},
            {"criteria": "Developer Experience", "weight": 0.25, "scores": {}},
            {"criteria": "Community Support", "weight": 0.2, "scores": {}},
            {"criteria": "Cost", "weight": 0.15, "scores": {}},
            {"criteria": "Scalability", "weight": 0.1, "scores": {}},
        ]

    def _generate_tech_stack_adr(self, stack: TechnologyStack) -> Dict:
        return {
            "id": f"adr-tech-stack-{int(__import__('time').time())}",
            "title": "Technology Stack Selection",
            "status": "accepted",
            "context": "Selecting technology stack for the project",
            "decision": f"Use {', '.join(stack.languages)} with {', '.join(stack.frameworks)}",
            "consequences": list(stack.rationale.values()),
        }

    def _generate_openapi_spec(self, api: APISpecification) -> str:
        return f"""openapi: 3.0.3
info:
  title: {api.name}
  version: {api.version}
servers:
  - url: {api.base_path}
paths: {{
}}
components:
  schemas: {{
}}
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
security:
  - bearerAuth: []"""

    def _generate_postman_collection(self, api: APISpecification) -> Dict:
        return {
            "info": {"name": api.name, "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
            "item": [],
            "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]},
        }

    def _generate_sql_ddl(self, schema: DatabaseSchema) -> str:
        ddl = f"-- Database: {schema.name}\n-- Type: {schema.type}\n\n"
        for table in schema.tables:
            ddl += f"CREATE TABLE {table.get('name', 'table')} (\n"
            for col in table.get('columns', []):
                ddl += f"    {col.get('name', 'id')} {col.get('type', 'UUID')} {col.get('constraints', '')},\n"
            ddl = ddl.rstrip(",\n") + "\n);\n\n"
        return ddl

    def _generate_er_diagram(self, schema: DatabaseSchema) -> str:
        mermaid = "```mermaid\nerDiagram\n"
        for table in schema.tables:
            mermaid += f"    {table.get('name', 'TABLE')} {{\n"
            for col in table.get('columns', []):
                mermaid += f"        {col.get('type', 'string')} {col.get('name', 'id')}\n"
            mermaid += "    }\n"
        for rel in schema.relationships:
            mermaid += f"    {rel.get('from', 'A')} ||--o{{{{ {rel.get('to', 'B')}}}}} : {rel.get('type', 'has')}\n"
        mermaid += "```"
        return mermaid

    def _generate_migrations(self, schema: DatabaseSchema) -> List[str]:
        return [f"-- Migration for {schema.name}", self._generate_sql_ddl(schema)]

    def _generate_terraform_modules(self, project_id: str, cloud: str, req: Dict) -> Dict[str, str]:
        return {
            "main.tf": f"# {project_id} Terraform Configuration\nprovider \"{cloud}\" {{\n  region = var.region\n}}\n",
            "variables.tf": "variable \"region\" { default = \"us-east-1\" }",
            "outputs.tf": "",
        }

    def _generate_k8s_manifests(self, project_id: str, req: Dict) -> Dict[str, str]:
        return {
            "deployment.yaml": f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {project_id}\nspec:\n  replicas: 3\n  selector:\n    matchLabels:\n      app: {project_id}\n  template:\n    metadata:\n      labels:\n        app: {project_id}\n    spec:\n      containers:\n      - name: {project_id}\n        image: {project_id}:latest\n        ports:\n        - containerPort: 8080\n",
            "service.yaml": f"apiVersion: v1\nkind: Service\nmetadata:\n  name: {project_id}\nspec:\n  selector:\n    app: {project_id}\n  ports:\n  - port: 80\n    targetPort: 8080\n  type: ClusterIP\n",
        }

    def _generate_network_diagram(self, req: Dict) -> str:
        return "```mermaid\ngraph LR\n    Internet --> WAF[WAF]\n    WAF --> ALB[ALB]\n    ALB --> Subnet1[Private Subnet 1]\n    ALB --> Subnet2[Private Subnet 2]\n    Subnet1 --> App1[App Pods]\n    Subnet2 --> App2[App Pods]\n    App1 --> DB[(RDS)]\n    App2 --> DB\n    App1 --> Cache[(ElastiCache)]\n    App2 --> Cache\n```"

    def _generate_threat_model(self, project_id: str, req: Dict) -> Dict:
        return {
            "project_id": project_id,
            "threats": [
                {"id": "T1", "category": "Spoofing", "description": "Identity spoofing", "mitigation": "MFA, JWT"},
                {"id": "T2", "category": "Tampering", "description": "Data tampering", "mitigation": "Signatures, HTTPS"},
                {"id": "T3", "category": "Repudiation", "description": "Action repudiation", "mitigation": "Audit logs"},
                {"id": "T4", "category": "Information Disclosure", "description": "Data leakage", "mitigation": "Encryption"},
                {"id": "T5", "category": "Denial of Service", "description": "Service disruption", "mitigation": "Rate limiting, WAF"},
                {"id": "T6", "category": "Elevation of Privilege", "description": "Privilege escalation", "mitigation": "RBAC, least privilege"},
            ],
        }

    def _generate_auth_design(self, req: Dict) -> Dict:
        return {
            "authentication": req.get("auth", {"type": "OAuth2/OIDC", "provider": "Auth0"}),
            "authorization": {"model": "RBAC", "roles": ["admin", "user", "viewer"]},
            "session_management": {"type": "JWT", "access_token_ttl": "15m", "refresh_token_ttl": "7d"},
            "mfa": {"required": True, "methods": ["TOTP", "SMS", "Email"]},
        }

    def _generate_encryption_plan(self, req: Dict) -> Dict:
        return {
            "at_rest": {"algorithm": "AES-256", "key_management": "AWS KMS"},
            "in_transit": {"protocol": "TLS 1.3", "certificate_management": "ACM"},
            "application_level": {"pii_encryption": "AES-256-GCM", "key_rotation": "90 days"},
        }

    def _generate_security_policies(self, req: Dict) -> List[Dict]:
        return [
            {"name": "Password Policy", "rules": ["min 12 chars", "complexity", "rotation 90 days"]},
            {"name": "Access Control", "rules": ["least privilege", "regular review", "MFA required"]},
            {"name": "Data Protection", "rules": ["encryption at rest", "encryption in transit", "PII handling"]},
            {"name": "Incident Response", "rules": ["detection", "containment", "recovery", "postmortem"]},
        ]

    def _generate_compliance_mapping(self, req: Dict) -> Dict:
        return {
            "SOC2": {"status": "planned", "controls": []},
            "GDPR": {"status": "planned", "controls": []},
            "HIPAA": {"status": "not_applicable", "controls": []},
            "PCI-DSS": {"status": "not_applicable", "controls": []},
        }

    def _generate_capacity_plan(self, req: Dict) -> Dict:
        return {
            "expected_rps": req.get("rps", 1000),
            "peak_rps": req.get("peak_rps", 5000),
            "storage_gb": req.get("storage_gb", 100),
            "storage_growth_gb_month": req.get("storage_growth", 10),
            "compute": {"cpu_cores": 16, "memory_gb": 64},
            "scaling_triggers": {"cpu": "70%", "memory": "80%", "rps": "80% of capacity"},
        }

    def _generate_load_test_plan(self, req: Dict) -> Dict:
        return {
            "tool": "k6",
            "scenarios": [
                {"name": "baseline", "vus": 10, "duration": "5m"},
                {"name": "load", "vus": 100, "duration": "10m"},
                {"name": "stress", "vus": 500, "duration": "5m"},
                {"name": "spike", "vus": 1000, "duration": "1m"},
                {"name": "soak", "vus": 50, "duration": "4h"},
            ],
            "thresholds": {"http_req_duration": "p(95)<500", "http_req_failed": "rate<0.01"},
        }

    def _generate_scaling_strategy(self, req: Dict) -> Dict:
        return {
            "horizontal": {"enabled": True, "min_replicas": 3, "max_replicas": 100, "metric": "cpu"},
            "vertical": {"enabled": False},
            "cluster": {"enabled": True, "node_groups": ["general", "compute", "memory"]},
            "database": {"read_replicas": 2, "sharding": "planned"},
            "cache": {"cluster_mode": True, "shards": 4},
        }

    def _generate_cache_strategy(self, req: Dict) -> Dict:
        return {
            "layers": [
                {"name": "CDN", "ttl": "1h", "scope": "static assets"},
                {"name": "API Gateway", "ttl": "5m", "scope": "GET responses"},
                {"name": "Application", "ttl": "1h", "scope": "computed data"},
                {"name": "Database", "ttl": "30m", "scope": "query results"},
            ],
            "invalidation": ["event-driven", "TTL-based", "manual"],
        }

    def _generate_cdn_strategy(self, req: Dict) -> Dict:
        return {
            "provider": "CloudFront",
            "distributions": [
                {"origin": "S3", "path": "/static/*", "ttl": "1y"},
                {"origin": "ALB", "path": "/api/*", "ttl": "0", "cache_behavior": "no-cache"},
            ],
            "edge_functions": ["auth@edge", "redirects", "headers"],
        }

    def _generate_observability_plan(self, req: Dict) -> Dict:
        return {
            "metrics": {"provider": "Prometheus", "retention": "30d", "key_metrics": ["latency", "errors", "traffic", "saturation"]},
            "logs": {"provider": "Loki", "retention": "14d", "structured": True},
            "traces": {"provider": "Tempo", "sampling": "10%", "retention": "7d"},
            "alerts": {"provider": "Alertmanager", "channels": ["Slack", "PagerDuty", "Email"]},
            "dashboards": {"provider": "Grafana", "templates": ["RED", "USE", "Business"]},
        }

    def _generate_adr_markdown(self, adr: ArchitectureDecision) -> str:
        return f"""# {adr.id}: {adr.title}

**Status**: {adr.status}
**Date**: {adr.date.strftime('%Y-%m-%d')}
**Tags**: {', '.join(adr.tags)}

## Context
{adr.context}

## Decision
{adr.decision}

## Consequences
{chr(10).join(f'- {c}' for c in adr.consequences)}

## Alternatives
{chr(10).join(f'- {a.get("name", "Alternative")}: {a.get("description", "")}' for a in adr.alternatives)}
"""

    def _format_components(self, components: List[Dict]) -> str:
        return "\n".join(f"- **{c.get('name', 'Component')}**: {c.get('description', '')}" for c in components)

    def _format_interfaces(self, interfaces: List[Dict]) -> str:
        return "\n".join(f"- **{i.get('name', 'Interface')}**: {i.get('protocol', 'HTTP')} {i.get('from', '')} -> {i.get('to', '')}" for i in interfaces)

    def _format_data_flow(self, flows: List[Dict]) -> str:
        return "\n".join(f"- {f.get('from', '')} -> {f.get('to', '')}: {f.get('data', '')}" for f in flows)

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        packet.payload["architect_context"] = {
            "architectures": artifacts.get("architecture_doc", []),
            "tech_stacks": artifacts.get("tech_stack", []),
            "api_specs": artifacts.get("api_spec", []),
            "database_schemas": artifacts.get("schema", []),
            "adrs": artifacts.get("adrs", []),
        }
        return packet


def create_architect_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.ANALYTICAL,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> ArchitectAgent:
    """Factory function to create an ArchitectAgent."""
    return ArchitectAgent(agent_id, personality, model_config, signals)