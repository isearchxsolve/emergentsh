#!/usr/bin/env python3
"""
EmergentSH — Autonomous AI Agent Desktop Environment
=====================================================

A modern, native Windows desktop application built with PySide6 that
serves as an autonomous AI agent environment, similar to emergent.sh.

The core AI engine is based on the NVIDIA NIM terminal agent, ported
into a non-blocking, responsive GUI with:
  * QThread-based agent worker (UI never freezes)
  * Signal-driven architecture (agent ↔ UI fully decoupled)
  * Token-bucket RPM enforcement
  * 10 % context compaction
  * Auto-Correction Interceptor for XML hallucinations
  * Mid-stream overload protection + auto-retry
  * Live streaming terminal output in an Execution Drawer

Usage
-----
    python main.py

Requirements
------------
    pip install -r requirements.txt
"""

import sys

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.theme import DARK_THEME_QSS


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("EmergentSH")
    app.setOrganizationName("EmergentSH")

    # Apply dark theme globally
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
