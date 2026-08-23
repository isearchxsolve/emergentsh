"""
Updater Package — Auto-update mechanism for Windows.
"""

from .updater import (
    UpdateManager,
    UpdateInfo,
    UpdateProgress,
    UpdateChannel,
    BackgroundUpdateChecker,
    create_update_manager,
    MSIBuilder,
)

__all__ = [
    "UpdateManager",
    "UpdateInfo",
    "UpdateProgress",
    "UpdateChannel",
    "BackgroundUpdateChecker",
    "create_update_manager",
    "MSIBuilder",
]