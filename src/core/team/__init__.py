"""
Team Package — collaborative team workspaces.
"""

from .workspace import (
    TeamWorkspaceManager,
    Team,
    TeamRole,
    TeamMember,
    TeamInvitation,
    InvitationStatus,
    ActivityEvent,
    SharedSession,
    create_team_workspace,
    get_team_workspace,
)

__all__ = [
    "TeamWorkspaceManager",
    "Team",
    "TeamRole",
    "TeamMember",
    "TeamInvitation",
    "InvitationStatus",
    "ActivityEvent",
    "SharedSession",
    "create_team_workspace",
    "get_team_workspace",
]