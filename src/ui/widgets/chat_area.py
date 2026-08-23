"""
ChatMessageWidget — a single message bubble in the chat area.

Supports four message types: user, assistant, tool, and reasoning.
Each renders with a distinct visual style defined in the theme QSS.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChatMessageWidget(QFrame):
    """A single chat message bubble."""

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_TOOL = "tool"
    ROLE_REASONING = "reasoning"

    ROLE_LABELS = {
        ROLE_USER: "You",
        ROLE_ASSISTANT: "Assistant",
        ROLE_TOOL: "Tool",
        ROLE_REASONING: "Thinking",
    }

    ROLE_OBJECT_NAMES = {
        ROLE_USER: "UserBubble",
        ROLE_ASSISTANT: "AssistantBubble",
        ROLE_TOOL: "ToolBubble",
        ROLE_REASONING: "ReasoningBubble",
    }

    # Role → role-tag color mapping (mirrors DESIGN.md §4.1)
    ROLE_TAG_COLORS = {
        ROLE_USER: "#7aa2f7",        # accent
        ROLE_ASSISTANT: "#9ece6a",   # ok
        ROLE_TOOL: "#e0af68",         # warn
        ROLE_REASONING: "#bb9af7",    # think
    }

    # Error bubble reuses AssistantBubble frame with an err role tag
    ROLE_ERROR = "error"
    ROLE_TAG_COLORS[ROLE_ERROR] = "#f7768e"  # err

    ROLE_LABEL_OBJECT_NAMES = {
        ROLE_USER: "RoleUser",
        ROLE_ASSISTANT: "RoleAssistant",
        ROLE_TOOL: "RoleTool",
        ROLE_REASONING: "RoleReasoning",
    }

    def __init__(self, role: str, content: str = "", parent=None):
        super().__init__(parent)
        self._role = role
        self._content_parts: list[str] = [content] if content else []

        self.setObjectName(self.ROLE_OBJECT_NAMES.get(role, "AssistantBubble"))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Role label
        role_label = QLabel(self.ROLE_LABELS.get(role, role))
        role_label.setObjectName(
            self.ROLE_LABEL_OBJECT_NAMES.get(role, "RoleAssistant")
        )
        role_label.setObjectName("RoleLabel")
        # Apply role-specific class via styleSheet override
        role_label.setStyleSheet(
            self._role_label_style(role)
        )
        layout.addWidget(role_label)

        # Content label
        self.content_label = QLabel(content)
        self.content_label.setObjectName(
            "ReasoningContent" if role == self.ROLE_REASONING else "ContentLabel"
        )
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.TextFormat.PlainText)
        self.content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.content_label)

    # ------------------------------------------------------------------
    @staticmethod
    def _role_label_style(role: str) -> str:
        colours = {
            ChatMessageWidget.ROLE_USER: "#7aa2f7",
            ChatMessageWidget.ROLE_ASSISTANT: "#9ece6a",
            ChatMessageWidget.ROLE_TOOL: "#e0af68",
            ChatMessageWidget.ROLE_REASONING: "#bb9af7",
        }
        c = colours.get(role, "#c0caf5")
        return (
            f"font-size: 11px; font-weight: bold; padding: 2px 0; "
            f"color: {c};"
        )

    # ------------------------------------------------------------------
    def append_text(self, text: str) -> None:
        """Append streaming text to the content label."""
        self._content_parts.append(text)
        full = "".join(self._content_parts)
        self.content_label.setText(full)

    def set_text(self, text: str) -> None:
        """Replace the entire content."""
        self._content_parts = [text]
        self.content_label.setText(text)

    @property
    def role(self) -> str:
        return self._role

    @property
    def full_text(self) -> str:
        return "".join(self._content_parts)


class ChatAreaWidget(QWidget):
    """
    Scrollable chat container that holds ChatMessageWidget instances.

    New messages are appended at the bottom and the view auto-scrolls.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatScroll")

        self._scroll = QVBoxLayout(self)
        self._scroll.setContentsMargins(0, 0, 0, 0)
        self._scroll.setSpacing(2)

        # Inner container that grows with content
        self._container = QWidget()
        self._container.setObjectName("ChatContainer")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(16, 16, 16, 16)
        self._container_layout.setSpacing(10)
        self._container_layout.addStretch(1)

        # Wrap container in a scroll area
        from PySide6.QtWidgets import QScrollArea

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._container)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._scroll.addWidget(self._scroll_area)

        self._messages: list[ChatMessageWidget] = []

    # ------------------------------------------------------------------
    def add_message(
        self, role: str, content: str = ""
    ) -> ChatMessageWidget:
        """Add a new message bubble and return it."""
        msg = ChatMessageWidget(role, content)
        # Insert before the stretch
        self._container_layout.insertWidget(
            self._container_layout.count() - 1, msg
        )
        self._messages.append(msg)
        self._scroll_to_bottom()
        return msg

    def append_to_last(self, role: str, text: str) -> None:
        """
        Append *text* to the last message of *role*, or create a new
        one if the last message has a different role.
        """
        if self._messages and self._messages[-1].role == role:
            self._messages[-1].append_text(text)
        else:
            self.add_message(role, text)
        self._scroll_to_bottom()

    def clear_messages(self) -> None:
        """Remove all message widgets."""
        for msg in self._messages:
            self._container_layout.removeWidget(msg)
            msg.deleteLater()
        self._messages.clear()

    def _scroll_to_bottom(self) -> None:
        """Scroll the view to the bottom (deferred to next event loop)."""
        from PySide6.QtCore import QTimer

        QTimer.singleShot(10, self._do_scroll)

    def _do_scroll(self) -> None:
        sb = self._scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())
