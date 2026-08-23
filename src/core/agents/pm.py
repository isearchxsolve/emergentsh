"""
PMAgent — responsible for product management, requirements gathering, and project planning.

The PMAgent handles:
- Requirements gathering and analysis
- User story creation and backlog management
- Sprint planning and release planning
- Feature prioritization (MoSCoW, RICE, WSJF)
- Stakeholder communication
- Acceptance criteria definition
- Roadmap creation and maintenance
- Metrics and KPI definition
- Release notes and changelog management
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


class Priority(Enum):
    """Priority levels for features and tasks."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NICE_TO_HAVE = "nice_to_have"


class MoSCoW(Enum):
    """MoSCoW prioritization categories."""
    MUST_HAVE = "must_have"
    SHOULD_HAVE = "should_have"
    COULD_HAVE = "could_have"
    WONT_HAVE = "wont_have"


@dataclass
class UserStory:
    """User story definition."""
    id: str
    title: str
    description: str
    acceptance_criteria: List[str] = field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    moscow: MoSCoW = MoSCoW.SHOULD_HAVE
    story_points: Optional[int] = None
    epic_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Epic:
    """Epic definition."""
    id: str
    title: str
    description: str
    user_stories: List[str] = field(default_factory=list)  # story IDs
    priority: Priority = Priority.HIGH
    target_release: Optional[str] = None
    business_value: int = 0
    effort_estimate: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Sprint:
    """Sprint definition."""
    id: str
    name: str
    goal: str
    start_date: datetime
    end_date: datetime
    stories: List[str] = field(default_factory=list)  # story IDs
    capacity: int = 0
    velocity: int = 0
    status: str = "planned"  # planned, active, completed, cancelled


@dataclass
class Release:
    """Release definition."""
    id: str
    name: str
    version: str
    description: str
    target_date: datetime
    epics: List[str] = field(default_factory=list)  # epic IDs
    stories: List[str] = field(default_factory=list)  # story IDs
    status: str = "planned"  # planned, in_progress, released, cancelled
    release_notes: str = ""


@dataclass
class Roadmap:
    """Product roadmap."""
    id: str
    name: str
    description: str
    time_horizon: str  # quarterly, half-yearly, yearly
    releases: List[str] = field(default_factory=list)  # release IDs
    themes: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Stakeholder:
    """Stakeholder definition."""
    id: str
    name: str
    role: str
    email: str
    influence: str  # high, medium, low
    interest: str  # high, medium, low
    communication_preference: str = "email"


class PMAgent(BaseAgent):
    """
    Agent specialized in product management and project planning.
    
    Capabilities:
    - Requirements gathering and analysis
    - User story and epic creation
    - Backlog management and prioritization
    - Sprint planning and execution
    - Release planning and management
    - Roadmap creation and maintenance
    - Stakeholder management
    - Metrics and KPI definition
    - Acceptance criteria definition
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.COLLABORATIVE,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="requirements_gathering",
                description="Gather and analyze requirements",
                tool_names=["gather_requirements", "analyze_requirements", "create_user_stories", "define_acceptance_criteria"],
                produces_artifacts=["requirements_doc", "user_stories", "acceptance_criteria"],
            ),
            AgentCapability(
                name="backlog_management",
                description="Manage product backlog",
                tool_names=["create_backlog", "prioritize_backlog", "refine_backlog", "estimate_stories"],
                produces_artifacts=["prioritized_backlog", "estimation_report"],
            ),
            AgentCapability(
                name="sprint_planning",
                description="Plan and manage sprints",
                tool_names=["create_sprint", "plan_sprint", "track_sprint", "sprint_retrospective"],
                produces_artifacts=["sprint_plan", "sprint_report", "retrospective_notes"],
            ),
            AgentCapability(
                name="release_planning",
                description="Plan and manage releases",
                tool_names=["create_release", "plan_release", "track_release", "generate_release_notes"],
                produces_artifacts=["release_plan", "release_notes", "changelog"],
            ),
            AgentCapability(
                name="roadmap_management",
                description="Create and maintain product roadmap",
                tool_names=["create_roadmap", "update_roadmap", "communicate_roadmap"],
                produces_artifacts=["roadmap_doc", "roadmap_presentation"],
            ),
            AgentCapability(
                name="stakeholder_management",
                description="Manage stakeholders and communication",
                tool_names=["identify_stakeholders", "create_communication_plan", "gather_feedback", "manage_expectations"],
                produces_artifacts=["stakeholder_map", "communication_plan", "feedback_report"],
            ),
            AgentCapability(
                name="metrics_kpis",
                description="Define and track metrics and KPIs",
                tool_names=["define_metrics", "create_dashboard", "track_kpis", "generate_reports"],
                produces_artifacts=["metrics_definition", "dashboard_config", "kpi_report"],
            ),
        ]

        system_prompt = """You are a Product Manager Agent in the emergent.sh multi-agent system.
