"""
AuthDialog — modal dialog for user authentication.

Supports:
- API key entry (for NVIDIA NIM, OpenRouter, etc.)
- OAuth flow initiation (GitHub, Google)
- Session management
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ....core.auth import AuthManager, get_auth_manager


class AuthDialog(QDialog):
    """
    Modal dialog for authentication setup.
    
    Provides tabs for:
    - API Key entry (NVIDIA NIM, OpenRouter, etc.)
    - OAuth providers (GitHub, Google)
    - Session management
    """
    
    auth_success = Signal(dict)  # Emitted with auth config on success
    
    def __init__(self, auth_manager: Optional[AuthManager] = None, parent=None):
        super().__init__(parent)
        self._auth = auth_manager or get_auth_manager()
        self.setWindowTitle("Authentication Setup")
        self.setMinimumWidth(500)
        self.setModal(True)
        
        self._build_ui()
        self._load_existing_credentials()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel("Configure Authentication")
        header.setObjectName("DialogTitle")
        layout.addWidget(header)
        
        subtitle = QLabel(
            "Add your API keys or connect with OAuth providers to use AI models."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #565f89; margin-bottom: 8px;")
        layout.addWidget(subtitle)
        
        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)
        
        # API Keys tab
        self._tabs.addTab(self._create_api_keys_tab(), "🔑 API Keys")
        
        # OAuth tab
        self._tabs.addTab(self._create_oauth_tab(), "🔐 OAuth")
        
        # Sessions tab
        self._tabs.addTab(self._create_sessions_tab(), "📋 Sessions")
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _create_api_keys_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # NVIDIA NIM
        nvidia_group = QGroupBox("NVIDIA NIM")
        nvidia_layout = QFormLayout(nvidia_group)
        
        self._nvidia_key = QLineEdit()
        self._nvidia_key.setPlaceholderText("nvapi-...")
        self._nvidia_key.setEchoMode(QLineEdit.EchoMode.Password)
        nvidia_layout.addRow("API Key:", self._nvidia_key)
        
        nvidia_help = QLabel(
            '<a href="https://build.nvidia.com/explore/discover">Get API key from NVIDIA Build</a>'
        )
        nvidia_help.setOpenExternalLinks(True)
        nvidia_help.setStyleSheet("font-size: 11px; color: #565f89;")
        nvidia_layout.addRow("", nvidia_help)
        
        layout.addWidget(nvidia_group)
        
        # OpenRouter
        or_group = QGroupBox("OpenRouter (Free Models)")
        or_layout = QFormLayout(or_group)
        
        self._openrouter_key = QLineEdit()
        self._openrouter_key.setPlaceholderText("REDACTED_OPENROUTER_KEY...")
        self._openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        or_layout.addRow("API Key:", self._openrouter_key)
        
        or_help = QLabel(
            '<a href="https://openrouter.ai/keys">Get free API key from OpenRouter</a>'
        )
        or_help.setOpenExternalLinks(True)
        or_help.setStyleSheet("font-size: 11px; color: #565f89;")
        or_layout.addRow("", or_help)
        
        layout.addWidget(or_group)
        
        # Anthropic
        anthropic_group = QGroupBox("Anthropic")
        anthropic_layout = QFormLayout(anthropic_group)
        
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setPlaceholderText("sk-ant-...")
        self._anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        anthropic_layout.addRow("API Key:", self._anthropic_key)
        
        anthropic_help = QLabel(
            '<a href="https://console.anthropic.com/">Get API key from Anthropic Console</a>'
        )
        anthropic_help.setOpenExternalLinks(True)
        anthropic_help.setStyleSheet("font-size: 11px; color: #565f89;")
        anthropic_layout.addRow("", anthropic_help)
        
        layout.addWidget(anthropic_group)
        
        # OpenAI
        openai_group = QGroupBox("OpenAI")
        openai_layout = QFormLayout(openai_group)
        
        self._openai_key = QLineEdit()
        self._openai_key.setPlaceholderText("sk-...")
        self._openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        openai_layout.addRow("API Key:", self._openai_key)
        
        openai_help = QLabel(
            '<a href="https://platform.openai.com/api-keys">Get API key from OpenAI Platform</a>'
        )
        openai_help.setOpenExternalLinks(True)
        openai_help.setStyleSheet("font-size: 11px; color: #565f89;")
        openai_layout.addRow("", openai_help)
        
        layout.addWidget(openai_group)
        
        # Custom provider
        custom_group = QGroupBox("Custom Provider")
        custom_layout = QFormLayout(custom_group)
        
        self._custom_name = QLineEdit()
        self._custom_name.setPlaceholderText("e.g., My Custom API")
        custom_layout.addRow("Name:", self._custom_name)
        
        self._custom_url = QLineEdit()
        self._custom_url.setPlaceholderText("https://api.example.com/v1")
        custom_layout.addRow("Base URL:", self._custom_url)
        
        self._custom_key = QLineEdit()
        self._custom_key.setPlaceholderText("API Key")
        self._custom_key.setEchoMode(QLineEdit.EchoMode.Password)
        custom_layout.addRow("API Key:", self._custom_key)
        
        layout.addWidget(custom_group)
        
        layout.addStretch()
        return widget
    
    def _create_oauth_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # GitHub OAuth
        github_group = QGroupBox("GitHub")
        github_layout = QVBoxLayout(github_group)
        
        github_desc = QLabel("Connect your GitHub account to access repositories and create PRs.")
        github_desc.setWordWrap(True)
        github_desc.setStyleSheet("color: #a9b1d6; margin-bottom: 8px;")
        github_layout.addWidget(github_desc)
        
        github_btn_layout = QHBoxLayout()
        self._github_connect_btn = QPushButton("Connect GitHub")
        self._github_connect_btn.clicked.connect(self._on_github_connect)
        github_btn_layout.addWidget(self._github_connect_btn)
        github_btn_layout.addStretch()
        github_layout.addLayout(github_btn_layout)
        
        self._github_status = QLabel("Not connected")
        self._github_status.setStyleSheet("color: #565f89; font-size: 11px;")
        github_layout.addWidget(self._github_status)
        
        layout.addWidget(github_group)
        
        # Google OAuth
        google_group = QGroupBox("Google")
        google_layout = QVBoxLayout(google_group)
        
        google_desc = QLabel("Sign in with Google for calendar, drive, and workspace integration.")
        google_desc.setWordWrap(True)
        google_desc.setStyleSheet("color: #a9b1d6; margin-bottom: 8px;")
        google_layout.addWidget(google_desc)
        
        google_btn_layout = QHBoxLayout()
        self._google_connect_btn = QPushButton("Connect Google")
        self._google_connect_btn.clicked.connect(self._on_google_connect)
        google_btn_layout.addWidget(self._google_connect_btn)
        google_btn_layout.addStretch()
        google_layout.addLayout(google_btn_layout)
        
        self._google_status = QLabel("Not connected")
        self._google_status.setStyleSheet("color: #565f89; font-size: 11px;")
        google_layout.addWidget(self._google_status)
        
        layout.addWidget(google_group)
        
        layout.addStretch()
        return widget
    
    def _create_sessions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Current session
        session_group = QGroupBox("Current Session")
        session_layout = QFormLayout(session_group)
        
        self._session_info = QLabel("No active session")
        self._session_info.setWordWrap(True)
        session_layout.addRow("Status:", self._session_info)
        
        self._session_expires = QLabel("")
        self._session_expires.setStyleSheet("color: #565f89; font-size: 11px;")
        session_layout.addRow("Expires:", self._session_expires)
        
        layout.addWidget(session_group)
        
        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self._logout_btn = QPushButton("Log Out")
        self._logout_btn.clicked.connect(self._on_logout)
        self._logout_btn.setStyleSheet("background-color: #f7768e; color: #1a1b26;")
        actions_layout.addWidget(self._logout_btn)
        
        self._refresh_btn = QPushButton("Refresh Token")
        self._refresh_btn.clicked.connect(self._on_refresh_token)
        actions_layout.addWidget(self._refresh_btn)
        
        layout.addWidget(actions_group)
        
        # Active sessions list
        active_group = QGroupBox("Active Sessions")
        active_layout = QVBoxLayout(active_group)
        
        self._sessions_list = QTextEdit()
        self._sessions_list.setReadOnly(True)
        self._sessions_list.setMaximumHeight(150)
        self._sessions_list.setPlaceholderText("No active sessions")
        active_layout.addWidget(self._sessions_list)
        
        layout.addWidget(active_group)
        layout.addStretch()
        return widget
    
    def _load_existing_credentials(self) -> None:
        """Load existing credentials from auth manager."""
        # API Keys
        self._nvidia_key.setText(self._auth.get_provider_key("nvidia") or "")
        self._openrouter_key.setText(self._auth.get_provider_key("openrouter") or "")
        self._anthropic_key.setText(self._auth.get_provider_key("anthropic") or "")
        self._openai_key.setText(self._auth.get_provider_key("openai") or "")
        
        # Check OAuth connections
        self._update_oauth_status()
    
    def _update_oauth_status(self) -> None:
        """Update OAuth connection status labels."""
        # This would check actual OAuth tokens in a real implementation
        pass
    
    def _on_github_connect(self) -> None:
        """Initiate GitHub OAuth flow."""
        # In a real implementation, this would open a browser window
        # and handle the OAuth callback
        from ..core.auth import create_auth_manager
        
        # Get GitHub OAuth config from environment or settings
        client_id = "your_github_client_id"
        redirect_uri = "http://localhost:8080/callback"
        
        auth = create_auth_manager()
        auth_url = auth.get_github_auth_url(client_id, redirect_uri, scopes=["repo", "user:email"])
        
        # Open in browser
        import webbrowser
        webbrowser.open(auth_url)
        
        # Update status
        self._github_status.setText("Opening browser... Please complete authentication.")
    
    def _on_google_connect(self) -> None:
        """Initiate Google OAuth flow."""
        # Similar to GitHub
        pass
    
    def _on_logout(self) -> None:
        """Log out current user."""
        # Clear session
        pass
    
    def _on_refresh_token(self) -> None:
        """Refresh access token."""
        pass
    
    def _on_accept(self) -> None:
        """Save credentials and accept."""
        # Save API keys
        if self._nvidia_key.text().strip():
            self._auth.set_provider_key("nvidia", self._nvidia_key.text().strip())
        if self._openrouter_key.text().strip():
            self._auth.set_provider_key("openrouter", self._openrouter_key.text().strip())
        if self._anthropic_key.text().strip():
            self._auth.set_provider_key("anthropic", self._anthropic_key.text().strip())
        if self._openai_key.text().strip():
            self._auth.set_provider_key("openai", self._openai_key.text().strip())
        
        # Custom provider
        if self._custom_name.text().strip() and self._custom_key.text().strip():
            self._auth.set_provider_key(
                self._custom_name.text().strip().lower().replace(" ", "_"),
                self._custom_key.text().strip()
            )
        
        # Emit success signal with config
        config = {
            "nvidia": self._nvidia_key.text().strip(),
            "openrouter": self._openrouter_key.text().strip(),
            "anthropic": self._anthropic_key.text().strip(),
            "openai": self._openai_key.text().strip(),
        }
        self.auth_success.emit(config)
        self.accept()
    
    def get_api_keys(self) -> Dict[str, str]:
        """Get the entered API keys."""
        return {
            "nvidia": self._nvidia_key.text().strip(),
            "openrouter": self._openrouter_key.text().strip(),
            "anthropic": self._anthropic_key.text().strip(),
            "openai": self._openai_key.text().strip(),
        }


class ProfileDialog(QDialog):
    """Dialog for managing user profile and preferences."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profile & Preferences")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Profile tab
        profile_widget = QWidget()
        profile_layout = QFormLayout(profile_widget)
        
        self._name_edit = QLineEdit()
        profile_layout.addRow("Display Name:", self._name_edit)
        
        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("your@email.com")
        profile_layout.addRow("Email:", self._email_edit)
        
        self._avatar_btn = QPushButton("Change Avatar")
        self._avatar_btn.clicked.connect(self._on_change_avatar)
        profile_layout.addRow("", self._avatar_btn)
        
        tabs.addTab(profile_widget, "Profile")
        
        # Preferences tab
        prefs_widget = QWidget()
        prefs_layout = QFormLayout(prefs_widget)
        
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark", "Light", "System"])
        prefs_layout.addRow("Theme:", self._theme_combo)
        
        self._font_size = QSpinBox()
        self._font_size.setRange(10, 24)
        self._font_size.setValue(13)
        prefs_layout.addRow("Font Size:", self._font_size)
        
        self._auto_save = QCheckBox("Auto-save sessions")
        self._auto_save.setChecked(True)
        prefs_layout.addRow("", self._auto_save)
        
        tabs.addTab(prefs_widget, "Preferences")
        
        # API Keys tab (read-only summary)
        api_widget = QWidget()
        api_layout = QVBoxLayout(api_widget)
        self._api_summary = QTextEdit()
        self._api_summary.setReadOnly(True)
        self._api_summary.setPlaceholderText("No API keys configured")
        api_layout.addWidget(self._api_summary)
        tabs.addTab(api_widget, "API Keys")
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _on_change_avatar(self) -> None:
        pass


