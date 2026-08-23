"""
DARK_THEME — QSS stylesheet for the Emergent.sh clone.

Colour palette per DESIGN.md (NVIDIA identity, near-black, developer-grade):
  bg-base       #0A0A0B    bg-surface    #131316    bg-surface-2  #1B1B20
  bg-elevated   #222228    border-subtle #26262C    border-strong #3A3A44
  text-primary  #F5F5F7    text-secondary#A1A1AA    text-muted    #6B6B73
  accent        #76B900    accent-hover  #8FD400    accent-muted  rgba(118,185,0,0.12)
  info          #3B82F6    warning       #F59E0B    danger        #EF4444
  success       #22C55E    code-bg       #0F0F12

Agent role colors (consistent across rail, chat, logs):
  Orchestrator #3B82F6  Frontend #EC4899  Backend #8B5CF6
  Database     #14B8A6  Tester   #F59E0B  Deployer #76B900
"""

DARK_THEME_QSS = """
/* ── Global ──────────────────────────────────────────────────────── */
QWidget {
    background-color: #0A0A0B;
    color: #F5F5F7;
    font-family: "Inter", "Segoe UI", "Cascadia Code", "Consolas", sans-serif;
    font-size: 14px;
}

QMainWindow, QDialog {
    background-color: #0A0A0B;
}

/* ── Scrollbars ──────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #131316;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3A3A44;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #6B6B73;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #131316;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3A3A44;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #6B6B73;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
#Sidebar {
    background-color: #131316;
    border-right: 1px solid #26262C;
}
#Sidebar QLabel#SidebarTitle {
    color: #76B900;
    font-size: 15px;
    font-weight: 600;
    padding: 8px 12px 4px 12px;
}
#Sidebar QLabel#SectionLabel {
    color: #6B6B73;
    font-size: 11px;
    font-weight: 600;
    padding: 8px 12px 2px 12px;
    text-transform: uppercase;
}

/* ── Profile / Session list ──────────────────────────────────────── */
QListWidget {
    background-color: #131316;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 6px 12px;
    border-radius: 6px;
    color: #A1A1AA;
}
QListWidget::item:hover {
    background-color: #1B1B20;
}
QListWidget::item:selected {
    background-color: rgba(118,185,0,0.12);
    color: #76B900;
    font-weight: 600;
}

/* ── Chat area ───────────────────────────────────────────────────── */
#ChatScroll {
    background-color: #0A0A0B;
    border: none;
}
#ChatContainer {
    background-color: #0A0A0B;
}

/* Message bubbles */
QFrame#UserBubble {
    background-color: #1B1B20;
    border: 1px solid #26262C;
    border-radius: 10px;
}
QFrame#AssistantBubble {
    background-color: #131316;
    border: 1px solid #26262C;
    border-radius: 10px;
}
QFrame#ToolBubble {
    background-color: #0A0A0B;
    border: 1px dashed #26262C;
    border-radius: 6px;
}
QFrame#ReasoningBubble {
    background-color: #0A0A0B;
    border-left: 3px solid #8B5CF6;
    border-radius: 0px;
}
QLabel#RoleLabel {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 0;
}
QLabel#RoleUser { color: #76B900; }
QLabel#RoleAssistant { color: #22C55E; }
QLabel#RoleTool { color: #F59E0B; }
QLabel#RoleReasoning { color: #8B5CF6; }
QLabel#ContentLabel {
    color: #F5F5F7;
}
QLabel#ReasoningContent {
    color: #8B5CF6;
    font-style: italic;
}

/* ── Input area ──────────────────────────────────────────────────── */
#InputFrame {
    background-color: #16161e;
    border-top: 1px solid #3b4261;
}
QPlainTextEdit#PromptInput {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 8px;
    padding: 8px;
    color: #c0caf5;
    font-size: 14px;
    selection-background-color: #2d3f5f;
}
QPlainTextEdit#PromptInput:focus {
    border: 1px solid #7aa2f7;
}

/* ── Buttons ─────────────────────────────────────────────────────── */
QPushButton {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 6px 16px;
    color: #c0caf5;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2d3f5f;
    border-color: #7aa2f7;
}
QPushButton:pressed {
    background-color: #7aa2f7;
    color: #1a1b26;
}
QPushButton:disabled {
    background-color: #16161e;
    color: #565f89;
    border-color: #2a2e3f;
}
QPushButton#SendButton {
    background-color: #7aa2f7;
    border: none;
    color: #1a1b26;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 24px;
}
QPushButton#SendButton:hover {
    background-color: #89b0ff;
}
QPushButton#SendButton:disabled {
    background-color: #2a2e3f;
    color: #565f89;
}
QPushButton#StopButton {
    background-color: #f7768e;
    border: none;
    color: #1a1b26;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 24px;
}
QPushButton#StopButton:hover {
    background-color: #ff8fa3;
}

/* ── Execution Drawer ────────────────────────────────────────────── */
#ExecutionDrawer {
    background-color: #16161e;
    border-top: 1px solid #3b4261;
}
#ExecutionDrawer QLabel#DrawerTitle {
    color: #e0af68;
    font-size: 13px;
    font-weight: bold;
    padding: 6px 12px;
}
QPlainTextEdit#TerminalOutput {
    background-color: #0f0f14;
    border: none;
    color: #9ece6a;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 4px 8px;
    selection-background-color: #2d3f5f;
}

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #16161e;
    border-top: 1px solid #3b4261;
    color: #565f89;
    font-size: 11px;
}
QStatusBar QLabel {
    color: #565f89;
    padding: 0 8px;
}
QLabel#StatusHealthOk { color: #9ece6a; }
QLabel#StatusHealthErr { color: #f7768e; }
QLabel#StatusCredits { color: #e0af68; }
QLabel#StatusBuildIdle { color: #565f89; }
QLabel#StatusBuildRunning { color: #e0af68; }
QLabel#StatusBuildDone { color: #9ece6a; }
QLabel#StatusBuildFailed { color: #f7768e; }

/* ── Preview overlay ─────────────────────────────────────────────── */
QFrame#PreviewOverlay {
    background-color: rgba(15,15,20,200);
}
QLabel#PreviewBuilding {
    color: #e0af68;
    font-size: 14px;
    font-weight: bold;
}
QLabel#PreviewReady {
    color: #9ece6a;
    font-size: 14px;
    font-weight: bold;
}
QLabel#PreviewFailed {
    color: #f7768e;
    font-size: 14px;
    font-weight: bold;
}

/* ── Self-debug iteration stepper ─────────────────────────────────── */
QFrame#DebugStepper {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 4px 8px;
}
QLabel#DebugIter {
    color: #bb9af7;
    font-size: 11px;
    font-weight: bold;
}
QLabel#DebugIterActive {
    color: #e0af68;
    font-size: 11px;
    font-weight: bold;
}
QLabel#DebugIterDone {
    color: #9ece6a;
    font-size: 11px;
    font-weight: bold;
}

/* ── Credit / token chip on tool bubbles ─────────────────────────── */
QLabel#CostChip {
    color: #565f89;
    font-size: 10px;
    background-color: #16161e;
    border: 1px solid #3b4261;
    border-radius: 8px;
    padding: 1px 6px;
}

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #3b4261;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ── Tooltips ────────────────────────────────────────────────────── */
QToolTip {
    background-color: #1f2335;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── Dialog ───────────────────────────────────────────────────────── */
QDialog {
    background-color: #1a1b26;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #1f2335;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 6px 8px;
    color: #c0caf5;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #7aa2f7;
}
QGroupBox {
    border: 1px solid #3b4261;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: #7aa2f7;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
"""
