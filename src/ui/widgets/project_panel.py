"""
ProjectPanel — left sidebar with project management.

Shows:
  * A list of projects (click to switch)
  * A "New Project" button
  * A list of saved sessions for the current project
  * Actions: Open Folder, Archive
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.workspace import WorkspaceManager, get_workspace, Project
from .project_wizard import ProjectWizard


class ProjectPanel(QWidget):
    """
    Left sidebar with project and session management.

    Emits
    -----
    project_selected : str
        Emitted with project ID when user selects a project.
    session_selected : str
        Emitted with session ID when user clicks a session.
    new_project_requested : ()
        Emitted when user clicks "New Project".
    open_folder_requested : str
        Emitted with project ID when user clicks "Open Folder".
    archive_project_requested : str
        Emitted with project ID when user clicks "Archive".
    clear_context_requested : ()
        Emitted when user clicks "Clear Context".
    """

    project_selected = Signal(str)
    session_selected = Signal(str)
    new_project_requested = Signal()
    open_folder_requested = Signal(str)
    archive_project_requested = Signal(str)
    clear_context_requested = Signal()

    def __init__(self, workspace: Optional[WorkspaceManager] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectPanel")
        self.setFixedWidth(280)

        self._workspace = workspace or get_workspace()
        self._current_project_id: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title ──────────────────────────────────────────────────
        title = QLabel("◆ Projects")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        # ── Projects section ──────────────────────────────────────
        projects_label = QLabel("PROJECTS")
        projects_label.setObjectName("SectionLabel")
        layout.addWidget(projects_label)

        self._project_list = QListWidget()
        self._project_list.setObjectName("ProjectList")
        self._project_list.itemClicked.connect(self._on_project_clicked)
        self._project_list.itemDoubleClicked.connect(self._on_project_double_clicked)
        layout.addWidget(self._project_list, stretch=1)

        new_project_btn = QPushButton("+ New Project")
        new_project_btn.clicked.connect(self._on_new_project)
        layout.addWidget(new_project_btn)

        # ── Project actions ───────────────────────────────────────
        actions_layout = QHBoxLayout()
        self._open_folder_btn = QPushButton("📂 Open")
        self._open_folder_btn.setEnabled(False)
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        actions_layout.addWidget(self._open_folder_btn)

        self._archive_btn = QPushButton("📦 Archive")
        self._archive_btn.setEnabled(False)
        self._archive_btn.clicked.connect(self._on_archive)
        actions_layout.addWidget(self._archive_btn)
        layout.addLayout(actions_layout)

        # ── Sessions section ──────────────────────────────────────
        sessions_label = QLabel("SESSIONS")
        sessions_label.setObjectName("SectionLabel")
        layout.addWidget(sessions_label)

        self._session_list = QListWidget()
        self._session_list.setObjectName("SessionList")
        self._session_list.itemClicked.connect(self._on_session_clicked)
        layout.addWidget(self._session_list, stretch=1)

        # Clear context button
        clear_btn = QPushButton("✗ Clear Context")
        clear_btn.clicked.connect(self.clear_context_requested.emit)
        layout.addWidget(clear_btn)

        self.refresh_projects()

    def refresh_projects(self) -> None:
        """Reload the project list from workspace."""
        self._project_list.clear()
        projects = self._workspace.list_projects(include_archived=False)
        for p in projects:
            # Format: "Name\n  web · nextjs+tailwind · fastapi"
            stack_info = []
            if p.tech_stack:
                if p.tech_stack.get("frontend"):
                    stack_info.append(p.tech_stack["frontend"])
                if p.tech_stack.get("backend"):
                    stack_info.append(p.tech_stack["backend"])
            stack_str = " · ".join(stack_info) if stack_info else "empty"
            target_str = p.target if hasattr(p, "target") else "web"
            label = f"{p.name}\n  {target_str} · {stack_str}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._project_list.addItem(item)

    def refresh_sessions(self, project_id: str) -> None:
        """Reload sessions for the given project."""
        self._session_list.clear()
        sessions = self._workspace.get_sessions_for_project(project_id)
        for s in sessions:
            goal = s.goal or "(no goal set)"
            msg_count = len(s.messages)
            label = f"{goal[:50]}\n  {msg_count} messages"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self._session_list.addItem(item)

    def select_project(self, project_id: str) -> None:
        """Programmatically select a project by ID."""
        for i in range(self._project_list.count()):
            item = self._project_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == project_id:
                self._project_list.setCurrentRow(i)
                self._on_project_clicked(item)
                break

    def _on_new_project(self) -> None:
        wizard = ProjectWizard(self._workspace, self)
        wizard.project_created.connect(self._on_project_created)
        wizard.exec()

    def _on_project_created(self, project: Project) -> None:
        self.refresh_projects()
        self.select_project(project.id)

    def _on_project_clicked(self, item: QListWidgetItem) -> None:
        project_id = item.data(Qt.ItemDataRole.UserRole)
        if project_id == self._current_project_id:
            return
        self._current_project_id = project_id
        self.refresh_sessions(project_id)
        self._open_folder_btn.setEnabled(True)
        self._archive_btn.setEnabled(True)
        self.project_selected.emit(project_id)

    def _on_project_double_clicked(self, item: QListWidgetItem) -> None:
        # Could open project settings
        pass

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.session_selected.emit(session_id)

    def _on_open_folder(self) -> None:
        if self._current_project_id:
            self.open_folder_requested.emit(self._current_project_id)

    def _on_archive(self) -> None:
        if self._current_project_id:
            self.archive_project_requested.emit(self._current_project_id)

    @property
    def current_project_id(self) -> Optional[str]:
        return self._current_project_id