class APIKeyWidget(QWidget):
    """Widget for displaying and managing a single API key."""
    
    key_changed = Signal(str, str)  # provider, key
    key_removed = Signal(str)  # provider
    
    def __init__(self, provider: str, display_name: str, key: str = "", parent=None):
        super().__init__(parent)
        self._provider = provider
        self._display_name = display_name
        self._key = key
        self._build_ui()
    
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Provider name
        name_label = QLabel(self._provider)
        name_label.setMinimumWidth(100)
        layout.addWidget(name_label)
        
        # Key display (masked)
        self._key_display = QLineEdit()
        self._key_display.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_display.setReadOnly(True)
        self._update_display()
        layout.addWidget(self._key_display, stretch=1)
        
        # Show/hide button
        self._show_btn = QPushButton("👁")
        self._show_btn.setFixedWidth(32)
        self._show_btn.setCheckable(True)
        self._show_btn.toggled.connect(self._toggle_visibility)
        layout.addWidget(self._show_btn)
        
        # Edit button
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.clicked.connect(self._on_edit)
        layout.addWidget(self._edit_btn)
        
        # Remove button
        self._remove_btn = QPushButton("🗑")
        self._remove_btn.setFixedWidth(32)
        self._remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(self._remove_btn)
    
    def _update_display(self):
        if self._key:
            self._key_display.setText("•" * min(len(self._key), 20))
        else:
            self._key_display.setText("(not set)")
            self._key_display.setStyleSheet("color: #565f89;")
    
    def _toggle_visibility(self, checked: bool):
        self._key_display.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
    
    def _on_edit(self):
        from PySide6.QtWidgets import QInputDialog
        new_key, ok = QInputDialog.getText(
            self, f"Edit {self._provider} API Key",
            "Enter new API key:", QLineEdit.EchoMode.Password, self._key
        )
        if ok and new_key.strip():
            self._key = new_key.strip()
            self._update_display()
            self.key_changed.emit(self._provider, self._key)
    
    def _on_remove(self):
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
            self, "Remove API Key",
            f"Remove {self._provider} API key?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._key = ""
            self._update_display()
            self.key_removed.emit(self._provider)
    
    def set_key(self, key: str):
        self._key = key
        self._update_display()
    
    def get_key(self) -> str:
        return self._key
    
    def get_provider(self) -> str:
        return self._provider