"""
MainWindow — the primary application window.

Layout (Project-Centric)
------------------------
┌──────────────┬─────────────────────────────────────────────┐
│ ProjectPanel │  Chat Area (scrollable)                     │
│              │                                             │
│  Projects    │  [user message]                             │
│  [New +]     │  [assistant message]                        │
│  Sessions    │  [tool output]                              │
│  [actions]   │  [reasoning]                                │
│              │                                             │
│              ├─────────────────────────────────────────────┤
│              │  Execution Drawer (resizable)               │
│              ├─────────────────────────────────────────────┤
│              │  [Prompt Input]              [Send] [Stop]  │
└──────────────┴─────────────────────────────────────────────┘

Two execution modes:
1. Single Agent (legacy): AgentWorker with NIMAgentCore
2. Multi-Agent Orchestration: OrchestratorWorker with task graph
"""

import os
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..core.signals import AgentSignals
from ..core.workspace import WorkspaceManager, get_workspace, Project, Profile, Session
from ..core.preview import DevServerManager, DevServerConfig, DevServerStatus, create_dev_server_manager
from ..core.models import get_model_registry
from ..workers.agent_worker import AgentWorker
from ..workers.orchestrator_worker import OrchestratorWorker, OrchestratorSignals
from .theme import DARK_THEME_QSS
from .widgets.chat_area import ChatAreaWidget
from .widgets.execution_drawer import ExecutionDrawer
from .widgets.profile_dialog import ProfileDialog
from .widgets.project_panel import ProjectPanel
from .widgets.project_wizard import ProjectWizard
from .widgets.preview.preview_widget import PreviewWidget
from .widgets.agent_builder.agent_builder_dialog import AgentBuilderDialog
from .widgets.auth.auth_dialog import AuthDialog


