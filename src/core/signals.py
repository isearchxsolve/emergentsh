"""
AgentSignals — Qt signals emitted by the agent worker thread.

These signals decouple the agentic loop from the UI.  The worker thread
emits them; the main window connects slots to update widgets.
"""

from PySide6.QtCore import QObject, Signal


class AgentSignals(QObject):
    """
    All signals are emitted from the worker thread and marshalled to the
    GUI thread by Qt's queued-connection mechanism.
    """

    # ── Streaming ──────────────────────────────────────────────────
    #: A reasoning/thinking token arrived (``str``).
    token_reasoning = Signal(str)
    #: A content token arrived (``str``).
    token_content = Signal(str)
    #: Full assistant message finished (``str`` full content).
    response_finished = Signal(str)

    # ── Tool lifecycle ─────────────────────────────────────────────
    #: A tool call is being prepared (tool_name: str).
    tool_start = Signal(str)
    #: A tool is executing (tool_name, args_json).
    tool_executing = Signal(str, str)
    #: A line of live stdout/stderr from run_command (line: str).
    tool_output = Signal(str)
    #: A tool finished (tool_name, result: str).
    tool_result = Signal(str, str)

    # ── Round / lifecycle ───────────────────────────────────────────
    #: A new agentic round started (round_number: int, context_tokens: int).
    round_started = Signal(int, int)
    #: The agent loop finished entirely.
    agent_finished = Signal()
    #: The agent is waiting / pacing (message: str).
    status_info = Signal(str)
    #: A warning was issued (message: str).
    status_warning = Signal(str)
    #: An error occurred (message: str).
    error = Signal(str)
    #: Context was compacted (old_tokens, new_tokens).
    context_compacted = Signal(int, int)
    #: Provider info (provider_name: str, model_id: str).
    provider_info = Signal(str, str)
    #: Auto-correction interceptor fired (message: str).
    auto_corrected = Signal(str)
    #: Auto-nudge fired (message: str).
    auto_nudged = Signal(str)

    # ── Orchestration (multi-agent) ─────────────────────────────────
    #: A task status changed (task_id, old_status, new_status).
    task_status_changed = Signal(str, str, str)
    #: A new task was created (task_dict).
    task_created = Signal(dict)
    #: Graph progress update (completed, running, total).
    graph_progress = Signal(int, int, int)
    #: An agent was spawned (agent_id, role, task_id).
    agent_spawned = Signal(str, str, str)
    #: An agent completed (agent_id, role, task_id).
    agent_completed = Signal(str, str, str)
    #: A handoff was initiated (handoff_id, from_role, to_role, objective).
    handoff_initiated = Signal(str, str, str, str)
    #: A handoff was acknowledged (handoff_id, accepted).
    handoff_acknowledged = Signal(str, bool)
    #: Project started (project_id, project_name).
    project_started = Signal(str, str)
    #: Project completed (project_id, summary_dict).
    project_completed = Signal(str, dict)
    #: Project failed (project_id, error).
    project_failed = Signal(str, str)