Your role is to manage product requirements, planning, and stakeholder communication.

You operate with a COLLABORATIVE personality: inclusive, communicative, and consensus-building.
You produce clear requirements, well-prioritized backlogs, and actionable plans.

Key responsibilities:
1. Gather and analyze requirements from stakeholders
2. Create user stories with clear acceptance criteria
3. Manage and prioritize product backlog (MoSCoW, RICE, WSJF)
4. Plan sprints with realistic capacity and goals
5. Plan releases with clear scope and timelines
6. Create and maintain product roadmaps
7. Manage stakeholder communication and expectations
8. Define and track metrics/KPIs
9. Generate release notes and changelogs

Output format: Generate requirements documents, user stories, backlogs, sprint plans, release plans, roadmaps, and metrics definitions as structured markdown/JSON.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.PRODUCT_MANAGER,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute PM task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "gather_requirements")

        if task_type == "gather_requirements":
            return self._gather_requirements(task.input_data)
        elif task_type == "create_user_stories":
            return self._create_user_stories(task.input_data)
        elif task_type == "prioritize_backlog":
            return self._prioritize_backlog(task.input_data)
        elif task_type == "plan_sprint":
            return self._plan_sprint(task.input_data)
        elif task_type == "plan_release":
            return self._plan_release(task.input_data)
        elif task_type == "create_roadmap":
            return self._create_roadmap(task.input_data)
        elif task_type == "manage_stakeholders":
            return self._manage_stakeholders(task.input_data)
        elif task_type == "define_metrics":
            return self._define_metrics(task.input_data)
        else:
            return self._gather_requirements(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _gather_requirements(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Gather and analyze requirements."""
        project_id = input_data.get("project_id", "proj-001")
        stakeholders = input_data.get("stakeholders", [])
        self.emit_status(f"Gathering requirements for {project_id}...", "info")

        artifacts = {
            "requirements_doc": self._generate_requirements_doc(project_id, input_data),
            "functional_requirements": self._generate_functional_requirements(input_data),
            "non_functional_requirements": self._generate_non_functional_requirements(input_data),
            "user_personas": self._generate_user_personas(input_data),
            "use_cases": self._generate_use_cases(input_data),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _create_user_stories(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create user stories from requirements."""
        project_id = input_data.get("project_id", "proj-001")
        requirements = input_data.get("requirements", [])
        self.emit_status(f"Creating user stories for {project_id}...", "info")

        stories = []
        for i, req in enumerate(requirements):
            story = UserStory(
                id=f"{project_id}-US-{i+1:03d}",
                title=req.get("title", f"User Story {i+1}"),
                description=req.get("description", ""),
                acceptance_criteria=req.get("acceptance_criteria", []),
                priority=Priority(req.get("priority", "medium")),
                moscow=MoSCoW(req.get("moscow", "should_have")),
                story_points=req.get("story_points"),
                epic_id=req.get("epic_id"),
                tags=req.get("tags", []),
                dependencies=req.get("dependencies", []),
            )
            stories.append(story)

        artifacts = {
            "user_stories": [s.__dict__ for s in stories],
            "story_map": self._generate_story_map(stories),
            "backlog": self._generate_backlog(stories),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _prioritize_backlog(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prioritize product backlog."""
        stories = input_data.get("stories", [])
        method = input_data.get("method", "moscow")  # moscow, rice, wsjf
        self.emit_status(f"Prioritizing backlog using {method.upper()}...", "info")

        # Convert to UserStory objects
        story_objects = [UserStory(**s) if isinstance(s, dict) else s for s in stories]

        if method == "moscow":
            prioritized = self._prioritize_moscow(story_objects)
        elif method == "rice":
            prioritized = self._prioritize_rice(story_objects)
        elif method == "wsjf":
            prioritized = self._prioritize_wsjf(story_objects)
        else:
            prioritized = story_objects

        artifacts = {
            "prioritized_backlog": [s.__dict__ for s in prioritized],
            "prioritization_method": method,
            "prioritization_report": self._generate_prioritization_report(prioritized, method),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _plan_sprint(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan a sprint."""
        project_id = input_data.get("project_id", "proj-001")
        sprint_number = input_data.get("sprint_number", 1)
        backlog = input_data.get("backlog", [])
        capacity = input_data.get("capacity", 40)  # story points
        self.emit_status(f"Planning Sprint {sprint_number} for {project_id}...", "info")

        sprint = Sprint(
            id=f"{project_id}-SPRINT-{sprint_number}",
            name=f"Sprint {sprint_number}",
            goal=input_data.get("goal", f"Sprint {sprint_number} Goal"),
            start_date=datetime.fromisoformat(input_data.get("start_date", datetime.now().isoformat())),
            end_date=datetime.fromisoformat(input_data.get("end_date", (datetime.now().replace(day=datetime.now().day+14)).isoformat())),
            capacity=capacity,
        )

        # Select stories for sprint
        selected_stories = self._select_stories_for_sprint(backlog, capacity)
        sprint.stories = [s.id for s in selected_stories]

        artifacts = {
            "sprint": sprint.__dict__,
            "sprint_plan": self._generate_sprint_plan(sprint, selected_stories),
            "capacity_analysis": self._generate_capacity_analysis(selected_stories, capacity),
            "sprint_board": self._generate_sprint_board(sprint, selected_stories),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _plan_release(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Plan a release."""
        project_id = input_data.get("project_id", "proj-001")
        version = input_data.get("version", "1.0.0")
        self.emit_status(f"Planning release {version} for {project_id}...", "info")

        release = Release(
            id=f"{project_id}-REL-{version}",
            name=f"Release {version}",
            version=version,
            description=input_data.get("description", f"Release {version}"),
            target_date=datetime.fromisoformat(input_data.get("target_date", datetime.now().isoformat())),
            epics=input_data.get("epics", []),
            stories=input_data.get("stories", []),
        )

        artifacts = {
            "release": release.__dict__,
            "release_plan": self._generate_release_plan(release, input_data),
            "release_notes_template": self._generate_release_notes_template(release),
            "deployment_checklist": self._generate_deployment_checklist(),
            "rollback_plan": self._generate_rollback_plan(),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _create_roadmap(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create product roadmap."""
        project_id = input_data.get("project_id", "proj-001")
        time_horizon = input_data.get("time_horizon", "quarterly")
        self.emit_status(f"Creating {time_horizon} roadmap for {project_id}...", "info")

        roadmap = Roadmap(
            id=f"{project_id}-ROADMAP",
            name=f"{project_id} Product Roadmap",
            description=input_data.get("description", "Product roadmap"),
            time_horizon=time_horizon,
            themes=input_data.get("themes", []),
        )

        artifacts = {
            "roadmap": roadmap.__dict__,
            "roadmap_doc": self._generate_roadmap_doc(roadmap, input_data),
            "roadmap_visualization": self._generate_roadmap_visualization(roadmap),
            "theme_breakdown": self._generate_theme_breakdown(input_data.get("themes", [])),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _manage_stakeholders(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manage stakeholders."""
        project_id = input_data.get("project_id", "proj-001")
        stakeholders_data = input_data.get("stakeholders", [])
        self.emit_status(f"Managing stakeholders for {project_id}...", "info")

        stakeholders = [
            Stakeholder(
                id=s.get("id", f"SH-{i}"),
                name=s.get("name", ""),
                role=s.get("role", ""),
                email=s.get("email", ""),
                influence=s.get("influence", "medium"),
                interest=s.get("interest", "medium"),
                communication_preference=s.get("communication_preference", "email"),
            )
            for i, s in enumerate(stakeholders_data)
        ]

        artifacts = {
            "stakeholders": [s.__dict__ for s in stakeholders],
            "stakeholder_map": self._generate_stakeholder_map(stakeholders),
            "communication_plan": self._generate_communication_plan(stakeholders),
            "raci_matrix": self._generate_raci_matrix(stakeholders),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _define_metrics(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Define metrics and KPIs."""
        project_id = input_data.get("project_id", "proj-001")
        goals = input_data.get("goals", [])
        self.emit_status(f"Defining metrics for {project_id}...", "info")

        artifacts = {
            "metrics_definition": self._generate_metrics_definition(goals),
            "kpi_dashboard": self._generate_kpi_dashboard_config(goals),
            "north_star_metric": self._identify_north_star_metric(goals),
            "leading_lagging_indicators": self._classify_indicators(goals),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    # Prioritization methods

    def _prioritize_moscow(self, stories: List[UserStory]) -> List[UserStory]:
        """Prioritize using MoSCoW method."""
        order = {MoSCoW.MUST_HAVE: 0, MoSCoW.SHOULD_HAVE: 1, MoSCoW.COULD_HAVE: 2, MoSCoW.WONT_HAVE: 3}
        return sorted(stories, key=lambda s: (order.get(s.moscow, 4), -s.priority.value if hasattr(s.priority, 'value') else 0))

    def _prioritize_rice(self, stories: List[UserStory]) -> List[UserStory]:
        """Prioritize using RICE scoring (Reach, Impact, Confidence, Effort)."""
        def rice_score(story: UserStory) -> float:
            reach = getattr(story, 'reach', 100)
            impact = getattr(story, 'impact', 3)
            confidence = getattr(story, 'confidence', 0.8)
            effort = getattr(story, 'effort', story.story_points or 5)
            return (reach * impact * confidence) / max(effort, 1)
        return sorted(stories, key=rice_score, reverse=True)

    def _prioritize_wsjf(self, stories: List[UserStory]) -> List[UserStory]:
        """Prioritize using WSJF (Weighted Shortest Job First)."""
        def wsjf_score(story: UserStory) -> float:
            cost_of_delay = getattr(story, 'cost_of_delay', 10)
            duration = getattr(story, 'duration', story.story_points or 5)
            return cost_of_delay / max(duration, 1)
        return sorted(stories, key=wsjf_score, reverse=True)

    def _select_stories_for_sprint(self, backlog: List[Dict], capacity: int) -> List[UserStory]:
        """Select stories for sprint based on priority and capacity."""
        stories = [UserStory(**s) if isinstance(s, dict) else s for s in backlog]
        stories = self._prioritize_moscow(stories)
        
        selected = []
        total_points = 0
        for story in stories:
            points = story.story_points or 5
            if total_points + points <= capacity:
                selected.append(story)
                total_points += points
        return selected

    # Artifact generation methods

    def _generate_requirements_doc(self, project_id: str, input_data: Dict) -> str:
        return f"""# {project_id} Requirements Document

## Project Overview
{input_data.get('overview', 'Project overview')}

## Stakeholders
{self._format_stakeholders(input_data.get('stakeholders', []))}

## Functional Requirements
{self._format_requirements(input_data.get('functional_requirements', []))}

## Non-Functional Requirements
{self._format_requirements(input_data.get('non_functional_requirements', []))}

## Constraints
{self._format_constraints(input_data.get('constraints', []))}

## Assumptions
{self._format_assumptions(input_data.get('assumptions', []))}
"""

    def _generate_functional_requirements(self, input_data: Dict) -> List[Dict]:
        return [
            {"id": "FR-001", "title": "User Authentication", "description": "Users can register, login, and manage account", "priority": "high"},
            {"id": "FR-002", "title": "Data Management", "description": "CRUD operations for core entities", "priority": "high"},
            {"id": "FR-003", "title": "Search and Filter", "description": "Full-text search and advanced filtering", "priority": "medium"},
        ]

    def _generate_non_functional_requirements(self, input_data: Dict) -> List[Dict]:
        return [
            {"id": "NFR-001", "title": "Performance", "description": "API response < 200ms p95", "category": "performance"},
            {"id": "NFR-002", "title": "Availability", "description": "99.9% uptime SLA", "category": "reliability"},
            {"id": "NFR-003", "title": "Security", "description": "OWASP Top 10 compliance", "category": "security"},
            {"id": "NFR-004", "title": "Scalability", "description": "Handle 10k concurrent users", "category": "scalability"},
        ]

    def _generate_user_personas(self, input_data: Dict) -> List[Dict]:
        return [
            {"name": "Primary User", "role": "End User", "goals": ["Complete tasks efficiently"], "pain_points": ["Complex workflows"]},
            {"name": "Admin", "role": "Administrator", "goals": ["Manage system", "Monitor usage"], "pain_points": ["Limited visibility"]},
        ]

    def _generate_use_cases(self, input_data: Dict) -> List[Dict]:
        return [
            {"id": "UC-001", "name": "User Registration", "actor": "User", "flow": ["Enter details", "Verify email", "Create account"]},
            {"id": "UC-002", "name": "Data Export", "actor": "User", "flow": ["Select data", "Choose format", "Download"]},
        ]

    def _generate_story_map(self, stories: List[UserStory]) -> Dict:
        epics = {}
        for story in stories:
            epic_id = story.epic_id or "uncategorized"
            if epic_id not in epics:
                epics[epic_id] = []
            epics[epic_id].append(story.__dict__)
        return epics

    def _generate_backlog(self, stories: List[UserStory]) -> List[Dict]:
        return [s.__dict__ for s in sorted(stories, key=lambda s: (s.moscow.value, -s.priority.value if hasattr(s.priority, 'value') else 0))]

    def _generate_prioritization_report(self, stories: List[UserStory], method: str) -> str:
        return f"""# Prioritization Report ({method.upper()})

## Method: {method.upper()}
## Total Stories: {len(stories)}

## Prioritized Order:
{chr(10).join(f'{i+1}. {s.id} - {s.title} ({s.moscow.value})' for i, s in enumerate(stories))}
"""

    def _generate_sprint_plan(self, sprint: Sprint, stories: List[UserStory]) -> str:
        return f"""# Sprint Plan: {sprint.name}

## Goal
{sprint.goal}

## Dates
Start: {sprint.start_date.strftime('%Y-%m-%d')}
End: {sprint.end_date.strftime('%Y-%m-%d')}

## Capacity
Total: {sprint.capacity} story points
Committed: {sum(s.story_points or 5 for s in stories)} story points

## Stories
{chr(10).join(f'- {s.id}: {s.title} ({s.story_points or 5} pts)' for s in stories)}

## Definition of Done
- Code complete and reviewed
- Tests passing
- Deployed to staging
- Acceptance criteria met
"""

    def _generate_capacity_analysis(self, stories: List[UserStory], capacity: int) -> Dict:
        total = sum(s.story_points or 5 for s in stories)
        return {
            "total_capacity": capacity,
            "committed_points": total,
            "utilization": f"{(total/capacity*100):.1f}%" if capacity > 0 else "0%",
            "remaining_capacity": capacity - total,
            "story_count": len(stories),
        }

    def _generate_sprint_board(self, sprint: Sprint, stories: List[UserStory]) -> Dict:
        return {
            "columns": ["Backlog", "To Do", "In Progress", "In Review", "Done"],
            "stories": [
                {"id": s.id, "title": s.title, "points": s.story_points or 5, "status": "To Do", "assignee": None}
                for s in stories
            ],
        }

    def _generate_release_plan(self, release: Release, input_data: Dict) -> str:
        return f"""# Release Plan: {release.name}

## Version
{release.version}

## Target Date
{release.target_date.strftime('%Y-%m-%d')}

## Scope
### Epics
{chr(10).join(f'- {e}' for e in release.epics)}

### Stories
{chr(10).join(f'- {s}' for s in release.stories)}

## Milestones
- Code Complete: {(release.target_date.replace(day=release.target_date.day-7)).strftime('%Y-%m-%d')}
- QA Complete: {(release.target_date.replace(day=release.target_date.day-3)).strftime('%Y-%m-%d')}
- Release: {release.target_date.strftime('%Y-%m-%d')}

## Risks
{chr(10).join(f'- {r}' for r in input_data.get('risks', ['No risks identified']))}

## Go/No-Go Criteria
- All critical bugs fixed
- Performance benchmarks met
- Security scan passed
- Stakeholder sign-off
"""

    def _generate_release_notes_template(self, release: Release) -> str:
        return f"""# Release Notes: {release.name}

## Version
{release.version} - {release.target_date.strftime('%Y-%m-%d')}

## Highlights
- 

## New Features
- 

## Improvements
- 

## Bug Fixes
- 

## Breaking Changes
- 

## Deprecations
- 

## Known Issues
- 

## Contributors
- 
"""

    def _generate_deployment_checklist(self) -> List[str]:
        return [
            "All tests passing in CI",
            "Security scan completed",
            "Performance benchmarks met",
            "Database migrations tested",
            "Rollback plan verified",
            "Stakeholder approval obtained",
            "Monitoring alerts configured",
            "Documentation updated",
        ]

    def _generate_rollback_plan(self) -> str:
        return """# Rollback Plan

## Trigger Conditions
- Critical bug in production
- Performance degradation > 50%
- Security vulnerability discovered

## Rollback Steps
1. Notify stakeholders
2. Execute database rollback (if applicable)
3. Deploy previous version
4. Verify system health
5. Communicate status

## Rollback Time Target
< 15 minutes
"""

    def _generate_roadmap_doc(self, roadmap: Roadmap, input_data: Dict) -> str:
        nl = chr(10)
        return f"""# {roadmap.name}

## Overview
{roadmap.description}

## Time Horizon
{roadmap.time_horizon.capitalize()}

## Themes
{nl.join(f'### {t.get("name", "Theme")}{nl}{t.get("description", "")}{nl}**Timeline**: {t.get("timeline", "TBD")}{nl}**Epics**: {", ".join(t.get("epics", []))}' for t in roadmap.themes)}

## Releases
{nl.join(f'- {r}' for r in roadmap.releases)}
"""

    def _generate_roadmap_visualization(self, roadmap: Roadmap) -> str:
        nl = chr(10)
        return f"""```mermaid
gantt
    title {roadmap.name}
    dateFormat  YYYY-MM-DD
    axisFormat  %b %Y
{nl.join(f'    section {t.get("name", "Theme")}{nl}    {t.get("name", "task")} :active, {t.get("name", "task").lower().replace(" ", "_")}, {t.get("start", "2024-01-01")}, {t.get("duration", "30d")}' for t in roadmap.themes)}
```
"""

    def _generate_theme_breakdown(self, themes: List[Dict]) -> List[Dict]:
        return [
            {
                "theme": t.get("name", ""),
                "description": t.get("description", ""),
                "epics": t.get("epics", []),
                "timeline": t.get("timeline", ""),
                "success_metrics": t.get("success_metrics", []),
            }
            for t in themes
        ]

    def _generate_stakeholder_map(self, stakeholders: List[Stakeholder]) -> Dict:
        return {
            "high_influence_high_interest": [s.name for s in stakeholders if s.influence == "high" and s.interest == "high"],
            "high_influence_low_interest": [s.name for s in stakeholders if s.influence == "high" and s.interest == "low"],
            "low_influence_high_interest": [s.name for s in stakeholders if s.influence == "low" and s.interest == "high"],
            "low_influence_low_interest": [s.name for s in stakeholders if s.influence == "low" and s.interest == "low"],
        }

    def _generate_communication_plan(self, stakeholders: List[Stakeholder]) -> List[Dict]:
        return [
            {
                "stakeholder": s.name,
                "frequency": "weekly" if s.influence == "high" else "bi-weekly",
                "channel": s.communication_preference,
                "content": "Status updates, decisions needed, blockers" if s.influence == "high" else "Progress summary",
            }
            for s in stakeholders
        ]

    def _generate_raci_matrix(self, stakeholders: List[Stakeholder]) -> Dict:
        activities = ["Requirements", "Design", "Development", "Testing", "Deployment", "Maintenance"]
        matrix = {}
        for activity in activities:
            matrix[activity] = {}
            for s in stakeholders:
                if s.influence == "high":
                    matrix[activity][s.name] = "A" if activity in ["Requirements", "Deployment"] else "R"
                elif s.interest == "high":
                    matrix[activity][s.name] = "C"
                else:
                    matrix[activity][s.name] = "I"
        return matrix

    def _generate_metrics_definition(self, goals: List[Dict]) -> List[Dict]:
        return [
            {
                "name": "User Activation Rate",
                "definition": "Percentage of users who complete onboarding",
                "target": "60%",
                "frequency": "weekly",
                "owner": "Product",
            },
            {
                "name": "Feature Adoption",
                "definition": "Percentage of active users using key features",
                "target": "40%",
                "frequency": "monthly",
                "owner": "Product",
            },
            {
                "name": "Customer Satisfaction (CSAT)",
                "definition": "Average satisfaction score from surveys",
                "target": "4.5/5",
                "frequency": "quarterly",
                "owner": "Product",
            },
            {
                "name": "System Uptime",
                "definition": "Percentage of time system is operational",
                "target": "99.9%",
                "frequency": "real-time",
                "owner": "Engineering",
            },
        ]

    def _generate_kpi_dashboard_config(self, goals: List[Dict]) -> Dict:
        return {
            "panels": [
                {"title": "User Activation", "type": "gauge", "metric": "activation_rate"},
                {"title": "Feature Adoption", "type": "bar", "metric": "feature_adoption"},
                {"title": "CSAT Trend", "type": "line", "metric": "csat"},
                {"title": "System Health", "type": "stat", "metric": "uptime"},
            ],
            "refresh_interval": "5m",
            "time_range": "7d",
        }

    def _identify_north_star_metric(self, goals: List[Dict]) -> Dict:
        return {
            "metric": "Weekly Active Users (WAU)",
            "rationale": "Best indicator of product value delivery",
            "target": "10,000 WAU by Q4",
        }

    def _classify_indicators(self, goals: List[Dict]) -> Dict:
        return {
            "leading": [
                "Sign-up rate",
                "Onboarding completion",
                "Feature usage",
                "NPS score",
            ],
            "lagging": [
                "Revenue",
                "Churn rate",
                "Customer lifetime value",
                "Market share",
            ],
        }

    def _format_stakeholders(self, stakeholders: List) -> str:
        return "\n".join(f"- {s.get('name', '')} ({s.get('role', '')})" for s in stakeholders)

    def _format_requirements(self, requirements: List) -> str:
        return "\n".join(f"- **{r.get('id', '')}**: {r.get('title', '')} - {r.get('description', '')}" for r in requirements)

    def _format_constraints(self, constraints: List) -> str:
        return "\n".join(f"- {c.get('type', '')}: {c.get('description', '')}" for c in constraints)


def create_pm_agent(
    agent_id: str = "pm-001",
    personality: AgentPersonality = AgentPersonality.COLLABORATIVE,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> PMAgent:
    """Factory function to create a PM agent."""
    return PMAgent(
        agent_id=agent_id,
        personality=personality,
        model_config=model_config,
        signals=signals,
    )