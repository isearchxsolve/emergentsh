"""
PreviewWidget — embedded browser view for live preview with HMR support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import Qt, QUrl, QTimer, Signal, QObject, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QFrame, QSplitter, QToolBar
)
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtCore import QSize


class PreviewPage(QWebEnginePage):
    """Custom page with console logging and error handling."""

    console_message = Signal(str, int, str)  # message, level, source

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(profile, parent)

    def javaScriptConsoleMessage(self, level: int, message: str, line: int, source: str) -> None:
        level_names = {0: "INFO", 1: "WARNING", 2: "ERROR"}
        self.console_message.emit(f"[{level_names.get(level, 'LOG')}] {source}:{line} - {message}", level, source)
        super().javaScriptConsoleMessage(level, message, line, source)


class PreviewWidget(QWidget):
    """
    Live preview widget with embedded browser.

    Features:
    - QWebEngineView for rendering
    - Auto-refresh on HMR
    - Address bar with navigation
    - Device toolbar (mobile/desktop)
    - Console panel
    - Component inspector overlay (via injected JS)
    """

    url_changed = Signal(QUrl)
    load_finished = Signal(bool)
    console_message = Signal(str)
    inspect_element = Signal(dict)  # element info from inspector

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_url: Optional[QUrl] = None
        self._inspector_active = False
        self._hmr_connected = False

        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create web view FIRST
        self._profile = QWebEngineProfile("preview", self)
        self._page = PreviewPage(self._profile, self)
        self._page.console_message.connect(self._on_console_message)

        self._web_view = QWebEngineView(self)
        self._web_view.setPage(self._page)
        self._web_view.urlChanged.connect(self._on_url_changed)
        self._web_view.loadFinished.connect(self._on_load_finished)

        # Configure web engine settings
        self._configure_web_engine()

        # Toolbar
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setIconSize(QSize(16, 16))
        layout.addWidget(self._toolbar)

        # Navigation - need to create web view reference first
        self._back_btn = QAction("←", self)
        self._back_btn.setToolTip("Back")
        self._back_btn.triggered.connect(self._web_view.back)

        self._forward_btn = QAction("→", self)
        self._forward_btn.setToolTip("Forward")
        self._forward_btn.triggered.connect(self._web_view.forward)

        self._refresh_btn = QAction("⟳", self)
        self._refresh_btn.setToolTip("Refresh (F5)")
        self._refresh_btn.triggered.connect(self._web_view.reload)

        # Toolbar
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setIconSize(QSize(16, 16))
        layout.addWidget(self._toolbar)

        # Now add actions to toolbar
        self._back_btn = QAction("←", self)
        self._back_btn.setToolTip("Back")
        self._back_btn.triggered.connect(self._web_view.back)
        self._toolbar.addAction(self._back_btn)

        self._forward_btn = QAction("→", self)
        self._forward_btn.setToolTip("Forward")
        self._forward_btn.triggered.connect(self._web_view.forward)
        self._toolbar.addAction(self._forward_btn)

        self._refresh_btn = QAction("⟳", self)
        self._refresh_btn.setToolTip("Refresh (F5)")
        self._refresh_btn.triggered.connect(self._web_view.reload)
        self._toolbar.addAction(self._refresh_btn)

        self._toolbar.addSeparator()

        # Address bar
        self._address_bar = QLineEdit()
        self._address_bar.setPlaceholderText("Enter URL (http://localhost:3000)...")
        self._address_bar.returnPressed.connect(self._navigate_to_address)
        self._address_bar.setMinimumWidth(300)
        self._toolbar.addWidget(self._address_bar)

        self._toolbar.addSeparator()

        # Device selector
        self._device_combo = QComboBox()
        self._device_combo.addItems([
            "Desktop (1920x1080)",
            "Laptop (1366x768)",
            "Tablet Portrait (768x1024)",
            "Tablet Landscape (1024x768)",
            "Mobile Portrait (375x667)",
            "Mobile Landscape (667x375)",
            "Custom...",
        ])
        self._device_combo.currentTextChanged.connect(self._on_device_changed)
        self._toolbar.addWidget(self._device_combo)

        self._toolbar.addSeparator()

        # Inspector toggle
        self._inspect_btn = QAction("🔍 Inspect", self)
        self._inspect_btn.setCheckable(True)
        self._inspect_btn.setToolTip("Toggle element inspector (Ctrl+Shift+I)")
        self._inspect_btn.toggled.connect(self._toggle_inspector)
        self._toolbar.addAction(self._inspect_btn)

        # Console toggle
        self._console_btn = QAction("📋 Console", self)
        self._console_btn.setCheckable(True)
        self._console_btn.setToolTip("Toggle console panel")
        self._console_btn.toggled.connect(self._toggle_console)
        self._toolbar.addAction(self._console_btn)

        # Main view splitter
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setHandleWidth(4)
        layout.addWidget(self._splitter)

        # Add web view to splitter
        self._splitter.addWidget(self._web_view)

        # Console panel (hidden by default)
        self._console_widget = QWidget()
        self._console_widget.setVisible(False)
        console_layout = QVBoxLayout(self._console_widget)
        console_layout.setContentsMargins(8, 8, 8, 8)

        console_header = QHBoxLayout()
        console_header.addWidget(QLabel("Console"))
        console_header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(self._clear_console)
        console_header.addWidget(clear_btn)
        console_layout.addLayout(console_header)

        self._console_output = QLabel()
        self._console_output.setWordWrap(True)
        self._console_output.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._console_output.setStyleSheet("""
            background-color: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Monospace';
            font-size: 11px;
            padding: 8px;
            border-radius: 4px;
        """)
        self._console_output.setTextInteractionFlags(Qt.TextSelectableByMouse)
        console_layout.addWidget(self._console_output)

        self._splitter.addWidget(self._console_widget)
        self._splitter.setSizes([600, 0])

        # Settings
        self._configure_web_engine()

        # Add toolbar to layout (after web view so it's on top)
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._toolbar.setIconSize(QSize(16, 16))
        # Insert toolbar at top
        layout = self.layout()
        layout.insertWidget(0, self._toolbar)

        # Navigation actions
        self._back_btn = QAction("←", self)
        self._back_btn.setToolTip("Back")
        self._back_btn.triggered.connect(self._web_view.back)
        self._toolbar.addAction(self._back_btn)

        self._forward_btn = QAction("→", self)
        self._forward_btn.setToolTip("Forward")
        self._forward_btn.triggered.connect(self._web_view.forward)
        self._toolbar.addAction(self._forward_btn)

        self._refresh_btn = QAction("⟳", self)
        self._refresh_btn.setToolTip("Refresh (F5)")
        self._refresh_btn.triggered.connect(self._web_view.reload)
        self._toolbar.addAction(self._refresh_btn)

        self._toolbar.addSeparator()

        # Address bar
        self._address_bar = QLineEdit()
        self._address_bar.setPlaceholderText("Enter URL (http://localhost:3000)...")
        self._address_bar.returnPressed.connect(self._navigate_to_address)
        self._address_bar.setMinimumWidth(300)
        self._toolbar.addWidget(self._address_bar)

        self._toolbar.addSeparator()

        # Device selector
        self._device_combo = QComboBox()
        self._device_combo.addItems([
            "Desktop (1920x1080)",
            "Laptop (1366x768)",
            "Tablet Portrait (768x1024)",
            "Tablet Landscape (1024x768)",
            "Mobile Portrait (375x667)",
            "Mobile Landscape (667x375)",
            "Custom...",
        ])
        self._device_combo.currentTextChanged.connect(self._on_device_changed)
        self._toolbar.addWidget(self._device_combo)

        self._toolbar.addSeparator()

        # Inspector toggle
        self._inspect_btn = QAction("🔍 Inspect", self)
        self._inspect_btn.setCheckable(True)
        self._inspect_btn.setToolTip("Toggle element inspector (Ctrl+Shift+I)")
        self._inspect_btn.toggled.connect(self._toggle_inspector)
        self._toolbar.addAction(self._inspect_btn)

        # Console toggle
        self._console_btn = QAction("📋 Console", self)
        self._console_btn.setCheckable(True)
        self._console_btn.setToolTip("Toggle console panel")
        self._console_btn.toggled.connect(self._toggle_console)
        self._toolbar.addAction(self._console_btn)

    def _configure_web_engine(self) -> None:
        """Configure web engine settings for development."""
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        # Enable developer tools
        self._profile.setPersistentStoragePath(str(Path.home() / ".emergentsh" / "webengine"))

    def _setup_shortcuts(self) -> None:
        # F5 / Ctrl+R = Refresh
        QShortcut(QKeySequence(Qt.Key_F5), self, self._web_view.reload)
        QShortcut(QKeySequence("Ctrl+R"), self, self._web_view.reload)

        # Ctrl+Shift+R = Hard refresh
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, lambda: self._web_view.reload())

        # Ctrl+L = Focus address bar
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self._address_bar.setFocus())

        # Ctrl+Shift+I = Toggle inspector
        QShortcut(QKeySequence("Ctrl+Shift+I"), self, lambda: self._inspect_btn.toggle())

        # Ctrl+Shift+J = Toggle console
        QShortcut(QKeySequence("Ctrl+Shift+J"), self, lambda: self._console_btn.toggle())

        # Escape = Stop loading
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._web_view.stop)

    def load_url(self, url: str | QUrl) -> None:
        """Load a URL in the preview."""
        if isinstance(url, str):
            url = QUrl(url)
        if not url.scheme():
            url.setScheme("http")
        self._web_view.load(url)

    def load_project(self, project_dir: str, port: int) -> None:
        """Load a project from a directory and port."""
        url = QUrl(f"http://localhost:{port}")
        self._web_view.load(url)

    def _navigate_to_address(self) -> None:
        text = self._address_bar.text().strip()
        if not text:
            return
        if not text.startswith(("http://", "https://", "file://")):
            text = "http://" + text
        self.load_url(text)

    def _on_url_changed(self, url: QUrl) -> None:
        self._current_url = url
        self._address_bar.setText(url.toString())
        self.url_changed.emit(url)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            self._inject_hmr_client()
            self._inject_inspector()
        self.load_finished.emit(ok)

    def _on_console_message(self, message: str, level: int, source: str) -> None:
        self.console_message.emit(message)
        self._append_console(message, level)

    def _inject_hmr_client(self) -> None:
        """Inject HMR WebSocket client for auto-refresh."""
        hmr_script = """
        (function() {
            if (window.__hmr_connected) return;
            window.__hmr_connected = true;

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(`${protocol}//${window.location.host}/hmr`);

            ws.onopen = () => console.log('[HMR] Connected');
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'reload') {
                        console.log('[HMR] Reloading page...');
                        window.location.reload();
                    } else if (data.type === 'css-update') {
                        // Hot reload CSS without full reload
                        const links = document.querySelectorAll('link[rel="stylesheet"]');
                        links.forEach(link => {
                            const href = link.href.split('?')[0];
                            link.href = href + '?' + Date.now();
                        });
                    } else if (data.type === 'update') {
                        console.log('[HMR] Module update:', data.payload);
                        // Module hot update would go here
                    }
                } catch (e) {
                    console.error('[HMR] Message parse error:', e);
                }
            };

            ws.onclose = () => {
                console.log('[HMR] Disconnected, reconnecting in 2s...');
                setTimeout(() => window.location.reload(), 2000);
            };

            ws.onerror = (err) => console.error('[HMR] WebSocket error:', err);
        })();
        """
        self._web_view.page().runJavaScript(hmr_script)

    def _inject_inspector(self) -> None:
        """Inject element inspector script."""
        inspector_script = """
        (function() {
            if (window.__inspector_injected) return;
            window.__inspector_injected = true;

            let selectedElement = null;
            let highlightOverlay = null;

            function createOverlay() {
                const overlay = document.createElement('div');
                overlay.style.cssText = `
                    position: fixed;
                    pointer-events: none;
                    z-index: 2147483647;
                    border: 2px solid #00d4ff;
                    background: rgba(0, 212, 255, 0.1);
                    box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.3);
                    transition: all 0.1s ease;
                `;
                document.body.appendChild(overlay);
                return overlay;
            }

            function showOverlay(element) {
                if (!highlightOverlay) highlightOverlay = createOverlay();
                const rect = element.getBoundingClientRect();
                highlightOverlay.style.top = (rect.top + window.scrollY) + 'px';
                highlightOverlay.style.left = (rect.left + window.scrollX) + 'px';
                highlightOverlay.style.width = rect.width + 'px';
                highlightOverlay.style.height = rect.height + 'px';
                highlightOverlay.style.display = 'block';
            }

            function hideOverlay() {
                if (highlightOverlay) highlightOverlay.style.display = 'none';
            }

            function getElementInfo(element) {
                const rect = element.getBoundingClientRect();
                const styles = window.getComputedStyle(element);
                return {
                    tag: element.tagName.toLowerCase(),
                    id: element.id || null,
                    className: element.className || null,
                    xpath: getXPath(element),
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                    styles: {
                        display: styles.display,
                        position: styles.position,
                        color: styles.color,
                        backgroundColor: styles.backgroundColor,
                        fontSize: styles.fontSize,
                        fontFamily: styles.fontFamily,
                        margin: styles.margin,
                        padding: styles.padding,
                    },
                    attributes: Array.from(element.attributes).reduce((acc, attr) => {
                        acc[attr.name] = attr.value;
                        return acc;
                    }, {}),
                };
            }

            function getXPath(element) {
                if (element.id) return `//*[@id="${element.id}"]`;
                if (element === document.body) return '/html/body';
                let ix = 0;
                const siblings = element.parentNode ? Array.from(element.parentNode.childNodes).filter(n => n.nodeType === 1 && n.tagName === element.tagName) : [];
                for (let i = 0; i < siblings.length; i++) {
                    if (siblings[i] === element) { ix = i + 1; break; }
                }
                return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + (ix > 1 ? '[' + ix + ']' : '');
            }

            let inspectMode = false;

            window.__toggleInspect = function(enable) {
                inspectMode = enable;
                if (enable) {
                    document.addEventListener('mouseover', onMouseOver, true);
                    document.addEventListener('click', onClick, true);
                    document.body.style.cursor = 'crosshair';
                } else {
                    document.removeEventListener('mouseover', onMouseOver, true);
                    document.removeEventListener('click', onClick, true);
                    document.body.style.cursor = '';
                    hideOverlay();
                }
            };

            function onMouseOver(e) {
                if (!inspectMode) return;
                e.stopPropagation();
                showOverlay(e.target);
            }

            function onClick(e) {
                if (!inspectMode) return;
                e.preventDefault();
                e.stopPropagation();
                const info = getElementInfo(e.target);
                hideOverlay();
                window.__inspectMode = false;
                document.removeEventListener('mouseover', onMouseOver, true);
                document.removeEventListener('click', onClick, true);
                document.body.style.cursor = '';
                // Send to Qt
                if (window.qt && window.qt.inspectElement) {
                    window.qt.inspectElement(info);
                }
            }

            // Expose to Qt
            window.qt = {
                inspectElement: function(info) {
                    console.log('[Inspector] Element selected:', info);
                }
            };
        })();
        """
        self._web_view.page().runJavaScript(inspector_script)

    def _toggle_inspector(self, enabled: bool) -> None:
        self._inspector_active = enabled
        self._page.runJavaScript(f"window.__toggleInspect({str(enabled).lower()})")

    def _toggle_console(self, visible: bool) -> None:
        self._console_widget.setVisible(visible)
        if visible:
            self._splitter.setSizes([500, 200])

    def _append_console(self, message: str, level: int) -> None:
        color = {"0": "#9cdcfe", "1": "#dcdcaa", "2": "#f44747"}.get(str(level), "#9cdcfe")
        self._console_output.setText(
            self._console_output.text() + f'<span style="color:{color}">{message}</span><br>'
        )

    def _clear_console(self) -> None:
        self._console_output.clear()

    def _on_device_changed(self, device: str) -> None:
        """Handle device toolbar selection."""
        sizes = {
            "Desktop (1920x1080)": (1920, 1080),
            "Laptop (1366x768)": (1366, 768),
            "Tablet Portrait (768x1024)": (768, 1024),
            "Tablet Landscape (1024x768)": (1024, 768),
            "Mobile Portrait (375x667)": (375, 667),
            "Mobile Landscape (667x375)": (667, 375),
        }

        if device in sizes:
            w, h = sizes[device]
            self._web_view.resize(w, h)
        elif device == "Custom...":
            pass

    def get_current_url(self) -> Optional[QUrl]:
        return self._current_url

    def reload(self) -> None:
        self._web_view.reload()

    def stop(self) -> None:
        self._web_view.stop()

    def back(self) -> None:
        self._web_view.back()

    def forward(self) -> None:
        self._web_view.forward()


# Add missing imports
from PySide6.QtWidgets import QToolBar