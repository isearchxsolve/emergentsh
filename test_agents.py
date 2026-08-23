"""Test agent imports and basic functionality."""
import sys
sys.path.insert(0, 'src')

# Test imports
from core.agents import (
    BaseAgent,
    AgentRole,
    AgentPersonality,
    AgentCapability,
    AgentRegistry,
    get_registry,
    PlanningAgent,
    DesignAgent,
    FrontendAgent,
    BackendAgent,
    IntegrationAgent,
    QAAgent,
    DevOpsAgent,
    VersionControlAgent,
    ArchitectAgent,
    PMAgent,
    CustomAgent,
    CustomAgentBuilder,
    create_planning_agent,
    create_design_agent,
    create_frontend_agent,
    create_backend_agent,
    create_integration_agent,
    create_qa_agent,
    create_devops_agent,
)

print("All imports successful!")

# Test creating agents
planning = create_planning_agent("test-planning")
print(f"Created PlanningAgent: {planning.agent_id}, role={planning.role}")

design = create_design_agent("test-design")
print(f"Created DesignAgent: {design.agent_id}, role={design.role}")

frontend = create_frontend_agent("test-frontend")
print(f"Created FrontendAgent: {frontend.agent_id}, role={frontend.role}")

backend = create_backend_agent("test-backend")
print(f"Created BackendAgent: {backend.agent_id}, role={backend.role}")

integration = create_integration_agent("test-integration")
print(f"Created IntegrationAgent: {integration.agent_id}, role={integration.role}")

qa = create_qa_agent("test-qa")
print(f"Created QAAgent: {qa.agent_id}, role={qa.role}")

devops = create_devops_agent("test-devops")
print(f"Created DevOpsAgent: {devops.agent_id}, role={devops.role}")

# Test registry
registry = get_registry()
print(f"Registry agents: {list(registry._classes.keys())}")

print("\n=== ALL AGENT TESTS PASSED ===")