class MainWindow(QMainWindow):
    """Primary application window with project-centric workflow."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EmergentSH — Multi-Agent Development Environment")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        # ── State ──────────────────────────────────────────────────
        self._workspace = get_workspace()
        self._current_project: Optional[Project] = None
        self._current_profile: Optional[Profile] = None
        self._current_session: Optional[Session] = None

        # Workers
        self._agent_worker: Optional[AgentWorker] = None
        self._orchestrator_worker: Optional[OrchestratorWorker] = None
        self._agent_signals: Optional[AgentSignals] = None
        self._orch_signals: Optional[OrchestratorSignals] = None
        self._is_running: bool = False
        self._use_orchestrator: bool = True  # Default to multi-agent mode

        # Preview
        self._dev_server_manager: Optional[DevServerManager] = None
        self._preview_widget: Optional[PreviewWidget] = None

        # ── Build UI ───────────────────────────────────────────────
        self._build_ui()
        self._build_statusbar()

        # Initialize preview system
        self._init_preview()

        # Load last project or show welcome
        self._load_last_project_or_welcome()

    def _init_preview(self) -> None:
        """Initialize dev server manager and preview widget."""
        self._dev_server_manager = create_dev_server_manager(
            workspace=self._workspace,
            log_callback=self._on_dev_server_log,
            status_callback=self._on_dev_server_status,
        )
        self._preview_widget = PreviewWidget(self)
        self._preview_widget.load_finished.connect(self._on_preview_load_finished)
        self._preview_widget.console_message.connect(self._on_preview_console_message)
        self._preview_widget.inspect_element.connect(self._on_inspect_element)

    def _build_ui(self) -> None:
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Three-way horizontal splitter ─────────────────────────────
        self._h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._h_splitter.setHandleWidth(1)
        self._h_splitter.setChildrenCollapsible(False)

        # 1. Project Panel (Sidebar) - fixed width ~280px
        self.project_panel = ProjectPanel(self._workspace)
        self.project_panel.project_selected.connect(self._on_project_selected)
        self.project_panel.new_project_requested.connect(self._on_new_project)
        self.project_panel.session_selected.connect(self._on_session_selected)
        self.project_panel.clear_context_requested.connect(self._on_clear_context)
        self.project_panel.open_folder_requested.connect(self._on_open_folder)
        self.project_panel.archive_project_requested.connect(self._on_archive_project)
        self._h_splitter.addWidget(self.project_panel)

        # 2. Center panel (Chat + Execution Drawer + Input) - main work area
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Chat area + execution drawer in vertical splitter
        self._v_splitter = QSplitter(Qt.Orientation.Vertical)
        self._v_splitter.setHandleWidth(2)
        self._v_splitter.setChildrenCollapsible(False)

        self.chat_area = ChatAreaWidget()
        self.execution_drawer = ExecutionDrawer()

        self._v_splitter.addWidget(self.chat_area)
        self._v_splitter.addWidget(self.execution_drawer)
        self._v_splitter.setStretchFactor(0, 3)
        self._v_splitter.setStretchFactor(1, 1)
        self._v_splitter.setSizes([600, 200])

        center_layout.addWidget(self._v_splitter, stretch=1)

        # Input area
        input_frame = QFrame()
        input_frame.setObjectName("InputFrame")
        input_frame.setFixedHeight(72)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 10, 16, 10)

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setObjectName("PromptInput")
        self.prompt_input.setPlaceholderText(
            "Describe what you want to build…  (Enter to send, Shift+Enter for newline)"
        )
        self.prompt_input.setFixedHeight(48)
        input_layout.addWidget(self.prompt_input, stretch=1)

        # Mode toggle
        self._mode_btn = QPushButton("🤖 Multi-Agent")
        self._mode_btn.setObjectName("ModeButton")
        self._mode_btn.setFixedWidth(140)
        self._mode_btn.setCheckable(True)
        self._mode_btn.setChecked(True)
        self._mode_btn.toggled.connect(self._on_mode_toggled)
        input_layout.addWidget(self._mode_btn)

        # Agent Builder button
        self._agent_builder_btn = QPushButton("🛠️ Agent Builder")
        self._agent_builder_btn.setObjectName("AgentBuilderButton")
        self._agent_builder_btn.setFixedWidth(140)
        self._agent_builder_btn.clicked.connect(self._on_open_agent_builder)
        input_layout.addWidget(self._agent_builder_btn)

        # Auth/Profile button
        self._auth_btn = QPushButton("👤 Profile")
        self._auth_btn.setObjectName("AuthButton")
        self._auth_btn.setFixedWidth(100)
        self._auth_btn.clicked.connect(self._on_open_auth)
        input_layout.addWidget(self._auth_btn)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("SendButton")
        self.send_btn.setFixedWidth(100)
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("StopButton")
        self.stop_btn.setFixedWidth(100)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._on_stop)
        input_layout.addWidget(self.stop_btn)

        center_layout.addWidget(input_frame)

        self._h_splitter.addWidget(center_panel)

        # 3. Preview Panel (right side) - ~400px default
        self._preview_widget = PreviewWidget(self)
        self._preview_widget.load_finished.connect(self._on_preview_load_finished)
        self._preview_widget.console_message.connect(self._on_preview_console_message)
        self._preview_widget.inspect_element.connect(self._on_inspect_element)
        self._h_splitter.addWidget(self._preview_widget)

        # Configure splitter proportions: 280 | 700 | 400
        self._h_splitter.setStretchFactor(0, 0)  # Fixed sidebar
        self._h_splitter.setStretchFactor(1, 1)  # Flexible center
        self._h_splitter.setStretchFactor(2, 0)  # Fixed preview
        self._h_splitter.setSizes([280, 700, 400])

        main_layout.addWidget(self._h_splitter)
        self.setCentralWidget(central)

        # ── Keyboard shortcut: Enter to send ───────────────────────
        send_sc = QShortcut(QKeySequence(Qt.Key.Key_Return), self.prompt_input)
        send_sc.activated.connect(self._on_send)
        newline_sc = QShortcut(
            QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_Return), self.prompt_input
        )
        newline_sc.activated.connect(
            lambda: self.prompt_input.insertPlainText("\n")
        )

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QPushButton("Ready")
        self._status_label.setFlat(True)
        self._status_label.setEnabled(False)
        sb.addWidget(self._status_label)

        self._project_label = QPushButton("No Project")
        self._project_label.setFlat(True)
        self._project_label.setEnabled(False)
        sb.addWidget(self._project_label)

        self._agent_label = QPushButton("")
        self._agent_label.setFlat(True)
        self._agent_label.setEnabled(False)
        sb.addPermanentWidget(self._agent_label)

        self._round_label = QPushButton("")
        self._round_label.setFlat(True)
        self._round_label.setEnabled(False)
        sb.addPermanentWidget(self._round_label)

        self._token_label = QPushButton("")
        self._token_label.setFlat(True)
        self._token_label.setEnabled(False)
        sb.addPermanentWidget(self._token_label)

    # ==================================================================
    # Project / Session loading
    # ==================================================================
    def _load_last_project_or_welcome(self) -> None:
        """Load the most recently updated project or show welcome."""
        projects = self._workspace.list_projects()
        if projects:
            # Select the most recently updated
            self._on_project_selected(projects[0].id)
        else:
            self._status_label.setText("Welcome! Create a new project to begin.")
            self.send_btn.setEnabled(False)

    def _on_project_selected(self, project_id: str) -> None:
        """Handle project selection from panel."""
        project = self._workspace.get_project(project_id)
        if not project:
            return

        self._current_project = project
        self._current_session = None

        # Update UI
        self.project_panel.refresh_sessions(project_id)
        self._project_label.setText(f"📁 {project.name}")
        self._status_label.setText(f"Project: {project.name}")

        # Update chat with project context
        self.chat_area.clear_messages()
        self.chat_area.add_message("tool", f"📁 Project loaded: {project.name}")
        if project.description:
            self.chat_area.add_message("tool", f"Description: {project.description}")
        stack_parts = []
        if project.tech_stack.get("frontend"):
            stack_parts.append(f"Frontend: {project.tech_stack['frontend']}")
        if project.tech_stack.get("backend"):
            stack_parts.append(f"Backend: {project.tech_stack['backend']}")
        if project.tech_stack.get("database"):
            stack_parts.append(f"DB: {project.tech_stack['database']}")
        if stack_parts:
            self.chat_area.add_message("tool", "Tech Stack: " + "  ·  ".join(stack_parts))

        # Enable send
        self.send_btn.setEnabled(True)

        # Load or create default profile for this project
        if project.profile_id:
            self._current_profile = self._workspace.get_profile(project.profile_id)
        if not self._current_profile:
            # Fallback to first available profile
            profiles = self._workspace.list_profiles()
            if profiles:
                self._current_profile = profiles[0]

    def _on_session_selected(self, session_id: str) -> None:
        """Handle session selection for resume."""
        if not self._current_project:
            return
        session = self._workspace.get_session(session_id)
        if not session:
            return

        self._current_session = session
        self._status_label.setText(f"Resuming session: {session.goal or '(no goal)'}")

        # Show session in chat
        self.chat_area.clear_messages()
        self.chat_area.add_message("tool", f"🔄 Resuming session")
        if session.goal:
            self.chat_area.add_message("tool", f"Goal: {session.goal}")
        self.chat_area.add_message("tool", f"{len(session.messages)} messages in history")

    def _on_new_project(self) -> None:
        """Open the new project wizard."""
        wizard = ProjectWizard(self._workspace, self)
        wizard.project_created.connect(self._on_project_created)
        wizard.exec()

    def _on_project_created(self, project: Project) -> None:
        """Handle project creation from wizard."""
        self._on_project_selected(project.id)

    def _on_open_folder(self, project_id: str) -> None:
        """Open project folder in file explorer."""
        project = self._workspace.get_project(project_id)
        if not project:
            return
        try:
            os.startfile(project.root_dir)  # Windows
        except AttributeError:
            import subprocess
            subprocess.run(["xdg-open", project.root_dir])  # Linux
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {e}")

    def _on_archive_project(self, project_id: str) -> None:
        """Archive a project."""
        if QMessageBox.question(
            self, "Archive Project",
            "Archive this project? It will be hidden from the list but not deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._workspace.update_project(project_id, archived_at=datetime.now().isoformat())
            self.project_panel.refresh_projects()
            if self._current_project and self._current_project.id == project_id:
                self._current_project = None
                self._load_last_project_or_welcome()

    def _on_clear_context(self) -> None:
        """Clear chat and agent context."""
        self.chat_area.clear_messages()
        self.execution_drawer.clear()
        self._current_session = None
        self._status_label.setText("Context cleared.")

    # ==================================================================
    # Execution Mode Toggle
    # ==================================================================
    def _on_mode_toggled(self, checked: bool) -> None:
        """Switch between single-agent and multi-agent mode."""
        self._use_orchestrator = checked
        self._mode_btn.setText("🤖 Multi-Agent" if checked else "🤖 Single Agent")
        self._status_label.setText(f"Mode: {'Multi-Agent Orchestration' if checked else 'Single Agent'}")

    # ==================================================================
    # Send / Stop
    # ==================================================================
    def _on_send(self) -> None:
        if self._is_running:
            return
        if not self._current_project:
            QMessageBox.warning(self, "No Project", "Please select or create a project first.")
            return

        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return

        # Clear input
        self.prompt_input.clear()

        # Add user message to chat
        self.chat_area.add_message("user", prompt)

        # Set running state
        self._is_running = True
        self.send_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        self._status_label.setText("Agent running…" if not self._use_orchestrator else "Orchestrator running…")

        # Create signal objects
        self._agent_signals = AgentSignals()
        self._connect_agent_signals(self._agent_signals)

        if self._use_orchestrator:
            self._start_orchestrator(prompt)
        else:
            self._start_single_agent(prompt)

    def _on_stop(self) -> None:
        """Request stop of running agent/orchestrator."""
        if self._orchestrator_worker and self._orchestrator_worker.isRunning():
            self._orchestrator_worker.request_stop()
            self._status_label.setText("Stopping orchestrator…")
        elif self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.request_stop()
            self._status_label.setText("Stopping agent…")

    def _on_open_agent_builder(self) -> None:
        """Open the agent builder dialog."""
        from .widgets.agent_builder.agent_builder_dialog import AgentBuilderDialog
        dialog = AgentBuilderDialog(parent=self)
        dialog.agent_created.connect(self._on_agent_created)
        dialog.exec()

    def _on_open_auth(self) -> None:
        """Open the authentication dialog."""
        dialog = AuthDialog(parent=self)
        dialog.auth_success.connect(self._on_auth_success)
        dialog.exec()

    def _on_auth_success(self, config: dict) -> None:
        """Handle successful authentication."""
        QMessageBox.information(
            self,
            "Authentication Updated",
            f"Authentication configuration saved successfully!\n\n"
            f"Provider: {config.get('provider', 'Unknown')}\n"
            f"Type: {config.get('type', 'api_key')}"
        )

    def _on_agent_created(self, config: dict) -> None:
        """Handle agent creation from the builder dialog."""
        # Show confirmation
        QMessageBox.information(
            self,
            "Agent Created",
            f"Custom agent '{config['name']}' created successfully!\n"
            f"Role: {config['role']}\n"
            f"Model: {config['model_id']}\n\n"
            f"You can now use this agent in your projects."
        )

    def _start_single_agent(self, prompt: str) -> None:
        """Start single-agent execution (legacy mode)."""
        if not self._current_profile:
            profiles = self._workspace.list_profiles()
            if profiles:
                self._current_profile = profiles[0]
            else:
                QMessageBox.warning(self, "No Profile", "No AI profile configured.")
                self._on_agent_finished()
                return

        self._agent_worker = AgentWorker(
            profile={
                "name": self._current_profile.name,
                "key": self._current_profile.api_key,
                "default_model": self._current_profile.default_model,
                "rpm": self._current_profile.rpm,
                "models": self._current_profile.models,
            },
            project_dir=self._current_project.root_dir,
            signals=self._agent_signals,
            prompt=prompt,
            resume=self._current_session is not None,
        )
        self._agent_worker.start()

    def _start_orchestrator(self, prompt: str) -> None:
        """Start multi-agent orchestration."""
        if not self._current_profile:
            profiles = self._workspace.list_profiles()
            if profiles:
                self._current_profile = profiles[0]
            else:
                QMessageBox.warning(self, "No Profile", "No AI profile configured.")
                self._on_agent_finished()
                return

        self._orch_signals = OrchestratorSignals()
        self._connect_orchestrator_signals(self._orch_signals)

        self._orchestrator_worker = OrchestratorWorker(
            profile={
                "name": self._current_profile.name,
                "key": self._current_profile.api_key,
                "default_model": self._current_profile.default_model,
                "rpm": self._current_profile.rpm,
                "models": self._current_profile.models,
            },
            project_dir=self._current_project.root_dir,
            project_name=self._current_project.name,
            project_goal=prompt,
            signals=self._agent_signals,
            orchestrator_signals=self._orch_signals,
        )
        self._orchestrator_worker.start()

    # ==================================================================
    # Signal connections
    # ==================================================================
    def _connect_agent_signals(self, sig: AgentSignals) -> None:
        sig.token_reasoning.connect(self._on_token_reasoning)
        sig.token_content.connect(self._on_token_content)
        sig.response_finished.connect(self._on_response_finished)
        sig.tool_start.connect(self.execution_drawer.on_tool_start)
        sig.tool_executing.connect(self.execution_drawer.on_tool_executing)
        sig.tool_output.connect(self.execution_drawer.on_tool_output)
        sig.tool_result.connect(self._on_tool_result)
        sig.round_started.connect(self._on_round_started)
        sig.agent_finished.connect(self._on_agent_finished)
        sig.status_info.connect(self._on_status_info)
        sig.status_warning.connect(self._on_status_warning)
        sig.error.connect(self._on_error)
        sig.context_compacted.connect(self._on_context_compacted)
        sig.provider_info.connect(self._on_provider_info)
        sig.auto_corrected.connect(self._on_auto_corrected)
        sig.auto_nudged.connect(self._on_auto_nudged)

    def _connect_orchestrator_signals(self, sig: OrchestratorSignals) -> None:
        sig.project_started.connect(self._on_project_started)
        sig.project_completed.connect(self._on_project_completed)
        sig.project_failed.connect(self._on_project_failed)
        sig.task_status_changed.connect(self._on_task_status_changed)
        sig.task_created.connect(self._on_task_created)
        sig.graph_progress.connect(self._on_graph_progress)
        sig.agent_spawned.connect(self._on_agent_spawned)
        sig.agent_completed.connect(self._on_agent_completed)
        sig.agent_failed.connect(self._on_agent_failed)
        sig.handoff_initiated.connect(self._on_handoff_initiated)
        sig.handoff_completed.connect(self._on_handoff_completed)
        sig.escalation_received.connect(self._on_escalation_received)
        sig.state_updated.connect(self._on_state_updated)
        sig.decision_required.connect(self._on_decision_required)

    # ==================================================================
    # Agent signal handlers (single-agent mode)
    # ==================================================================
    def _on_token_reasoning(self, text: str) -> None:
        self.chat_area.append_to_last("reasoning", text)

    def _on_token_content(self, text: str) -> None:
        self.chat_area.append_to_last("assistant", text)

    def _on_response_finished(self, content: str) -> None:
        pass  # Streaming already handled

    def _on_tool_result(self, tool_name: str, result: str) -> None:
        self.execution_drawer.on_tool_result(tool_name, result)
        preview = result[:500]
        if len(result) > 500:
            preview += f"\n… ({len(result)} chars total)"
        self.chat_area.add_message("tool", f"[{tool_name}]\n{preview}")

    def _on_round_started(self, rnd: int, ctx: int) -> None:
        self._round_label.setText(f"Round {rnd}/100")
        self._token_label.setText(f"~{ctx} tok")

    def _on_agent_finished(self) -> None:
        self._is_running = False
        self.send_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        self._status_label.setText("Ready")
        self._agent_worker = None
        self._orchestrator_worker = None

    def _on_status_info(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_status_warning(self, msg: str) -> None:
        self._status_label.setText(f"⚠ {msg}")

    def _on_error(self, msg: str) -> None:
        self._status_label.setText(f"✗ {msg}")
        QMessageBox.critical(self, "Agent Error", msg)
        self._on_agent_finished()

    def _on_context_compacted(self, old_tok: int, new_tok: int) -> None:
        self._status_label.setText(f"Context compacted: ~{old_tok} → ~{new_tok} tokens")
        self._token_label.setText(f"~{new_tok} tok")

    def _on_provider_info(self, name: str, model_id: str) -> None:
        self._status_label.setText(f"Streaming from {name} ({model_id})…")

    def _on_auto_corrected(self, msg: str) -> None:
        self.chat_area.add_message("tool", f"⚠ Auto-Correction: {msg}")

    def _on_auto_nudged(self, msg: str) -> None:
        self.chat_area.add_message("tool", f"⚠ Auto-Nudge: {msg}")

    # ==================================================================
    # Orchestrator signal handlers (multi-agent mode)
    # ==================================================================
    def _on_project_started(self, project_id: str, project_name: str) -> None:
        self._status_label.setText(f"🚀 Project started: {project_name}")
        self.chat_area.add_message("tool", f"🚀 Multi-agent orchestration started for: {project_name}")

    def _on_project_completed(self, project_id: str, summary: dict) -> None:
        completed = summary.get("completed", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total_tasks", 0)
        self._status_label.setText(f"✅ Project completed: {completed}/{total} tasks")
        self.chat_area.add_message("tool",
            f"✅ Project completed!\n"
            f"Tasks: {completed} succeeded, {failed} failed out of {total} total."
        )
        self._on_agent_finished()

    def _on_project_failed(self, project_id: str, error: str) -> None:
        self._status_label.setText(f"❌ Project failed: {error}")
        self.chat_area.add_message("tool", f"❌ Project failed: {error}")
        self._on_agent_finished()

    def _on_task_status_changed(self, task_id: str, old_status: str, new_status: str) -> None:
        self.chat_area.add_message("tool", f"📋 Task {task_id[:8]}: {old_status} → {new_status}")

    def _on_task_created(self, task_dict: dict) -> None:
        task_id = task_dict.get("id", "unknown")
        name = task_dict.get("name", "Unnamed")
        role = task_dict.get("role", "unknown")
        self.chat_area.add_message("tool", f"📝 New task: {name} ({role}) [{task_id[:8]}]")

    def _on_graph_progress(self, completed: int, running: int, total: int) -> None:
        self._round_label.setText(f"Tasks: {completed}/{total} done, {running} running")
        self._token_label.setText(f"{running} active")

    def _on_agent_spawned(self, agent_id: str, role: str, task_id: str) -> None:
        self._agent_label.setText(f"🤖 {role.title()}")
        self.chat_area.add_message("tool", f"🤖 {role.title()} agent started for task {task_id[:8]}")

    def _on_agent_completed(self, agent_id: str, task_id: str, result: dict) -> None:
        self.chat_area.add_message("tool", f"✅ {task_id[:8]} completed by agent {agent_id[:8]}")
        if result.get("output"):
            preview = str(result["output"])[:300]
            self.chat_area.add_message("tool", f"Output: {preview}")

    def _on_agent_failed(self, agent_id: str, task_id: str, error: str) -> None:
        self.chat_area.add_message("tool", f"❌ Task {task_id[:8]} failed: {error}")

    def _on_handoff_initiated(self, from_role: str, to_role: str, task_id: str) -> None:
        self.chat_area.add_message("tool", f"🔄 Handoff: {from_role} → {to_role} (task {task_id[:8]})")

    def _on_handoff_completed(self, from_task_id: str, to_task_id: str, payload: dict) -> None:
        self.chat_area.add_message("tool", f"🔄 Handoff complete: {from_task_id[:8]} → {to_task_id[:8]}")

    def _on_escalation_received(self, from_role: str, issue: str, context: dict) -> None:
        self.chat_area.add_message("tool", f"⚠️ Escalation from {from_role}: {issue}")

    def _on_state_updated(self, state_dict: dict) -> None:
        # Update project state display if needed
        pass

    def _on_decision_required(self, question: str, context: dict) -> None:
        self.chat_area.add_message("tool", f"❓ Decision needed: {question}")
        # TODO: Show decision dialog to user

    # ==================================================================
    # Preview signal handlers
    # ==================================================================
    def _on_dev_server_log(self, message: str) -> None:
        self.execution_drawer.on_tool_output(message)

    def _on_dev_server_status(self, status: DevServerStatus) -> None:
        if status.state == "running":
            self._preview_widget.load_project(self._current_project.root_dir, status.port)
            self._status_label.setText(f"🌐 Preview server running at {status.url}")
        elif status.state == "error":
            self._status_label.setText(f"❌ Preview server error: {status.error}")
        elif status.state == "starting":
            self._status_label.setText(f"🔄 Starting preview server on port {status.port}…")

    def _on_preview_load_finished(self, ok: bool) -> None:
        if ok:
            self._status_label.setText("✅ Preview loaded")
        else:
            self._status_label.setText("❌ Preview failed to load")

    def _on_preview_console_message(self, message: str) -> None:
        self.execution_drawer.on_tool_output(message)

    def _on_inspect_element(self, element_info: dict) -> None:
        self.chat_area.add_message("tool", f"🔍 Element inspected: {element_info.get('tag', 'unknown')}#{element_info.get('id', '')}")

    # ==================================================================
    # Cleanup
    # ==================================================================
    def closeEvent(self, event) -> None:
        if self._orchestrator_worker and self._orchestrator_worker.isRunning():
            self._orchestrator_worker.request_stop()
            self._orchestrator_worker.wait(5000)
        elif self._agent_worker and self._agent_worker.isRunning():
            self._agent_worker.request_stop()
            self._agent_worker.wait(5000)
        event.accept()


# Import datetime for archive
from datetime import datetime