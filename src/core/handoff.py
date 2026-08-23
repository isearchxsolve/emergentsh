"""
Inter-Agent Handoff Protocol — structured communication for task delegation
and context transfer between specialist agents.

This defines the wire format for handoffs: what gets passed, how it's
validated, and how agents acknowledge receipt.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from typing_extensions import TypedDict


# ════════════════════════════════════════════════════════════════════════════
# Handoff Types & Structures
# ════════════════════════════════════════════════════════════════════════════

class HandoffType(str, Enum):
    """Types of inter-agent handoffs."""
    DELEGATE = "delegate"           # Orchestrator → Specialist: "do this task"
    HANDOFF = "handoff"             # Specialist → Specialist: "take over from here"
    ESCALATE = "escalate"           # Specialist → Orchestrator: "blocked/need decision"
    CONSULT = "consult"             # Specialist → Specialist: "review this"
    MERGE = "merge"                 # Specialist → Orchestrator: "here's my result"
    SYNC = "sync"                   # Any → Any: "state update"


@dataclass
class HandoffContext:
    """
    Rich context passed during handoff. Contains everything the receiving
    agent needs to continue work without asking clarifying questions.
    """
    # Source info
    from_role: str
    from_task_id: str
    from_agent_id: int

    # Target info
    to_role: str

    # Core payload
    objective: str                    # What should the receiver do?
    acceptance_criteria: List[str]    # How to know it's done
    context_summary: str              # Human-readable summary of work so far

    # Artifacts & state
    artifacts: Dict[str, Any] = field(default_factory=dict)      # Key outputs
    files_modified: List[str] = field(default_factory=list)      # Paths changed
    decisions_made: List[Dict[str, Any]] = field(default_factory=list)

    # Technical context
    tech_stack: Dict[str, str] = field(default_factory=dict)
    api_contracts: Dict[str, Any] = field(default_factory=dict)
    design_tokens: Dict[str, Any] = field(default_factory=dict)

    # Constraints & guidance
    constraints: List[str] = field(default_factory=list)
    suggested_approach: str = ""
    files_to_reference: List[str] = field(default_factory=list)

    # Metadata
    handoff_type: HandoffType = HandoffType.DELEGATE
    priority: int = 50
    created_at: datetime = field(default_factory=datetime.now)
    handoff_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["handoff_type"] = self.handoff_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HandoffContext":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["handoff_type"] = HandoffType(data["handoff_type"])
        return cls(**data)


@dataclass
class HandoffAcknowledgment:
    """Receiver's acknowledgment of handoff receipt."""
    handoff_id: str
    received_at: datetime = field(default_factory=datetime.now)
    accepted: bool = True
    questions: List[str] = field(default_factory=list)  # Clarifying questions if any
    estimated_effort: Optional[str] = None  # e.g., "2-3 rounds"


# ════════════════════════════════════════════════════════════════════════════
# Handoff Manager — orchestrates the handoff flow
# ════════════════════════════════════════════════════════════════════════════

class HandoffManager:
    """
    Manages the lifecycle of handoffs between agents.

    Flow:
    1. Sender creates HandoffContext via create_handoff()
    2. Manager validates and stores
    3. Receiver gets handoff via get_pending_handoffs()
    4. Receiver acknowledges via acknowledge()
    5. Manager updates state, notifies sender
    """

    def __init__(self):
        self._pending: Dict[str, HandoffContext] = {}           # handoff_id -> context
        self._acknowledged: Dict[str, HandoffAcknowledgment] = {}
        self._history: List[Dict[str, Any]] = []                # Full audit trail
        self._by_sender: Dict[int, Set[str]] = defaultdict(set)  # agent_id -> handoff_ids
        self._by_receiver_role: Dict[str, Set[str]] = defaultdict(set)

    def create_handoff(self, context: HandoffContext) -> HandoffContext:
        """Register a new handoff."""
        if context.handoff_id in self._pending:
            raise ValueError(f"Handoff {context.handoff_id} already exists")
        self._pending[context.handoff_id] = context
        self._by_sender[context.from_agent_id].add(context.handoff_id)
        self._by_receiver_role[context.to_role].add(context.handoff_id)
        self._history.append({
            "event": "created",
            "handoff_id": context.handoff_id,
            "from_role": context.from_role,
            "to_role": context.to_role,
            "timestamp": datetime.now().isoformat(),
        })
        return context

    def get_pending_for_role(self, role: str) -> List[HandoffContext]:
        """Get all pending handoffs targeted at a role."""
        ids = self._by_receiver_role.get(role, set())
        return [self._pending[hid] for hid in ids if hid in self._pending]

    def get_pending_for_agent(self, agent_id: int) -> List[HandoffContext]:
        """Get all pending handoffs sent by an agent."""
        ids = self._by_sender.get(agent_id, set())
        return [self._pending[hid] for hid in ids if hid in self._pending]

    def acknowledge(self, handoff_id: str, ack: HandoffAcknowledgment) -> bool:
        """Record acknowledgment and remove from pending."""
        if handoff_id not in self._pending:
            return False
        handoff = self._pending.pop(handoff_id)
        self._acknowledged[handoff_id] = ack
        self._by_sender[handoff.from_agent_id].discard(handoff_id)
        self._by_receiver_role[handoff.to_role].discard(handoff_id)
        self._history.append({
            "event": "acknowledged",
            "handoff_id": handoff_id,
            "accepted": ack.accepted,
            "timestamp": datetime.now().isoformat(),
        })
        return True

    def get_handoff(self, handoff_id: str) -> Optional[HandoffContext]:
        return self._pending.get(handoff_id) or self._acknowledged.get(handoff_id)

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def get_stats(self) -> Dict[str, int]:
        return {
            "pending": len(self._pending),
            "acknowledged": len(self._acknowledged),
            "total": len(self._history),
        }


