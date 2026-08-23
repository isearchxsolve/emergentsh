"""
Agent Builder Widgets — supporting widgets for the AgentBuilderDialog.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QVBoxLayout,
    QWidget,
)

from ....core.agent_registry import AgentRole
from ....core.models import (
    ModelCapability,
    ModelProvider,
    get_model_registry,
    get_model_selector_options,
)


# ════════════════════════════════════════════════════════════════════════════
# Model Selector Widget
# ════════════════════════════════════════════════════════════════════════════

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
        layout.addRow("Temperature:", self._temp_spin)
        
        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(1024, 128000)
        self._max_tokens_spin.setValue(32768)
        self._max_tokens_spin.setSingleStep(1024)
        layout.addRow("Max Tokens:", self._max_tokens_spin)
        
        self._reasoning_combo = QComboBox()
        self._reasoning_combo.addItems(["low", "medium", "high"])
        self._reasoning_combo.setCurrentText("medium")
        layout.addRow("Reasoning Effort:", self._reasoning_combo)
        
        layout.addWidget(adv_group)
        
        # Load models
        self._load_models()
    
    def _load_models(self):
        options = get_model_selector_options()
        self._model_combo.clear()
        for opt in options:
            self._model_combo.addItem(opt["label"], opt["value"])
    
    def _on_provider_changed(self, provider: str):
        current_model = self._model_combo.currentData()
        self._model_combo.clear()
        options = get_model_selector_options()
        for opt in options:
            if opt["provider"] == provider:
                self._model_combo.addItem(opt["label"], opt["value"])
        
        if current_model:
            idx = self._model_combo.findData(current_model)
            if idx >= 0:
                self._model_combo.setCurrentIndex(idx)
    
    def _on_model_changed(self, model_id: str):
        self._model_id = model_id
        registry = get_model_registry()
        model = registry.get_model(model_id)
        if model:
            info = f"Context: {model.context_window:,} tokens | "
            info += f"Max Output: {model.max_output_tokens:,} | "
            info += f"Free: {'Yes' if model.is_free else 'No'} | "
            info += f"Caps: {', '.join(c.value for c in model.capabilities)}"
            self._model_info.setText(info)
        self.model_changed.emit(model_id)


# ════════════════════════════════════════════════════════════════════════════
# Tool Selector Widget
# ════════════════════════════════════════════════════════════════════════════

class ToolSelectorWidget(QWidget):
    """Widget for selecting allowed tools."""
    
    tools_changed = Signal(set)
    
    AVAILABLE_TOOLS = {
        "read_file": "Read files from the workspace",
        "write_file": "Write/create files in the workspace",
        "search_files": "Search files by pattern",
        "run_command": "Execute shell commands",
        "list_directory": "List directory contents",
        "git": "Git operations (status, diff, commit, push)",
        "web_search": "Search the web",
        "http_request": "Make HTTP requests",
        "database": "Database queries",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_tools: Set[str] = set()
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Select all / none buttons
        btn_layout = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(self._select_all)
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(self._deselect_all)
        btn_layout.addWidget(select_all)
        btn_layout.addWidget(deselect_all)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Tool checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        for tool_id, description in self.AVAILABLE_TOOLS.items():
            cb = QCheckBox(f"{tool_id}: {description}")
            cb.setChecked(True)
            cb.stateChanged.connect(lambda state, tid=tool_id: self._on_tool_changed(tid, state))
            self._checkboxes[tool_id] = cb
            container_layout.addWidget(cb)
        
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
    
    def _select_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(True)
    
    def _deselect_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(False)
    
    def _on_tool_changed(self, tool_id: str, state: int):
        if state == Qt.Checked:
            self._selected_tools.add(tool_id)
        else:
            self._selected_tools.discard(tool_id)
        self.tools_changed.emit(self._selected_tools.copy())
    
    def set_tools(self, tools: Set[str]):
        self._selected_tools = set(tools)
        for tool_id, cb in self._checkboxes.items():
            cb.setChecked(tool_id in self._selected_tools)
    
    def get_tools(self) -> Set[str]:
        return self._selected_tools.copy()


# ════════════════════════════════════════════════════════════════════════════
# Capability Selector Widget
# ════════════════════════════════════════════════════════════════════════════

class CapabilitySelectorWidget(QWidget):
    """Widget for selecting model capabilities."""
    
    capabilities_changed = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._capabilities: List[str] = []
        self._checkboxes: Dict[str, QCheckBox] = {}
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        for cap in ModelCapability:
            cb = QCheckBox(cap.value.replace("_", " ").title())
            cb.setToolTip(f"Capability: {cap.value}")
            cb.stateChanged.connect(self._on_changed)
            self._checkboxes[cap.value] = cb
            container_layout.addWidget(cb)
        
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
    
    def _on_changed(self, state: int):
        self._capabilities = [cap for cap, cb in self._checkboxes.items() if cb.isChecked()]
        self.capabilities_changed.emit(self._capabilities)
    
    def set_capabilities(self, capabilities: List[str]):
        self._capabilities = list(capabilities)
        for cap, cb in self._checkboxes.items():
            cb.setChecked(cap in self._capabilities)
    
    def get_capabilities(self) -> List[str]:
        return self._capabilities.copy()


# ════════════════════════════════════════════════════════════════════════════
# Delegation Rules Widget
# ════════════════════════════════════════════════════════════════════════════

class DelegationWidget(QWidget):
    """Widget for configuring delegation rules (keyword → target role)."""
    
    rules_changed = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: Dict[str, List[str]] = {}
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Add rule form
        form_group = QGroupBox("Add Delegation Rule")
        form_layout = QFormLayout(form_group)
        
        self._keyword_edit = QLineEdit()
        self._keyword_edit.setPlaceholderText("e.g., 'deploy', 'test', 'design'")
        form_layout.addRow("Keyword:", self._keyword_edit)
        
        self._target_role_combo = QComboBox()
        for role in AgentRole:
            self._target_role_combo.addItem(role.value, role.value)
        form_layout.addRow("Target Role:", self._target_role_combo)
        
        add_btn = QPushButton("Add Rule")
        add_btn.clicked.connect(self._add_rule)
        form_layout.addRow(add_btn)
        
        layout.addWidget(form_group)
        
        # Rules list
        self._rules_list = QListWidget()
        self._rules_list.itemDoubleClicked.connect(self._edit_rule)
        layout.addWidget(QLabel("Current Rules:"))
        layout.addWidget(self._rules_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)
    
    def _add_rule(self):
        keyword = self._keyword_edit.text().strip()
        target_role = self._target_role_combo.currentData()
        
        if not keyword or not target_role:
            return
        
        if keyword not in self._rules:
            self._rules[keyword] = []
        
        if target_role not in self._rules[keyword]:
            self._rules[keyword].append(target_role)
        
        self._update_list()
        self._keyword_edit.clear()
        self.rules_changed.emit(self._rules.copy())
    
    def _update_list(self):
        self._rules_list.clear()
        for keyword, roles in self._rules.items():
            for role in roles:
                item = QListWidgetItem(f"{keyword} → {role}")
                item.setData(Qt.ItemDataRole.UserRole, (keyword, role))
                self._rules_list.addItem(item)
    
    def _edit_selected(self):
        item = self._rules_list.currentItem()
        if not item:
            return
        
        keyword, role = item.data(Qt.ItemDataRole.UserRole)
        self._keyword_edit.setText(keyword)
        idx = self._target_role_combo.findData(role)
        if idx >= 0:
            self._target_role_combo.setCurrentIndex(idx)
        
        self._rules[keyword].remove(role)
        if not self._rules[keyword]:
            del self._rules[keyword]
        self._update_list()
    
    def _edit_rule(self, item: QListWidgetItem):
        self._edit_selected()
    
    def _delete_selected(self):
        item = self._rules_list.currentItem()
        if not item:
            return
        
        keyword, role = item.data(Qt.ItemDataRole.UserRole)
        self._rules[keyword].remove(role)
        if not self._rules[keyword]:
            del self._rules[keyword]
        self._update_list()
        self.rules_changed.emit(self._rules.copy())
    
    def set_rules(self, rules: Dict[str, List[str]]):
        self._rules = {k: list(v) for k, v in rules.items()}
        self._update_list()
    
    def get_rules(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._rules.items()}


# ════════════════════════════════════════════════════════════════════════════
# Exports
# ════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ModelSelectorWidget",
    "ToolSelectorWidget",
    "CapabilitySelectorWidget",
    "DelegationWidget",
]