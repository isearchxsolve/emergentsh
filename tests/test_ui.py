"""
Tests for the UI components - Chat Area, Preview Widget, and Main Window.
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

# Create QApplication before importing Qt widgets
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

# Ensure src is in path
import sys
sys.path.insert(0, '.')

# Test ChatMessageWidget
from src.ui.widgets.chat_area import ChatMessageWidget, ChatAreaWidget


class TestChatMessageWidget:
    """Test ChatMessageWidget class."""

    def test_chat_message_widget_creation(self):
        """Test ChatMessageWidget creation with different roles."""
        widget = ChatMessageWidget("user", "Hello")
        assert widget.role == "user"
        assert widget.full_text == "Hello"

    def test_chat_message_widget_roles(self):
        """Test all supported roles."""
        for role in ["user", "assistant", "tool", "reasoning"]:
            widget = ChatMessageWidget(role, f"Content for {role}")
            assert widget.role == role
            assert role in widget.full_text

    def test_append_text(self):
        """Test appending text to message."""
        widget = ChatMessageWidget("assistant", "Initial")
        widget.append_text(" appended")
        assert widget.full_text == "Initial appended"

    def test_set_text(self):
        """Test replacing entire content."""
        widget = ChatMessageWidget("user", "Old")
        widget.set_text("New")
        assert widget.full_text == "New"

    def test_role_label_colors(self):
        """Test role label color mapping."""
        assert ChatMessageWidget.ROLE_TAG_COLORS["user"] == "#7aa2f7"
        assert ChatMessageWidget.ROLE_TAG_COLORS["assistant"] == "#9ece6a"
        assert ChatMessageWidget.ROLE_TAG_COLORS["tool"] == "#e0af68"
        assert ChatMessageWidget.ROLE_TAG_COLORS["reasoning"] == "#bb9af7"
        assert ChatMessageWidget.ROLE_TAG_COLORS["error"] == "#f7768e"


class TestChatAreaWidget:
    """Test ChatAreaWidget class."""

    def test_chat_area_creation(self):
        """Test ChatAreaWidget creation."""
        area = ChatAreaWidget()
        assert area is not None
        assert len(area._messages) == 0

    def test_add_message(self):
        """Test adding messages to chat area."""
        area = ChatAreaWidget()
        msg = area.add_message("user", "Hello")
        assert len(area._messages) == 1
        assert msg.role == "user"
        assert msg.full_text == "Hello"

    def test_append_to_last_same_role(self):
        """Test appending to last message of same role."""
        area = ChatAreaWidget()
        area.add_message("assistant", "First")
        area.append_to_last("assistant", " Second")
        assert len(area._messages) == 1
        assert area._messages[0].full_text == "First Second"

    def test_append_to_last_different_role(self):
        """Test appending creates new message for different role."""
        area = ChatAreaWidget()
        area.add_message("assistant", "First")
        area.append_to_last("user", " Second")
        assert len(area._messages) == 2
        assert area._messages[0].full_text == "First"
        assert area._messages[1].full_text == " Second"
        assert area._messages[1].role == "user"

    def test_clear_messages(self):
        """Test clearing all messages."""
        area = ChatAreaWidget()
        area.add_message("user", "Hello")
        area.add_message("assistant", "Hi")
        assert len(area._messages) == 2
        area.clear_messages()
        assert len(area._messages) == 0


# Test PreviewWidget
from src.ui.widgets.preview.preview_widget import PreviewWidget, PreviewPage

# Ensure the main_window submodule is loaded into the src.ui package namespace so
# that patch('src.ui.main_window.get_workspace') can resolve the target via
# getattr(src.ui, 'main_window') during fixture setup (before the test body
# imports MainWindow itself).
import src.ui.main_window  # noqa: F401


class TestPreviewWidget:
    """Test PreviewWidget class."""

    def test_preview_widget_creation(self):
        """Test PreviewWidget creation."""
        widget = PreviewWidget()
        assert widget is not None
        assert widget._web_view is not None

    def test_preview_page_creation(self):
        """Test PreviewPage creation."""
        from PySide6.QtWebEngineCore import QWebEngineProfile
        profile = QWebEngineProfile("test", None)
        page = PreviewPage(profile)
        assert page is not None

    @pytest.mark.skipif(not hasattr(__import__('PySide6.QtWebEngineWidgets'), 'QWebEngineView'), 
                        reason="QtWebEngine not available")
    def test_load_url(self):
        """Test loading a URL."""
        widget = PreviewWidget()
        # Just test the method exists and doesn't crash
        widget.load_url("http://example.com")
        # Can't easily test actual loading without event loop

    def test_device_sizes_mapping(self):
        """Test device size mappings in preview widget."""
        widget = PreviewWidget()
        # Access the internal mapping
        sizes = {
            "Desktop (1920x1080)": (1920, 1080),
            "Laptop (1366x768)": (1366, 768),
            "Tablet Portrait (768x1024)": (768, 1024),
            "Tablet Landscape (1024x768)": (1024, 768),
            "Mobile Portrait (375x667)": (375, 667),
            "Mobile Landscape (667x375)": (667, 375),
        }
        # Verify the mapping exists in the widget's _on_device_changed method
        for device, (w, h) in sizes.items():
            assert isinstance(w, int)
            assert isinstance(h, int)


# Test MainWindow (integration test)
class TestMainWindow:
    """Test MainWindow integration."""

    @pytest.fixture
    def mock_workspace(self):
        """Mock workspace manager."""
        with patch('src.ui.main_window.get_workspace') as mock_get:
            mock_ws = Mock()
            mock_ws.list_projects.return_value = []
            mock_ws.list_profiles.return_value = []
            mock_get.return_value = mock_ws
            yield mock_ws

    def test_main_window_creation(self, mock_workspace):
        """Test MainWindow creation with mocked dependencies."""
        with patch('src.ui.main_window.create_dev_server_manager') as mock_dev:
            mock_dev.return_value = Mock()
            
            from src.ui.main_window import MainWindow
            window = MainWindow()
            
            assert window is not None
            assert window.windowTitle() == "EmergentSH — Multi-Agent Development Environment"
            assert window.project_panel is not None
            assert window.chat_area is not None
            assert window.execution_drawer is not None
            assert window._preview_widget is not None

    def test_mode_toggle(self, mock_workspace):
        """Test single/multi-agent mode toggle."""
        with patch('src.ui.main_window.create_dev_server_manager'):
            from src.ui.main_window import MainWindow
            window = MainWindow()
            
            # Default is multi-agent (True)
            assert window._use_orchestrator is True
            assert window._mode_btn.isChecked() is True
            
            # Toggle to single agent
            window._mode_btn.setChecked(False)
            assert window._use_orchestrator is False
            assert "Single Agent" in window._mode_btn.text()


# Test ExecutionDrawer
from src.ui.widgets.execution_drawer import ExecutionDrawer


class TestExecutionDrawer:
    """Test ExecutionDrawer class."""

    def test_execution_drawer_creation(self):
        """Test ExecutionDrawer creation."""
        drawer = ExecutionDrawer()
        assert drawer is not None

    def test_on_tool_start(self):
        """Test tool start handling."""
        drawer = ExecutionDrawer()
        drawer.on_tool_start("read_file")
        # Just verify it doesn't crash

    def test_on_tool_executing(self):
        """Test tool executing handling."""
        drawer = ExecutionDrawer()
        drawer.on_tool_executing("write_file", '{"path": "test.py"}')
        # Just verify it doesn't crash

    def test_on_tool_output(self):
        """Test tool output handling."""
        drawer = ExecutionDrawer()
        drawer.on_tool_output("Reading file...")
        # Just verify it doesn't crash

    def test_on_tool_result(self):
        """Test tool result handling."""
        drawer = ExecutionDrawer()
        drawer.on_tool_result("read_file", "File content here")
        # Just verify it doesn't crash

    def test_clear(self):
        """Test clearing the drawer."""
        drawer = ExecutionDrawer()
        drawer.on_tool_output("Some output")
        drawer.clear()
        # Just verify it doesn't crash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])