"""
ProjectWizard Dialog — main dialog for creating new projects.

Includes:
- TECH_STACKS: Predefined technology stack definitions
- TechStackSelector: Visual card-based stack selector
- ProfileSelector: Profile selection widget
- ProjectWizard: Multi-step wizard dialog
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.workspace import WorkspaceManager, get_workspace, Profile, Project
from ...core.agent_registry import AgentRole


# ════════════════════════════════════════════════════════════════════════════
# Tech Stack Definitions
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class TechStack:
    """Definition of a technology stack."""
    key: str
    name: str
    description: str
    frontend: str
    styling: str
    backend: Optional[str] = None
    database: Optional[str] = None
    auth: Optional[str] = None
    deployment: Optional[str] = None
    icon: str = "📦"
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


# Predefined tech stacks
TECH_STACKS: Dict[str, TechStack] = {
    "nextjs-tailwind": TechStack(
        key="nextjs-tailwind",
        name="Next.js + Tailwind CSS",
        description="Full-stack React framework with utility-first CSS. Best for web apps.",
        frontend="nextjs",
        styling="tailwind",
        backend="nextjs-api",
        database="postgresql",
        auth="nextauth",
        deployment="vercel",
        tags=["web", "fullstack", "react", "typescript"],
    ),
    "nextjs-shadcn": TechStack(
        key="nextjs-shadcn",
        name="Next.js + shadcn/ui",
        description="Next.js with beautiful, accessible component library.",
        frontend="nextjs",
        styling="tailwind",
        backend="nextjs-api",
        database="postgresql",
        auth="nextauth",
        deployment="vercel",
        tags=["web", "fullstack", "react", "components"],
    ),
    "vite-react-tailwind": TechStack(
        key="vite-react-tailwind",
        name="Vite + React + Tailwind",
        description="Lightning-fast SPA setup. Best for client-heavy apps.",
        frontend="vite-react",
        styling="tailwind",
        backend="fastapi",
        database="postgresql",
        auth="jwt",
        deployment="netlify",
        tags=["web", "spa", "react", "typescript"],
    ),
    "expo-react-native": TechStack(
        key="expo-react-native",
        name="Expo + React Native",
        description="Cross-platform mobile apps with native performance.",
        frontend="expo",
        styling="nativewind",
        backend="fastapi",
        database="postgresql",
        auth="jwt",
        deployment="eas",
        tags=["mobile", "ios", "android", "react-native"],
    ),
    "fastapi-react": TechStack(
        key="fastapi-react",
        name="FastAPI + React",
        description="Python backend with React frontend. Separate services.",
        frontend="vite-react",
        styling="tailwind",
        backend="fastapi",
        database="postgresql",
        auth="jwt",
        deployment="fly",
        tags=["web", "api", "python", "react"],
    ),
    "django-react": TechStack(
        key="django-react",
        name="Django + React",
        description="Batteries-included Python backend with React frontend.",
        frontend="vite-react",
        styling="tailwind",
        backend="django",
        database="postgresql",
        auth="django-auth",
        deployment="railway",
        tags=["web", "api", "python", "django"],
    ),
    "sveltekit-tailwind": TechStack(
        key="sveltekit-tailwind",
        name="SvelteKit + Tailwind",
        description="Compiler-based framework with minimal boilerplate.",
        frontend="sveltekit",
        styling="tailwind",
        backend="sveltekit-api",
        database="sqlite",
        auth="lucia",
        deployment="vercel",
        tags=["web", "fullstack", "svelte"],
    ),
    "nuxt-tailwind": TechStack(
        key="nuxt-tailwind",
        name="Nuxt 3 + Tailwind",
        description="Vue.js full-stack framework with auto-imports.",
        frontend="nuxt",
        styling="tailwind",
        backend="nuxt-server",
        database="postgresql",
        auth="nuxt-auth",
        deployment="vercel",
        tags=["web", "fullstack", "vue"],
    ),
    "remix-tailwind": TechStack(
        key="remix-tailwind",
        name="Remix + Tailwind",
        description="Web standards-based full-stack React framework.",
        frontend="remix",
        styling="tailwind",
        backend="remix",
        database="postgresql",
        auth="remix-auth",
        deployment="fly",
        tags=["web", "fullstack", "react"],
    ),
}


def get_all_tech_stacks() -> List[TechStack]:
    """Get all available tech stacks."""
    return list(TECH_STACKS.values())


def get_tech_stacks_by_tag(tag: str) -> List[TechStack]:
    """Filter stacks by tag."""
    return [s for s in TECH_STACKS.values() if tag in s.tags]


# ════════════════════════════════════════════════════════════════════════════
# Tech Stack Selector Widget
# ════════════════════════════════════════════════════════════════════════════

class TechStackCard(QFrame):
    """Visual card for a tech stack option."""

    def __init__(self, stack: TechStack, parent=None):
        super().__init__(parent)
        self._stack = stack
        self.setObjectName("TechStackCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Icon + Name
        header = QHBoxLayout()
        icon_label = QLabel(stack.icon)
        icon_label.setStyleSheet("font-size: 28px;")
        header.addWidget(icon_label)

        name_label = QLabel(stack.name)
        name_label.setObjectName("StackName")
        name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #c0caf5;")
        header.addWidget(name_label)
        header.addStretch()
        layout.addLayout(header)

        # Description
        desc_label = QLabel(stack.description)
        desc_label.setObjectName("StackDescription")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #a9b1d6; font-size: 13px;")
        layout.addWidget(desc_label)

        # Tags
        tags_layout = QHBoxLayout()
        for tag in stack.tags:
            tag_label = QLabel(tag)
            tag_label.setObjectName("StackTag")
            tag_label.setStyleSheet(
                "background-color: #1f2335; color: #7aa2f7; "
                "font-size: 11px; padding: 2px 8px; border-radius: 10px;"
            )
            tags_layout.addWidget(tag_label)
        tags_layout.addStretch()
        layout.addLayout(tags_layout)

        # Tech details
        details = []
        details.append(f"Frontend: {stack.frontend}")
        if stack.styling:
            details.append(f"Styling: {stack.styling}")
        if stack.backend:
            details.append(f"Backend: {stack.backend}")
        if stack.database:
            details.append(f"DB: {stack.database}")

        details_label = QLabel(" · ".join(details))
        details_label.setObjectName("StackDetails")
        details_label.setStyleSheet("color: #565f89; font-size: 11px; font-family: monospace;")
        layout.addWidget(details_label)

    @property
    def stack(self) -> TechStack:
        return self._stack

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    # Signal
    clicked = Signal()


class TechStackSelector(QWidget):
    """
    Widget for selecting a technology stack from visual cards.

    Emits stack_selected(str) when a stack is chosen.
    """

    stack_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_card: Optional[TechStackCard] = None
        self._cards: List[TechStackCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self._grid_layout = QVBoxLayout(container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setContentsMargins(12, 12, 12, 12)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        self._build_cards()

    def _build_cards(self) -> None:
        """Create cards for all tech stacks."""
        stacks = get_all_tech_stacks()
        for stack in stacks:
            card = TechStackCard(stack)
            card.clicked.connect(lambda s=stack, c=card: self._on_card_clicked(s, c))
            self._cards.append(card)
            self._grid_layout.addWidget(card)

        self._grid_layout.addStretch()

    def _on_card_clicked(self, stack: TechStack, card: TechStackCard) -> None:
        # Update selection visual
        if self._selected_card:
            self._selected_card.setProperty("selected", False)
            self._selected_card.style().unpolish(self._selected_card)
            self._selected_card.style().polish(self._selected_card)

        self._selected_card = card
        card.setProperty("selected", True)
        card.style().unpolish(card)
        card.style().polish(card)

        self.stack_selected.emit(stack.key)

    def get_selected_stack(self) -> Optional[TechStack]:
        if self._selected_card:
            return self._selected_card.stack
        return None

    def set_selected_stack(self, stack_key: str) -> bool:
        """Programmatically select a stack by key."""
        for card in self._cards:
            if card.stack.key == stack_key:
                self._on_card_clicked(card.stack, card)
                return True
        return False


# ════════════════════════════════════════════════════════════════════════════
# Profile Selector Widget
# ════════════════════════════════════════════════════════════════════════════

class ProfileSelector(QWidget):
    """
    Widget for selecting an AI profile from the workspace.

    Emits profile_selected(int) with profile ID when selected.
    """

    profile_selected = Signal(int)

    def __init__(self, workspace, parent=None):
        super().__init__(parent)
        self._workspace = workspace
        self._selected_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self.refresh()

    def refresh(self) -> None:
        """Reload profiles from workspace."""
        self._list.clear()
        profiles = self._workspace.list_profiles()
        for p in profiles:
            model_info = p.models.get(p.default_model, {})
            model_name = model_info.get("name", p.default_model)
            item_text = f"{p.name}\n  Model: {model_name}  ·  RPM: {p.rpm}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_id = profile_id
        self.profile_selected.emit(profile_id)

    def get_selected_profile_id(self) -> Optional[int]:
        return self._selected_id

    def set_selected_profile(self, profile_id: int) -> bool:
        """Programmatically select a profile."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == profile_id:
                self._list.setCurrentItem(item)
                self._selected_id = profile_id
                return True
        return False


