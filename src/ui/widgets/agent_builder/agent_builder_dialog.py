"""
AgentBuilderDialog — UI for creating and configuring custom AI agents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ....core.agent_registry import AgentCapability, AgentRole, ROLE_PROFILES
from ....core.models import (
    ModelCapability,
    ModelProvider,
    get_model_registry,
    get_model_selector_options,
)
from .agent_builder_widgets import (
    ToolSelectorWidget,
    CapabilitySelectorWidget,
    DelegationWidget,
)


@dataclass
class AgentConfig:
    """Configuration for a custom agent."""
    role: str  # Custom role identifier
    name: str  # Display name
    description: str
    
    # Model settings
    model_id: str
    temperature: float = 0.2
    max_tokens: int = 32768
    reasoning_effort: str = "medium"  # low, medium, high
    
    # Capabilities & tools
    allowed_tools: Set[str] = None
    capabilities: List[str] = None
    
    # Behavior
    system_prompt: str = ""
    system_prompt_suffix: str = ""
    delegation_rules: Dict[str, str] = None  # keyword -> target role
    
    # Constraints
    max_concurrent: int = 1
    timeout_seconds: int = 300
    
    def __post_init__(self):
        if self.allowed_tools is None:
            self.allowed_tools = {"read_file", "write_file", "search_files", "run_command"}
        if self.capabilities is None:
            self.capabilities = []
        if self.delegation_rules is None:
            self.delegation_rules = {}


class ModelSelectorWidget(QWidget):
    """Widget for selecting and configuring an LLM model."""
    
    model_changed = Signal(str)  # model_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model_id = ""
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Provider selector
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItems([p.value for p in ModelProvider])
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self._provider_combo)
        layout.addLayout(provider_layout)
        
        # Model selector
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(300)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addWidget(self._model_combo)
        layout.addLayout(model_layout)
        
        # Model info
        self._model_info = QLabel()
        self._model_info.setWordWrap(True)
        self._model_info.setStyleSheet("color: #565f89; font-size: 11px;")
        layout.addWidget(self._model_info)
        
        # Advanced settings
        adv_group = QGroupBox("Advanced Settings")
        adv_layout = QFormLayout(adv_group)
        
        self._temp_spin = QSpinBox()
        self._temp_spin.setRange(0, 200)
        self._temp_spin.setValue(20)  # 0.2 * 100
        self._temp_spin.setSuffix(" (x0.01)")
        adv_layout.addRow("Temperature:", self._temp_spin)
        
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(1024, 128000)
        self._max_tokens_spin.setValue(32768)
        self._max_tokens_spin.setSingleStep(1024)
        adv_layout.addRow("Max Tokens:", self._max_tokens_spin)
        
        self._reasoning_combo = QComboBox()
        self._reasoning_combo.addItems(["low", "medium", "high"])
        self._reasoning_combo.setCurrentText("medium")
        adv_layout.addRow("Reasoning Effort:", self._reasoning_combo)
        
        layout.addWidget(adv_group)
        
        # Load models
        self._load_models()
    
    def _load_models(self):
        from ...core.models import get_model_selector_options
        options = get_model_selector_options()
        self._model_combo.clear()
        for opt in options:
            self._model_combo.addItem(opt["label"], opt["value"])
    
    def _on_provider_changed(self, provider: str):
        # Filter models by provider
        current_model = self._model_combo.currentData()
        self._model_combo.clear()
        from ...core.models import get_model_selector_options
        options = get_model_selector_options()
        for opt in get_model_selector_options():
            if opt["provider"] == provider:
                self._model_combo.addItem(opt["label"], opt["value"])
        
        # Try to restore previous selection
        if current_model:
            idx = self._model_combo.findData(current_model)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
    
    def _on_model_changed(self, model_id: str):
        self._model_id = model_id
        # Update model info
        from ...core.models import get_model_registry
        registry = get_model_registry()
        model = registry.get_model(model_id)
        if model:
            info = f"Context: {model.context_window:,} tokens | "
            info += f"Max Output: {model.max_output_tokens:,} | "
            info += f"Free: {'Yes' if model.is_free else 'No'} | "
            info += f"Caps: {', '.join(c.value for c in model.capabilities)}"
            self._model_info.setText(info)
        self.model_changed.emit(model_id)


class AgentBuilderDialog(QDialog):
    """
    Dialog for creating and configuring custom AI agents.
    
    Allows users to define custom agent roles with specific models,
    capabilities, tools, and delegation rules.
    """
    
    agent_created = Signal(dict)  # Emits the AgentConfig as dict
    
    def __init__(self, existing: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Custom Agent" if not existing else "Edit Agent")
        self.setMinimumSize(800, 700)
        self._existing = existing
        self._build_ui()
        
        if existing:
            self._load_config(existing)
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)
        
        # Tab 1: Basic Info
        self._tabs.addTab(self._create_basic_tab(), "Basic Info")
        
        # Tab 2: Model Configuration
        self._tabs.addTab(self._create_model_tab(), "Model Settings")
        
        # Tab 3: Capabilities & Tools
        self._tabs.addTab(self._create_tools_tab(), "Capabilities & Tools")
        
        # Tab 3: Delegation Rules
        self._tabs.addTab(self._create_delegation_tab(), "Delegation Rules")
        
        # Tab 4: Advanced
        self._tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _create_basic_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g., 'Security Auditor', 'Performance Optimizer'")
        layout.addRow("Agent Name:", self._name_edit)
        
        self._role_edit = QLineEdit()
        self._role_edit.setPlaceholderText("e.g., 'security_auditor', 'perf_optimizer'")
        layout.addRow("Role ID:", self._role_edit)
        
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        self._desc_edit.setPlaceholderText("Describe what this agent does...")
        layout.addRow("Description:", self._desc_edit)
        
        return widget
    
    def _create_model_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self._model_selector = ModelSelectorWidget()
        layout.addWidget(self._model_selector)
        
        # Temperature, max tokens, reasoning
        settings_group = QGroupBox("Generation Settings")
        settings_layout = QFormLayout(settings_group)
        
        self._temp_spin = QSpinBox()
        self._temp_spin.setRange(0, 200)
        self._temp_spin.setValue(20)
        self._temp_spin.setSuffix(" (x0.01)")
        settings_layout.addRow("Temperature:", self._temp_spin)
        
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(1024, 128000)
        self._max_tokens_spin.setValue(32768)
        self._max_tokens_spin.setSingleStep(1024)
        settings_layout.addRow("Max Tokens:", self._max_tokens_spin)
        
        self._reasoning_combo = QComboBox()
        self._reasoning_combo.addItems(["low", "medium", "high"])
        self._reasoning_combo.setCurrentText("medium")
        settings_layout.addRow("Reasoning Effort:", self._reasoning_combo)
        
        layout.addWidget(settings_group)
        layout.addStretch()
        
        return widget
    
    def _create_tools_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tools
        tools_group = QGroupBox("Allowed Tools")
        tools_layout = QVBoxLayout(tools_group)
        from .agent_builder_widgets import ToolSelectorWidget
        self._tool_selector = ToolSelectorWidget()
        self._tool_selector.tools_changed.connect(self._on_tools_changed)
        tools_layout.addWidget(self._tool_selector)
        layout.addWidget(tools_group)
        
        # Capabilities
        caps_group = QGroupBox("Model Capabilities")
        caps_layout = QVBoxLayout(caps_group)
        from .agent_builder_widgets import CapabilitySelectorWidget
        self._capability_selector = CapabilitySelectorWidget()
        self._capability_selector.capabilities_changed.connect(self._on_caps_changed)
        caps_layout.addWidget(self._capability_selector)
        layout.addWidget(caps_group)
        
        return widget
    
    def _create_delegation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        from .agent_builder_widgets import DelegationWidget
        self._delegation_widget = DelegationWidget()
        self._delegation_widget.rules_changed.connect(self._on_rules_changed)
        layout.addWidget(self._delegation_widget)
        
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self._system_prompt_edit = QTextEdit()
        self._system_prompt_edit.setPlaceholderText("Optional: Override default system prompt...")
        self._system_prompt_edit.setMaximumHeight(120)
        layout.addRow("Custom System Prompt:", self._system_prompt_edit)
        
        self._system_suffix_edit = QTextEdit()
        self._system_suffix_edit.setPlaceholderText("Optional: Append to default system prompt...")
        self._system_suffix_edit.setMaximumHeight(80)
        layout.addRow("System Prompt Suffix:", self._system_suffix_edit)
        
        self._max_concurrent_spin = QSpinBox()
        self._max_concurrent_spin.setRange(1, 10)
        self._max_concurrent_spin.setValue(1)
        layout.addRow("Max Concurrent Instances:", self._max_concurrent_spin)
        
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(30, 3600)
        self._timeout_spin.setValue(300)
        self._timeout_spin.setSuffix(" seconds")
        layout.addRow("Timeout:", self._timeout_spin)
        
        return widget
    
    def _on_tools_changed(self, tools: set):
        pass
    
    def _on_caps_changed(self, caps: list):
        pass
    
    def _on_rules_changed(self, rules: dict):
        pass
    
    def _load_config(self, config: dict):
        self._name_edit.setText(config.get("name", ""))
        self._role_edit.setText(config.get("role", ""))
        self._desc_edit.setPlainText(config.get("description", ""))
        model_id = config.get("model_id", "")
        if model_id:
            self._model_selector._model_combo.setCurrentText(model_id)
        self._temp_spin.setValue(int(config.get("temperature", 0.2) * 100))
        self._max_tokens_spin.setValue(config.get("max_tokens", 32768))
        self._reasoning_combo.setCurrentText(config.get("reasoning_effort", "medium"))
        
        from .agent_builder_widgets import ToolSelectorWidget
        # Note: tools and capabilities would need to be loaded from config
        # This is a simplified version
        
        self._system_prompt_edit.setPlainText(config.get("system_prompt", ""))
        self._system_suffix_edit.setPlainText(config.get("system_prompt_suffix", ""))
        self._max_concurrent_spin.setValue(config.get("max_concurrent", 1))
        self._timeout_spin.setValue(config.get("timeout_seconds", 300))
    
    def _on_accept(self):
        # Validate
        name = self._name_edit.text().strip()
        role = self._role_edit.text().strip()
        model_id = self._model_selector._model_id
        
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter an agent name.")
            return
        if not role:
            QMessageBox.warning(self, "Missing Role ID", "Please enter a role ID.")
            return
        if not model_id:
            QMessageBox.warning(self, "No Model Selected", "Please select a model.")
            return
        
        # Build config dict
        config = {
            "role": self._role_edit.text().strip(),
            "name": self._name_edit.text().strip(),
            "description": self._desc_edit.toPlainText().strip(),
            "model_id": self._model_selector._model_id,
            "temperature": self._temp_spin.value() / 100.0,
            "max_tokens": self._max_tokens_spin.value(),
            "reasoning_effort": self._reasoning_combo.currentText(),
            "allowed_tools": list(self._tool_selector.get_tools()),
            "capabilities": self._capability_selector.get_capabilities(),
            "system_prompt": self._system_prompt_edit.toPlainText().strip(),
            "system_prompt_suffix": self._system_suffix_edit.toPlainText().strip(),
            "delegation_rules": self._delegation_widget.get_rules(),
            "max_concurrent": self._max_concurrent_spin.value(),
            "timeout_seconds": self._timeout_spin.value(),
        }
        
        self.agent_created.emit(config)
        self.accept()


# Import at top level
from ....core.models import ModelProvider, ModelCapability