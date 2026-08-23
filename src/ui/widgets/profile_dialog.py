"""
ProfileDialog — modal dialog for creating / editing agent profiles.

Collects: profile name, NVIDIA API key, default model, and RPM limit.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from ...core.config import DEFAULT_PROFILE_TEMPLATE


class ProfileDialog(QDialog):
    """
    Modal dialog for creating or editing a profile.

    Returns a dict with keys: name, key, default_model, rpm, models
    via :meth:`get_data` after :meth:`exec` returns ``Accepted``.
    """

    def __init__(self, existing: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profile Setup")
        self.setMinimumWidth(420)
        self._existing = existing

        layout = QVBoxLayout(self)

        # ── Form ────────────────────────────────────────────────────
        form_group = QGroupBox("Profile Details")
        form_layout = QFormLayout(form_group)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. My NVIDIA NIM")
        form_layout.addRow("Profile Name:", self._name_edit)

        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("nvapi-...")
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("NVIDIA API Key:", self._key_edit)

        self._model_combo = QComboBox()
        for mk, mv in DEFAULT_PROFILE_TEMPLATE["models"].items():
            self._model_combo.addItem(
                f"{mv['name']}  ({mv['id']})", mk
            )
        form_layout.addRow("Default Model:", self._model_combo)

        self._rpm_spin = QSpinBox()
        self._rpm_spin.setRange(1, 200)
        self._rpm_spin.setValue(40)
        self._rpm_spin.setSuffix(" RPM")
        form_layout.addRow("Rate Limit:", self._rpm_spin)

        layout.addWidget(form_group)

        # ── Buttons ────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # ── Pre-fill if editing ────────────────────────────────────
        if existing:
            self._name_edit.setText(existing.get("name", ""))
            self._key_edit.setText(existing.get("key", ""))
            dm = existing.get("default_model", "glm")
            for i in range(self._model_combo.count()):
                if self._model_combo.itemData(i) == dm:
                    self._model_combo.setCurrentIndex(i)
                    break
            self._rpm_spin.setValue(int(existing.get("rpm", 40)))

    # ------------------------------------------------------------------
    def get_data(self) -> dict:
        model_key = self._model_combo.currentData()
        return {
            "name": self._name_edit.text().strip() or "Unnamed",
            "key": self._key_edit.text().strip(),
            "default_model": model_key,
            "rpm": float(self._rpm_spin.value()),
            "models": DEFAULT_PROFILE_TEMPLATE["models"],
        }