# ════════════════════════════════════════════════════════════════════════════
# Project Wizard Dialog
# ════════════════════════════════════════════════════════════════════════════

class ProjectWizard(QDialog):
    """
    Multi-step wizard for creating a new project.

    Steps:
    1. Basic Info (name, description, directory)
    2. Tech Stack Selection
    3. Profile Selection
    4. Advanced Options (git, deployment, environment)
    5. Review & Create
    """

    project_created = Signal(Project)  # Emitted when project is successfully created

    def __init__(self, workspace: Optional[WorkspaceManager] = None, parent=None):
        super().__init__(parent)
        self._workspace = workspace or get_workspace()
        self.setWindowTitle("New Project Wizard")
        self.setMinimumSize(800, 600)
        self.setModal(True)

        self._current_step = 0
        self._steps = []  # Will hold step widgets
        self._step_data = {}  # Collected data

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with step indicator
        self._header = QWidget()
        self._header.setObjectName("WizardHeader")
        header_layout = QVBoxLayout(self._header)
        header_layout.setContentsMargins(24, 16, 24, 16)

        self._step_indicator = QLabel()
        self._step_indicator.setObjectName("StepIndicator")
        header_layout.addWidget(self._step_indicator)

        self._step_title = QLabel()
        self._step_title.setObjectName("StepTitle")
        header_layout.addWidget(self._step_title)

        self._step_description = QLabel()
        self._step_description.setObjectName("StepDescription")
        header_layout.addWidget(self._step_description)

        layout.addWidget(self._header)

        # Content area
        self._content = QWidget()
        self._content.setObjectName("WizardContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 0, 24, 0)
        layout.addWidget(self._content, stretch=1)

        # Navigation buttons
        self._button_box = QDialogButtonBox()
        self._button_box.setObjectName("WizardButtons")

        self._back_btn = self._button_box.addButton(
            "Back", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._next_btn = self._button_box.addButton(
            "Next", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._finish_btn = self._button_box.addButton(
            "Create Project", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._finish_btn.setVisible(False)

        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._finish_btn.clicked.connect(self._finish)

        self._button_box.rejected.connect(self.reject)

        layout.addWidget(self._button_box)

        # Create steps
        self._create_steps()
        self._show_step(0)

    def _create_steps(self) -> None:
        """Create all wizard step widgets."""
        self._steps = [
            self._create_step_basic_info(),
            self._create_step_tech_stack(),
            self._create_step_profile(),
            self._create_step_advanced(),
            self._create_step_review(),
        ]

    def _create_step_basic_info(self) -> QWidget:
        """Step 1: Basic project information."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Project name
        name_group = QGroupBox("Project Name")
        name_layout = QFormLayout(name_group)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My Awesome App")
        self._name_edit.textChanged.connect(self._validate_step)
        name_layout.addRow("Name:", self._name_edit)
        layout.addWidget(name_group)

        # Description
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout(desc_group)
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Brief description of what this project does...")
        self._desc_edit.setMaximumHeight(100)
        desc_layout.addWidget(self._desc_edit)
        layout.addWidget(desc_group)

        # Root directory
        dir_group = QGroupBox("Project Directory")
        dir_layout = QHBoxLayout(dir_group)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(os.path.expanduser("~/Projects/my-app"))
        self._dir_edit.setText(os.path.expanduser("~/Projects"))
        dir_layout.addWidget(self._dir_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_btn)
        layout.addWidget(dir_group)

        # Target platform
        target_group = QGroupBox("Target Platform")
        target_layout = QHBoxLayout(target_group)
        self._target_combo = QComboBox()
        self._target_combo.addItems(["Web Application", "Mobile Application", "Both (Web + Mobile)"])
        self._target_combo.setCurrentIndex(0)
        target_layout.addWidget(self._target_combo)
        layout.addWidget(target_group)

        layout.addStretch()
        return widget

    def _create_step_tech_stack(self) -> QWidget:
        """Step 2: Tech stack selection."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Choose a technology stack for your project. Each stack includes frontend, backend, and tooling pre-configured.")
        label.setWordWrap(True)
        label.setStyleSheet("color: #a9b1d6; margin-bottom: 12px;")
        layout.addWidget(label)

        self._tech_stack_selector = TechStackSelector()
        self._tech_stack_selector.stack_selected.connect(self._on_stack_selected)
        layout.addWidget(self._tech_stack_selector)

        # Show stack details
        self._stack_details = QLabel()
        self._stack_details.setObjectName("StackDetails")
        self._stack_details.setWordWrap(True)
        self._stack_details.setStyleSheet("color: #565f89; font-size: 12px; padding: 12px; background: #16161e; border-radius: 6px;")
        self._stack_details.setVisible(False)
        layout.addWidget(self._stack_details)

        layout.addStretch()
        return widget

    def _create_step_profile(self) -> QWidget:
        """Step 3: Profile selection."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Select the AI profile to use for this project. Profiles define the model, API key, and rate limits.")
        label.setWordWrap(True)
        label.setStyleSheet("color: #a9b1d6; margin-bottom: 12px;")
        layout.addWidget(label)

        self._profile_selector = ProfileSelector(self._workspace)
        self._profile_selector.profile_selected.connect(self._on_profile_selected)
        layout.addWidget(self._profile_selector)

        # New profile button
        new_profile_btn = QPushButton("➕ Create New Profile")
        new_profile_btn.clicked.connect(self._create_new_profile)
        new_profile_btn.setStyleSheet("margin-top: 8px;")
        layout.addWidget(new_profile_btn)

        layout.addStretch()
        return widget

    def _create_step_advanced(self) -> QWidget:
        """Step 4: Advanced options."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Git options
        git_group = QGroupBox("Git Repository")
        git_layout = QFormLayout(git_group)

        self._git_url_edit = QLineEdit()
        self._git_url_edit.setPlaceholderText("https://github.com/username/repo.git (optional)")
        git_layout.addRow("Remote URL:", self._git_url_edit)

        self._git_branch_edit = QLineEdit()
        self._git_branch_edit.setText("main")
        git_layout.addRow("Default Branch:", self._git_branch_edit)

        self._init_git_check = QPushButton("Initialize Git Repository")
        self._init_git_check.setCheckable(True)
        self._init_git_check.setChecked(True)
        git_layout.addRow(self._init_git_check)
        layout.addWidget(git_group)

        # Deployment target
        deploy_group = QGroupBox("Deployment Target")
        deploy_layout = QFormLayout(deploy_group)

        self._deploy_combo = QComboBox()
        self._deploy_combo.addItems([
            "Vercel", "Netlify", "Fly.io", "Railway", "Render",
            "AWS Amplify", "Cloudflare Pages", "Custom VPC"
        ])
        self._deploy_combo.setCurrentIndex(0)
        deploy_layout.addRow("Platform:", self._deploy_combo)
        layout.addWidget(deploy_group)

        # Environment variables
        env_group = QGroupBox("Environment Variables")
        env_layout = QVBoxLayout(env_group)
        self._env_edit = QTextEdit()
        self._env_edit.setPlaceholderText("KEY=VALUE\nNEXT_PUBLIC_API_URL=https://api.example.com\nDATABASE_URL=postgresql://...")
        self._env_edit.setMaximumHeight(100)
        env_layout.addWidget(self._env_edit)
        layout.addWidget(env_group)

        layout.addStretch()
        return widget

    def _create_step_review(self) -> QWidget:
        """Step 5: Review & Create."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Review your project configuration:")
        label.setObjectName("StepLabel")
        layout.addWidget(label)

        self._review_text = QTextEdit()
        self._review_text.setReadOnly(True)
        self._review_text.setObjectName("ReviewText")
        layout.addWidget(self._review_text, stretch=1)

        return widget

    def _browse_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if path:
            self._dir_edit.setText(path)

    def _on_stack_selected(self, stack_key: str) -> None:
        self._step_data["tech_stack_key"] = stack_key
        stack = TECH_STACKS.get(stack_key)
        if stack:
            details = (
                f"<b>{stack.name}</b><br>"
                f"{stack.description}<br><br>"
                f"<b>Frontend:</b> {stack.frontend}  ·  "
                f"<b>Styling:</b> {stack.styling}  ·  "
                f"<b>Backend:</b> {stack.backend or 'N/A'}<br>"
                f"<b>Database:</b> {stack.database or 'N/A'}  ·  "
                f"<b>Auth:</b> {stack.auth or 'N/A'}  ·  "
                f"<b>Deploy:</b> {stack.deployment or 'N/A'}"
            )
            self._stack_details.setHtml(details)
            self._stack_details.setVisible(True)

    def _on_profile_selected(self, profile_id: int) -> None:
        self._step_data["profile_id"] = profile_id

    def _create_new_profile(self) -> None:
        from .profile_dialog import ProfileDialog
        dlg = ProfileDialog(parent=self)
        if dlg.exec():
            data = dlg.get_data()
            pid = self._workspace.create_profile(
                name=data["name"],
                api_key=data["key"],
                default_model=data["default_model"],
                rpm=data["rpm"],
            )
            self._profile_selector.refresh()
            self._profile_selector.set_selected_profile(pid)
            self._step_data["profile_id"] = pid

    def _go_back(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self._show_step(self._current_step)

    def _go_next(self) -> None:
        # Validate current step
        if self._current_step == 0:
            if not self._name_edit.text().strip():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Missing Name", "Please enter a project name.")
                return
            if not self._dir_edit.text().strip():
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Missing Directory", "Please select a project directory.")
                return
            self._step_data["name"] = self._name_edit.text().strip()
            self._step_data["description"] = self._desc_edit.toPlainText().strip()
            self._step_data["root_dir"] = self._dir_edit.text().strip()

        elif self._current_step == 1:
            if "tech_stack_key" not in self._step_data:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "No Tech Stack", "Please select a technology stack.")
                return
            target_map = {0: "web", 1: "mobile", 2: "both"}
            self._step_data["target"] = target_map.get(self._target_combo.currentIndex(), "web")

        elif self._current_step == 2:
            if "profile_id" not in self._step_data:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "No Profile", "Please select an AI profile.")
                return

        elif self._current_step == 3:
            self._step_data["git_url"] = self._git_url_edit.text().strip()
            self._step_data["git_branch"] = self._git_branch_edit.text().strip()
            self._step_data["init_git"] = self._init_git_check.isChecked()
            self._step_data["deploy_target"] = self._deploy_combo.currentText()
            # Parse env vars
            env_text = self._env_edit.toPlainText().strip()
            env_vars = {}
            for line in env_text.split("\n"):
                line = line.strip()
                if line and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
            self._step_data["environment"] = env_vars

        if self._current_step < len(self._steps) - 1:
            self._current_step += 1
            self._show_step(self._current_step)

    def _show_step(self, index: int) -> None:
        """Display the step at the given index."""
        # Clear current content
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add new step widget
        self._content_layout.addWidget(self._steps[index])
        self._current_step = index

        # Update header
        step_names = [
            ("1", "Basic Information", "Enter your project name, description, and location."),
            ("2", "Technology Stack", "Choose the frameworks and tools for your project."),
            ("3", "AI Profile", "Select the AI model and rate limits for this project."),
            ("4", "Advanced Options", "Configure Git, deployment, and environment variables."),
            ("5", "Review & Create", "Review all settings before creating the project."),
        ]
        num, title, desc = step_names[index]
        self._step_indicator.setText(f"Step {num} of {len(step_names)}")
        self._step_title.setText(title)
        self._step_description.setText(desc)

        # Update buttons
        self._back_btn.setEnabled(index > 0)
        is_last = (index == len(self._steps) - 1)
        self._next_btn.setVisible(not is_last)
        self._finish_btn.setVisible(is_last)

        if is_last:
            self._update_review()

    def _update_review(self) -> None:
        """Update the review step with collected data."""
        stack_key = self._step_data.get("tech_stack_key", "nextjs-tailwind")
        stack = TECH_STACKS.get(stack_key, TECH_STACKS["nextjs-tailwind"])
        profile = None
        if "profile_id" in self._step_data:
            profile = self._workspace.get_profile(self._step_data["profile_id"])

        target_map = {"web": "Web Application", "mobile": "Mobile Application", "both": "Web + Mobile"}

        review = (
            f"<b>Project Name:</b> {self._step_data.get('name', 'N/A')}<br>"
            f"<b>Description:</b> {self._step_data.get('description', 'N/A') or '(none)'}<br>"
            f"<b>Directory:</b> {self._step_data.get('root_dir', 'N/A')}<br><br>"
            f"<b>Tech Stack:</b> {stack.name}<br>"
            f"<b>Frontend:</b> {stack.frontend}  ·  "
            f"<b>Styling:</b> {stack.styling}  ·  "
            f"<b>Backend:</b> {stack.backend or 'N/A'}<br>"
            f"<b>Database:</b> {stack.database or 'N/A'}  ·  "
            f"<b>Auth:</b> {stack.auth or 'N/A'}<br>"
            f"<b>Target:</b> {target_map.get(self._step_data.get('target', 'web'), 'Web')}<br><br>"
            f"<b>Profile:</b> {profile.name if profile else 'N/A'}<br>"
            f"<b>Model:</b> {profile.models.get(profile.default_model, {}).get('name', 'N/A') if profile else 'N/A'}<br>"
            f"<b>RPM:</b> {profile.rpm if profile else 'N/A'}<br><br>"
            f"<b>Git:</b> {self._step_data.get('git_url', '(none)')}<br>"
            f"<b>Branch:</b> {self._step_data.get('git_branch', 'main')}<br>"
            f"<b>Deploy Target:</b> {self._step_data.get('deploy_target', 'N/A')}<br>"
            f"<b>Environment Vars:</b> {len(self._step_data.get('environment', {}))} defined"
        )
        self._review_text.setHtml(review)

    def _finish(self) -> None:
        """Create the project and emit signal."""
        try:
            project = Project(
                id=f"proj-{abs(hash(self._step_data.get('name', ''))) % 1000000:06d}",
                name=self._step_data.get("name", "Untitled Project"),
                description=self._step_data.get("description", ""),
                root_dir=self._step_data.get("root_dir", str(Path.cwd())),
                tech_stack={
                    "frontend": TECH_STACKS[self._step_data["tech_stack_key"]].frontend,
                    "styling": TECH_STACKS[self._step_data["tech_stack_key"]].styling,
                    "backend": TECH_STACKS[self._step_data["tech_stack_key"]].backend,
                    "database": TECH_STACKS[self._step_data["tech_stack_key"]].database,
                    "auth": TECH_STACKS[self._step_data["tech_stack_key"]].auth,
                    "deployment": TECH_STACKS[self._step_data["tech_stack_key"]].deployment,
                },
                target=self._step_data.get("target", "web"),
                profile_id=self._step_data.get("profile_id", 1),
                git_repo_url=self._step_data.get("git_url") or None,
                git_branch=self._step_data.get("git_branch", "main"),
                deploy_target=self._step_data.get("deploy_target"),
                environment=self._step_data.get("environment", {}),
            )
            self._workspace.create_project(project)
            self.project_created.emit(project)
            self.accept()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error Creating Project", f"Failed to create project: {e}")

    def get_project_data(self) -> Dict:
        """Return the collected project data."""
        stack_key = self._step_data.get("tech_stack_key", "nextjs-tailwind")
        stack = TECH_STACKS[stack_key]

        return {
            "name": self._step_data.get("name", "Untitled Project"),
            "description": self._step_data.get("description", ""),
            "root_dir": self._step_data.get("root_dir", str(Path.cwd())),
            "tech_stack": {
                "frontend": stack.frontend,
                "styling": stack.styling,
                "backend": stack.backend,
                "database": stack.database,
                "auth": stack.auth,
                "deployment": stack.deployment,
            },
            "target": self._step_data.get("target", "web"),
            "profile_id": self._step_data.get("profile_id"),
        }