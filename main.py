#!/usr/bin/env python3
"""
NeonBuild — Autonomous AI Agent Desktop Environment
=====================================================

A modern, native Windows desktop application built with PySide6 that
serves as an autonomous AI agent environment, similar to NeonBuild.

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

import os
import sys

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.theme import DARK_THEME_QSS


def main() -> int:
    # This native shell still contains the historical direct-provider workers.
    # It is deliberately quarantined from production distribution until those
    # workers are refactored to submit authenticated durable SaaS jobs.
    runtime = os.getenv("APP_ENV", "development").strip().lower()
    enabled = os.getenv("EMERGENT_ENABLE_LEGACY_DESKTOP", "false").strip().lower() in {"true", "1", "yes", "on"}
    if runtime in {"production", "prod"} or not enabled:
        raise RuntimeError(
            "The legacy desktop agent is disabled. Use the authenticated SaaS pipeline; "
            "direct provider workers are not a production execution path."
        )
    app = QApplication(sys.argv)
    app.setApplicationName("NeonBuild")
    app.setOrganizationName("NeonBuild")

    # Apply dark theme globally
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