# ════════════════════════════════════════════════════════════════════════════
# Tool Schema for Handoff (for NIMAgentCore to call)
# ════════════════════════════════════════════════════════════════════════════

HANDOFF_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "handoff_task",
        "description": (
            "Delegate a task to another specialist agent. Use this to hand off "
            "work that requires a different expertise. Provide a complete context "
            "so the receiving agent can continue without asking questions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "to_role": {
                    "type": "string",
                    "enum": [
                        "planner", "architect", "designer", "frontend",
                        "backend", "integration", "devops", "qa", "docs",
                        "version_control"
                    ],
                    "description": "The specialist role to delegate to",
                },
                "objective": {
                    "type": "string",
                    "description": "Clear, specific objective for the receiving agent",
                },
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of criteria that define completion",
                },
                "context_summary": {
                    "type": "string",
                    "description": "Summary of work done so far and current state",
                },
                "artifacts": {
                    "type": "object",
                    "description": "Key outputs (code, specs, configs) to pass along",
                    "additionalProperties": True,
                },
                "files_modified": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths that were created/modified",
                },
                "decisions_made": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Technical decisions with rationale",
                },
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Constraints the receiver must respect",
                },
                "suggested_approach": {
                    "type": "string",
                    "description": "Suggested technical approach or starting point",
                },
                "files_to_reference": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Existing files the receiver should read first",
                },
                "priority": {
                    "type": "integer",
                    "default": 50,
                    "description": "Priority 0-200 (higher = more urgent)",
                },
            },
            "required": ["to_role", "objective", "acceptance_criteria", "context_summary"],
        },
    },
}


# ════════════════════════════════════════════════════════════════════════════
# Handoff Execution Helpers
# ════════════════════════════════════════════════════════════════════════════

def create_delegation_handoff(
    *,
    from_role: str,
    from_task_id: str,
    from_agent_id: int,
    to_role: str,
    objective: str,
    acceptance_criteria: List[str],
    context_summary: str,
    artifacts: Optional[Dict[str, Any]] = None,
    files_modified: Optional[List[str]] = None,
    decisions_made: Optional[List[Dict[str, Any]]] = None,
    tech_stack: Optional[Dict[str, str]] = None,
    api_contracts: Optional[Dict[str, Any]] = None,
    design_tokens: Optional[Dict[str, Any]] = None,
    constraints: Optional[List[str]] = None,
    suggested_approach: str = "",
    files_to_reference: Optional[List[str]] = None,
    priority: int = 50,
) -> HandoffContext:
    """Convenience function to create a standard delegation handoff."""
    return HandoffContext(
        from_role=from_role,
        from_task_id=from_task_id,
        from_agent_id=from_agent_id,
        to_role=to_role,
        objective=objective,
        acceptance_criteria=acceptance_criteria,
        context_summary=context_summary,
        artifacts=artifacts or {},
        files_modified=files_modified or [],
        decisions_made=decisions_made or [],
        tech_stack=tech_stack or {},
        api_contracts=api_contracts or {},
        design_tokens=design_tokens or {},
        constraints=constraints or [],
        suggested_approach=suggested_approach,
        files_to_reference=files_to_reference or [],
        handoff_type=HandoffType.DELEGATE,
        priority=priority,
    )


def create_escalation_handoff(
    *,
    from_role: str,
    from_task_id: str,
    from_agent_id: int,
    issue: str,
    context_summary: str,
    artifacts: Optional[Dict[str, Any]] = None,
    blocking: bool = True,
) -> HandoffContext:
    """Create an escalation handoff to orchestrator for blockers/decisions."""
    return HandoffContext(
        from_role=from_role,
        from_task_id=from_task_id,
        from_agent_id=from_agent_id,
        to_role="orchestrator",
        objective=f"Resolve blocker: {issue}",
        acceptance_criteria=["Blocker resolved or alternative approach approved"],
        context_summary=context_summary,
        artifacts=artifacts or {},
        constraints=["Requires orchestrator decision" if blocking else "Advisory only"],
        handoff_type=HandoffType.ESCALATE,
        priority=100 if blocking else 50,
    )


def create_consultation_handoff(
    *,
    from_role: str,
    from_task_id: str,
    from_agent_id: int,
    to_role: str,
    question: str,
    context_summary: str,
    artifacts: Optional[Dict[str, Any]] = None,
) -> HandoffContext:
    """Create a consultation request to another specialist."""
    return HandoffContext(
        from_role=from_role,
        from_task_id=from_task_id,
        from_agent_id=from_agent_id,
        to_role=to_role,
        objective=f"Consultation: {question}",
        acceptance_criteria=["Provide expert guidance or review"],
        context_summary=context_summary,
        artifacts=artifacts or {},
        handoff_type=HandoffType.CONSULT,
        priority=30,
    )


def create_merge_handoff(
    *,
    from_role: str,
    from_task_id: str,
    from_agent_id: int,
    deliverables: Dict[str, Any],
    context_summary: str,
    files_modified: Optional[List[str]] = None,
) -> HandoffContext:
    """Create a merge handoff: specialist → orchestrator with completed work."""
    return HandoffContext(
        from_role=from_role,
        from_task_id=from_task_id,
        from_agent_id=from_agent_id,
        to_role="orchestrator",
        objective="Deliver completed work for integration",
        acceptance_criteria=["Work reviewed and integrated"],
        context_summary=context_summary,
        artifacts=deliverables,
        files_modified=files_modified or [],
        handoff_type=HandoffType.MERGE,
        priority=80,
    )