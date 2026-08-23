"""Tests for the multi-agent system."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.agents import (
    BaseAgent,
    AgentRole,
    AgentPersonality,
    AgentCapability,
    AgentContext,
    AgentTask,
    HandoffPacket,
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
    DesignerAgent,
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


def test_agent_roles():
    """Test that all agent roles are defined."""
    assert AgentRole.PLANNING
    assert AgentRole.DESIGN
    assert AgentRole.FRONTEND
    assert AgentRole.BACKEND
    assert AgentRole.INTEGRATION
    assert AgentRole.QA
    assert AgentRole.DEVOPS
    assert AgentRole.VERSION_CONTROL
    assert AgentRole.ARCHITECT
    assert AgentRole.PM
    assert AgentRole.CUSTOM
    print("✓ AgentRole enum test passed")


def test_agent_personalities():
    """Test that all agent personalities are defined."""
    assert AgentPersonality.ANALYTICAL
    assert AgentPersonality.CREATIVE
    assert AgentPersonality.PRAGMATIC
    assert AgentPersonality.CAUTIOUS
    assert AgentPersonality.COLLABORATIVE
    assert AgentPersonality.AUTONOMOUS
    print("✓ AgentPersonality enum test passed")


def test_agent_capability():
    """Test AgentCapability dataclass."""
    cap = AgentCapability(
        name="test_capability",
        description="Test capability",
        tool_names=["tool1", "tool2"],
        produces_artifacts=["artifact1"],
    )
    assert cap.name == "test_capability"
    assert cap.description == "Test capability"
    assert cap.tool_names == ["tool1", "tool2"]
    assert cap.produces_artifacts == ["artifact1"]
    print("✓ AgentCapability test passed")


def test_agent_context():
    """Test AgentContext dataclass."""
    from pathlib import Path
    ctx = AgentContext(
        agent_id="agent-001",
        role=AgentRole.PLANNING,
        project_id="proj-001",
        task_id="task-001",
        working_directory=Path("/tmp/test"),
        available_tools={"tool1", "tool2"},
        input_artifacts={"spec": "test spec"},
        output_artifacts={},
        metadata={},
        parent_task_id=None,
        handoff_history=[],
    )
    assert ctx.project_id == "proj-001"
    assert ctx.agent_id == "agent-001"
    assert ctx.role == AgentRole.PLANNING
    assert ctx.input_artifacts["spec"] == "test spec"
    print("✓ AgentContext test passed")


def test_agent_task():
    """Test AgentTask dataclass."""
    from datetime import datetime
    task = AgentTask(
        id="task-001",
        role=AgentRole.PLANNING,
        title="Test Task",
        description="Test description",
        priority=1,
        dependencies=[],
        assigned_agent_id="agent-001",
        status="pending",
        input_data={"key": "value"},
        output_data={},
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
        error=None,
    )
    assert task.id == "task-001"
    assert task.role == AgentRole.PLANNING
    assert task.title == "Test Task"
    assert task.input_data["key"] == "value"
    print("✓ AgentTask test passed")


def test_handoff_packet():
    """Test HandoffPacket dataclass."""
    from datetime import datetime
    packet = HandoffPacket(
        from_agent_id="agent-001",
        from_role=AgentRole.PLANNING,
        to_agent_id="agent-002",
        to_role=AgentRole.DESIGN,
        task_id="task-001",
        payload={"data": "test"},
        artifacts={"artifact": "value"},
        context_summary="Test context",
        requires_approval=False,
        timestamp=datetime.now(),
    )
    assert packet.from_agent_id == "agent-001"
    assert packet.to_agent_id == "agent-002"
    assert packet.from_role == AgentRole.PLANNING
    assert packet.to_role == AgentRole.DESIGN
    assert packet.payload["data"] == "test"
    print("✓ HandoffPacket test passed")


def test_planning_agent():
    """Test PlanningAgent creation and basic functionality."""
    agent = create_planning_agent("planner-001")
    assert agent.agent_id == "planner-001"
    assert agent.role == AgentRole.PLANNING
    assert agent.personality == AgentPersonality.ANALYTICAL
    assert len(agent.capabilities) > 0
    print("✓ PlanningAgent test passed")


def test_design_agent():
    """Test DesignAgent creation and basic functionality."""
    agent = create_design_agent("designer-001")
    assert agent.agent_id == "designer-001"
    assert agent.role == AgentRole.DESIGN
    assert agent.personality == AgentPersonality.CREATIVE
    assert len(agent.capabilities) > 0
    print("✓ DesignAgent test passed")


def test_frontend_agent():
    """Test FrontendAgent creation and basic functionality."""
    agent = create_frontend_agent("frontend-001")
    assert agent.agent_id == "frontend-001"
    assert agent.role == AgentRole.FRONTEND
    assert agent.personality == AgentPersonality.PRAGMATIC
    assert len(agent.capabilities) > 0
    print("✓ FrontendAgent test passed")


def test_backend_agent():
    """Test BackendAgent creation and basic functionality."""
    agent = create_backend_agent("backend-001")
    assert agent.agent_id == "backend-001"
    assert agent.role == AgentRole.BACKEND
    assert agent.personality == AgentPersonality.PRAGMATIC
    assert len(agent.capabilities) > 0
    print("✓ BackendAgent test passed")


def test_integration_agent():
    """Test IntegrationAgent creation and basic functionality."""
    agent = create_integration_agent("integration-001")
    assert agent.agent_id == "integration-001"
    assert agent.role == AgentRole.INTEGRATION
    assert agent.personality == AgentPersonality.PRAGMATIC
    assert len(agent.capabilities) > 0
    print("✓ IntegrationAgent test passed")


def test_qa_agent():
    """Test QAAgent creation and basic functionality."""
    agent = create_qa_agent("qa-001")
    assert agent.agent_id == "qa-001"
    assert agent.role == AgentRole.QA
    assert agent.personality == AgentPersonality.ANALYTICAL
    assert len(agent.capabilities) > 0
    print("✓ QAAgent test passed")


def test_devops_agent():
    """Test DevOpsAgent creation and basic functionality."""
    agent = create_devops_agent("devops-001")
    assert agent.agent_id == "devops-001"
    assert agent.role == AgentRole.DEVOPS
    assert agent.personality == AgentPersonality.PRAGMATIC
    assert len(agent.capabilities) > 0
    print("✓ DevOpsAgent test passed")


def test_agent_registry():
    """Test AgentRegistry functionality."""
    registry = AgentRegistry()
    
    # Register agents
    planner = create_planning_agent("planner-001")
    designer = create_design_agent("designer-001")
    
    registry.register_instance(planner.agent_id, planner)
    registry.register_instance(designer.agent_id, designer)
    
    # Test retrieval
    assert registry.get_instance("planner-001") == planner
    assert registry.get_instance("designer-001") == designer
    
    # Test role-based retrieval
    planning_agents = [a for a in registry._instances.values() if a.role == AgentRole.PLANNING]
    assert len(planning_agents) == 1
    assert planning_agents[0] == planner
    
    design_agents = [a for a in registry._instances.values() if a.role == AgentRole.DESIGN]
    assert len(design_agents) == 1
    assert design_agents[0] == designer
    
    # Test all agents
    all_agents = registry._instances
    assert len(all_agents) == 2
    
    # Test unregister
    del registry._instances["planner-001"]
    assert registry.get_instance("planner-001") is None
    assert len(registry._instances) == 1
    
    print("✓ AgentRegistry test passed")


def test_global_registry():
    """Test global registry singleton."""
    registry1 = get_registry()
    registry2 = get_registry()
    assert registry1 is registry2
    print("✓ Global registry singleton test passed")


def test_agent_execution():
    """Test agent task execution."""
    agent = create_planning_agent("planner-001")
    
    from pathlib import Path
    from datetime import datetime
    
    task = AgentTask(
        id="task-001",
        role=AgentRole.PLANNING,
        title="Create Spec",
        description="Create project specification",
        priority=1,
        dependencies=[],
        assigned_agent_id="planner-001",
        status="pending",
        input_data={"project_id": "proj-001", "requirements": "Build a todo app"},
        output_data={},
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
        error=None,
    )
    
    context = AgentContext(
        agent_id="planner-001",
        role=AgentRole.PLANNING,
        project_id="proj-001",
        task_id="task-001",
        working_directory=Path("/tmp/test"),
        available_tools=set(),
        input_artifacts={},
        output_artifacts={},
        metadata={},
        parent_task_id=None,
        handoff_history=[],
    )
    
    result = agent.execute(task, context)
    # The planning agent returns project_plan for the default task type
    assert "project_plan" in result
    assert result["project_plan"]["project_id"] == "proj-001"
    print("✓ Agent execution test passed")


def test_agent_handoff():
    """Test agent handoff preparation."""
    agent = create_planning_agent("planner-001")
    
    from pathlib import Path
    from datetime import datetime
    
    task = AgentTask(
        id="task-001",
        role=AgentRole.PLANNING,
        title="Create Spec",
        description="Create project specification",
        priority=1,
        dependencies=[],
        assigned_agent_id="planner-001",
        status="pending",
        input_data={"project_id": "proj-001", "requirements": "Build a todo app"},
        output_data={},
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
        error=None,
    )
    
    context = AgentContext(
        agent_id="planner-001",
        role=AgentRole.PLANNING,
        project_id="proj-001",
        task_id="task-001",
        working_directory=Path("/tmp/test"),
        available_tools=set(),
        input_artifacts={},
        output_artifacts={},
        metadata={},
        parent_task_id=None,
        handoff_history=[],
    )
    
    agent.execute(task, context)
    
    # Prepare handoff to design agent
    handoff = agent.prepare_handoff(
        to_role=AgentRole.DESIGN,
        payload={"spec": agent.context.output_artifacts.get("spec", {})},
        artifacts=agent.context.output_artifacts,
    )
    
    assert handoff.from_role == AgentRole.PLANNING
    assert handoff.to_role == AgentRole.DESIGN
    assert "spec" in handoff.payload
    print("✓ Agent handoff test passed")


def test_custom_agent_builder():
    """Test CustomAgentBuilder."""
    builder = CustomAgentBuilder("custom-001")
    
    agent = (builder
        .with_personality(AgentPersonality.CREATIVE)
        .with_capability("custom_cap", "Custom capability", ["tool1"], ["artifact1"])
        .with_system_prompt("You are a custom agent.")
        .build())
    
    assert agent.agent_id == "custom-001"
    assert agent.role == AgentRole.CUSTOM
    assert agent.personality == AgentPersonality.CREATIVE
    assert len(agent.capabilities) == 1
    cap_names = list(agent.capabilities.keys())
    assert cap_names[0] == "custom_cap"
    print("✓ CustomAgentBuilder test passed")


def run_all_tests():
    """Run all tests."""
    print("Running agent tests...\n")
    
    test_agent_roles()
    test_agent_personalities()
    test_agent_capability()
    test_agent_context()
    test_agent_task()
    test_handoff_packet()
    test_planning_agent()
    test_design_agent()
    test_frontend_agent()
    test_backend_agent()
    test_integration_agent()
    test_qa_agent()
    test_devops_agent()
    test_agent_registry()
    test_global_registry()
    test_agent_execution()
    test_agent_handoff()
    test_custom_agent_builder()
    
    print("\n=== ALL AGENT TESTS PASSED ===")


if __name__ == "__main__":
    run_all_tests()