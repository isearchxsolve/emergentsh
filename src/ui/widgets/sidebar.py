"""
SidebarWidget — left panel with profile selection and session history.

Shows:
  * A list of profiles (click to switch)
  * A "New Profile" button
  * A list of saved sessions for the current profile+directory
  * A "Clear Context" button
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.config import ConfigManager


class SidebarWidget(QWidget):
    """
    Left sidebar with profile, session, and directory management.

    Emits
    -----
    profile_selected : ``str``
        Emitted with the profile ID when the user selects a profile.
    new_profile_requested : ``()``
        Emitted when the user clicks "New Profile".
    clear_context_requested : ``()``
        Emitted when the user clicks "Clear Context".
    session_selected : ``str``
        Emitted with the session key ("profile::dir") when the user
        clicks a saved session to resume it.
    directory_changed : ``str``
        Emitted with the new working directory when the user opens a
        different folder.
    """

    profile_selected = Signal(str)
    new_profile_requested = Signal()
    clear_context_requested = Signal()
    session_selected = Signal(str)
    directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title ──────────────────────────────────────────────────
        title = QLabel("◆ EmergentSH")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        # ── Profiles section ──────────────────────────────────────
        profiles_label = QLabel("PROFILES")
        profiles_label.setObjectName("SectionLabel")
        layout.addWidget(profiles_label)

        self._profile_list = QListWidget()
        self._profile_list.setObjectName("ProfileList")
        layout.addWidget(self._profile_list, stretch=1)

        new_profile_btn = QPushButton("+ New Profile")
        new_profile_btn.clicked.connect(self.new_profile_requested.emit)
        layout.addWidget(new_profile_btn)

        # ── Sessions section ──────────────────────────────────────
        sessions_label = QLabel("SESSIONS")
        sessions_label.setObjectName("SectionLabel")
        layout.addWidget(sessions_label)

        self._session_list = QListWidget()
        self._session_list.setObjectName("SessionList")
        layout.addWidget(self._session_list, stretch=1)

        # ── Working directory ─────────────────────────────────────
        dir_label = QLabel("WORKING DIRECTORY")
        dir_label.setObjectName("SectionLabel")
        layout.addWidget(dir_label)

        self._dir_label = QLabel("(not set)")
        self._dir_label.setObjectName("DirLabel")
        self._dir_label.setWordWrap(True)
        self._dir_label.setStyleSheet(
            "color: #565f89; font-size: 11px; padding: 2px 12px;"
        )
        layout.addWidget(self._dir_label)

        open_dir_btn = QPushButton("📂 Open Folder")
        open_dir_btn.clicked.connect(self._on_open_folder)
        layout.addWidget(open_dir_btn)

        # ── Actions ────────────────────────────────────────────────
        clear_btn = QPushButton("✗ Clear Context")
        clear_btn.clicked.connect(self.clear_context_requested.emit)
        layout.addWidget(clear_btn)

        # ── Connect signals ────────────────────────────────────────
        self._profile_list.itemClicked.connect(self._on_profile_clicked)
        self._session_list.itemClicked.connect(self._on_session_clicked)

        self.refresh_profiles()

    # ------------------------------------------------------------------
    def set_working_directory(self, path: str) -> None:
        """Update the displayed working directory."""
        self._dir_label.setText(path)

    def _on_open_folder(self) -> None:
        """Open a native folder dialog and emit directory_changed."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Working Directory"
        )
        if path:
            self.set_working_directory(path)
            self.directory_changed.emit(path)

    # ------------------------------------------------------------------
    def refresh_profiles(self) -> None:
        """Reload the profile list from config."""
        self._profile_list.clear()
        profiles = ConfigManager.get_profiles()
        for pid, p in profiles.items():
            try:
                model_id = p["models"][p["default_model"]]["id"]
            except (KeyError, TypeError):
                model_id = "unknown"
            label = f"{p.get('name', 'Unknown')}  ·  {model_id}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, pid)
            self._profile_list.addItem(item)

    def refresh_sessions(self, profile_name: str, pdir: str) -> None:
        """Reload the session list for a given profile+directory."""
        self._session_list.clear()
        sessions = ConfigManager.list_sessions()
        prefix = f"{profile_name}::"
        for key, data in sessions.items():
            if key.startswith(prefix):
                goal = data.get("goal") or "(no goal set)"
                msg_count = len(data.get("messages", []))
                label = f"{goal[:40]}\n  {msg_count} messages"
                item = QListWidgetItem(label)
                # Store the full session key so the window can resume it.
                item.setData(Qt.ItemDataRole.UserRole, key)
                self._session_list.addItem(item)

    # ------------------------------------------------------------------
    def _on_profile_clicked(self, item: QListWidgetItem) -> None:
        pid = item.data(Qt.ItemDataRole.UserRole)
        if pid:
            self.profile_selected.emit(pid)

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        """Emit the session key when a saved session is clicked."""
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self.session_selected.emit(key)

    def select_profile(self, pid: str) -> None:
        """Programmatically select a profile by ID."""
        for i in range(self._profile_list.count()):
            item = self._profile_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == pid:
                self._profile_list.setCurrentRow(i)
                break
