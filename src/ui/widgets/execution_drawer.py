"""
ExecutionDrawer — collapsible terminal pane showing live tool output.

The drawer sits at the bottom of the main window.  It can be toggled
visible/hidden and shows a monospace log of all tool executions,
including live stdout/stderr from ``run_command``.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ExecutionDrawer(QWidget):
    """
    Collapsible pane with a live terminal-style log.

    Signals from the agent (``tool_start``, ``tool_executing``,
    ``tool_output``, ``tool_result``) are connected to the methods
    below by the main window.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ExecutionDrawer")
        self.setFixedHeight(220)
        self._visible = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar ─────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(32)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 8, 0)

        title = QLabel("⚙  Execution / Terminal")
        title.setObjectName("DrawerTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(70)
        self._clear_btn.clicked.connect(self.clear)
        header_layout.addWidget(self._clear_btn)

        self._toggle_btn = QPushButton("▾")
        self._toggle_btn.setFixedWidth(32)
        self._toggle_btn.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self._toggle_btn)

        layout.addWidget(header)

        # ── Terminal output ────────────────────────────────────────
        self._terminal = QPlainTextEdit()
        self._terminal.setObjectName("TerminalOutput")
        self._terminal.setReadOnly(True)
        self._terminal.setMaximumBlockCount(10000)
        layout.addWidget(self._terminal)

    # ------------------------------------------------------------------
    # Public API (connected to agent signals)
    # ------------------------------------------------------------------
    def on_tool_start(self, tool_name: str) -> None:
        self._terminal.appendPlainText(f"── Preparing: {tool_name} ──")

    def on_tool_executing(self, tool_name: str, args_json: str) -> None:
        preview = args_json[:200]
        if len(args_json) > 200:
            preview += "..."
        self._terminal.appendPlainText(f"$ {tool_name}  {preview}")

    def on_tool_output(self, line: str) -> None:
        """Live stdout/stderr line from run_command."""
        # Use appendPlainText without extra newline for streaming lines
        cursor = self._terminal.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(line + "\n")
        self._terminal.setTextCursor(cursor)
        self._terminal.ensureCursorVisible()

    def on_tool_result(self, tool_name: str, result: str) -> None:
        """Final result of a tool execution."""
        lines = result.split("\n")
        for line in lines[:50]:
            self._terminal.appendPlainText(f"  │ {line}")
        if len(lines) > 50:
            self._terminal.appendPlainText(
                f"  │ ... ({len(lines) - 50} more lines)"
            )
        self._terminal.appendPlainText(
            f"── {tool_name} completed ──\n"
        )

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self._terminal.clear()

    def toggle_collapse(self) -> None:
        self._visible = not self._visible
        if self._visible:
            self._terminal.show()
            self.setFixedHeight(220)
            self._toggle_btn.setText("▾")
        else:
            self._terminal.hide()
            self.setFixedHeight(32)
            self._toggle_btn.setText("▴")

    @property
    def is_visible(self) -> bool:
        return self._visible
