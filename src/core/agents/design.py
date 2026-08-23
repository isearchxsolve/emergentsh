"""
DesignAgent — responsible for system design, architecture decisions, and UI/UX design.

The DesignAgent creates technical specifications, architecture diagrams,
database schemas, API contracts, and UI/UX designs.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class ArchitectureSpec:
    """System architecture specification."""
    project_id: str
    overview: str
    components: List[Dict[str, Any]] = field(default_factory=list)
    data_flow: List[Dict[str, Any]] = field(default_factory=list)
    technology_choices: Dict[str, str] = field(default_factory=dict)
    infrastructure: Dict[str, Any] = field(default_factory=dict)
    security_considerations: List[str] = field(default_factory=list)
    scalability_plan: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DatabaseSchema:
    """Database schema design."""
    project_id: str
    tables: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    migrations: List[str] = field(default_factory=list)


@dataclass
class APIContract:
    """API contract specification (OpenAPI/Swagger)."""
    project_id: str
    version: str = "1.0.0"
    base_path: str = "/api"
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    schemas: Dict[str, Any] = field(default_factory=dict)
    security_schemes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UIDesign:
    """UI/UX design specification."""
    project_id: str
    pages: List[Dict[str, Any]] = field(default_factory=list)
    components: List[Dict[str, Any]] = field(default_factory=list)
    design_system: Dict[str, Any] = field(default_factory=dict)
    user_flows: List[Dict[str, Any]] = field(default_factory=list)
    wireframes: Dict[str, str] = field(default_factory=dict)  # page_name -> description/svg
    accessibility_notes: List[str] = field(default_factory=list)


class DesignAgent(BaseAgent):
    """
    Agent specialized in system design, architecture, and UI/UX.
    
    Capabilities:
    - System architecture design
    - Database schema design
    - API contract design (OpenAPI)
    - UI/UX design and user flows
    - Design system creation
    - Technical specification writing
    - Architecture decision records (ADRs)
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.CREATIVE,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="architecture_design",
                description="Design system architecture and component interactions",
                tool_names=["design_architecture", "create_adr", "evaluate_tech_stack"],
                produces_artifacts=["architecture_spec", "adr", "tech_evaluation"],
            ),
            AgentCapability(
                name="database_design",
                description="Design database schemas and relationships",
                tool_names=["design_schema", "create_migrations", "optimize_queries"],
                produces_artifacts=["database_schema", "migration_files"],
            ),
            AgentCapability(
                name="api_design",
                description="Design REST/GraphQL API contracts",
                tool_names=["design_api", "generate_openapi", "version_api"],
                produces_artifacts=["api_contract", "openapi_spec"],
            ),
            AgentCapability(
                name="ui_ux_design",
                description="Design user interfaces and experiences",
                tool_names=["design_ui", "create_user_flows", "design_system"],
                produces_artifacts=["ui_design", "design_system", "wireframes"],
            ),
            AgentCapability(
                name="technical_specification",
                description="Write detailed technical specifications",
                tool_names=["write_spec", "create_sequence_diagram", "document_decisions"],
                produces_artifacts=["technical_spec", "sequence_diagrams", "adrs"],
            ),
        ]

        system_prompt = """You are a Design Agent in the emergent.sh multi-agent system.
Your role is to create system architectures, database designs, API contracts,
and UI/UX designs based on requirements and planning artifacts.

You operate with a CREATIVE personality: innovative, exploratory, and design-focused.
You produce comprehensive design specifications that guide implementation.

Key responsibilities:
1. Design system architecture with clear component boundaries
2. Create database schemas optimized for the use case
3. Design RESTful/GraphQL APIs with proper contracts
4. Create UI/UX designs with user flows and accessibility
5. Establish design systems for consistency
6. Document architecture decisions (ADRs)
7. Evaluate technology choices against requirements

Output format: Always produce structured JSON artifacts that can be consumed by implementation agents.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.DESIGN,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute design task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "design_system")

        if task_type == "design_architecture":
            return self._design_architecture(task.input_data)
        elif task_type == "design_database":
            return self._design_database(task.input_data)
        elif task_type == "design_api":
            return self._design_api(task.input_data)
        elif task_type == "design_ui":
            return self._design_ui(task.input_data)
        elif task_type == "create_design_system":
            return self._create_design_system(task.input_data)
        elif task_type == "write_technical_spec":
            return self._write_technical_spec(task.input_data)
        else:
            return self._design_system(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _design_architecture(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design system architecture."""
        requirements = input_data.get("requirements", {})
        tech_stack = input_data.get("tech_stack", {})
        self.emit_status("Designing system architecture...", "info")

        # TODO: Implement actual LLM-based architecture design
        arch = ArchitectureSpec(
            project_id=input_data.get("project_id", "proj-001"),
            overview="System architecture overview",
            technology_choices=tech_stack,
        )

        return {
            "architecture_spec": {
                "project_id": arch.project_id,
                "overview": arch.overview,
                "components": arch.components,
                "data_flow": arch.data_flow,
                "technology_choices": arch.technology_choices,
                "infrastructure": arch.infrastructure,
                "security_considerations": arch.security_considerations,
                "scalability_plan": arch.scalability_plan,
            },
            "adrs": [],
        }

    def _design_database(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design database schema."""
        requirements = input_data.get("requirements", {})
        self.emit_status("Designing database schema...", "info")

        schema = DatabaseSchema(
            project_id=input_data.get("project_id", "proj-001"),
        )

        return {
            "database_schema": {
                "project_id": schema.project_id,
                "tables": schema.tables,
                "relationships": schema.relationships,
                "indexes": schema.indexes,
                "migrations": schema.migrations,
            },
        }

    def _design_api(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design API contract."""
        requirements = input_data.get("requirements", {})
        self.emit_status("Designing API contract...", "info")

        contract = APIContract(
            project_id=input_data.get("project_id", "proj-001"),
        )

        return {
            "api_contract": {
                "project_id": contract.project_id,
                "version": contract.version,
                "base_path": contract.base_path,
                "endpoints": contract.endpoints,
                "schemas": contract.schemas,
                "security_schemes": contract.security_schemes,
            },
            "openapi_spec": {},
        }

    def _design_ui(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Design UI/UX."""
        requirements = input_data.get("requirements", {})
        self.emit_status("Designing UI/UX...", "info")

        ui = UIDesign(
            project_id=input_data.get("project_id", "proj-001"),
        )

        return {
            "ui_design": {
                "project_id": ui.project_id,
                "pages": ui.pages,
                "components": ui.components,
                "design_system": ui.design_system,
                "user_flows": ui.user_flows,
                "wireframes": ui.wireframes,
                "accessibility_notes": ui.accessibility_notes,
            },
        }

    def _create_design_system(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a design system."""
        brand = input_data.get("brand", {})
        self.emit_status("Creating design system...", "info")

        return {
            "design_system": {
                "colors": {},
                "typography": {},
                "spacing": {},
                "components": {},
                "icons": {},
                "dark_mode": True,
            },
        }

    def _write_technical_spec(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Write technical specification."""
        feature = input_data.get("feature", {})
        self.emit_status("Writing technical specification...", "info")

        return {
            "technical_spec": {
                "feature": feature.get("name", ""),
                "overview": "",
                "requirements": [],
                "design": {},
                "api_changes": [],
                "database_changes": [],
                "ui_changes": [],
                "testing_strategy": [],
                "deployment_notes": [],
                "rollback_plan": [],
            },
        }

    def _design_system(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Full system design combining all aspects."""
        self.emit_status("Designing complete system...", "info")

        # Run all design tasks
        arch_result = self._design_architecture(input_data)
        db_result = self._design_database(input_data)
        api_result = self._design_api(input_data)
        ui_result = self._design_ui(input_data)

        return {
            **arch_result,
            **db_result,
            **api_result,
            **ui_result,
        }

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        # Add design-specific context
        packet.payload["design_context"] = {
            "architecture": artifacts.get("architecture_spec", {}),
            "database_schema": artifacts.get("database_schema", {}),
            "api_contract": artifacts.get("api_contract", {}),
            "ui_design": artifacts.get("ui_design", {}),
            "design_system": artifacts.get("design_system", {}),
        }
        return packet


def create_design_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.CREATIVE,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> DesignAgent:
    """Factory function to create a DesignAgent."""
    return DesignAgent(agent_id, personality, model_config, signals)