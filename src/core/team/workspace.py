"""
TeamWorkspace — collaboration features for team workspaces.

Features:
- Shared projects with role-based access control
- Real-time co-editing (CRDT-based via Yjs)
- Team member management with roles
- Activity feed and notifications
- Shared sessions and context
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable

from ..workspace import WorkspaceManager, get_workspace, Project


# ════════════════════════════════════════════════════════════════════════════
# Enums & Data Models
# ════════════════════════════════════════════════════════════════════════════

class TeamRole(str, Enum):
    """Team member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    GUEST = "guest"


class InvitationStatus(str, Enum):
    """Invitation status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


@dataclass
class TeamMember:
    """Team member with role and permissions."""
    user_id: str
    email: str
    name: str
    role: TeamRole
    joined_at: datetime = field(default_factory=datetime.now)
    avatar_url: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    is_active: bool = True
    last_active: Optional[datetime] = None


@dataclass
class TeamInvitation:
    """Team invitation."""
    id: str
    team_id: str
    email: str
    role: TeamRole
    invited_by: str
    status: InvitationStatus = InvitationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=7))
    accepted_at: Optional[datetime] = None


@dataclass
class Team:
    """Team workspace."""
    id: str
    name: str
    description: str
    owner_id: str
    members: Dict[str, TeamMember] = field(default_factory=dict)  # user_id -> TeamMember
    invitations: Dict[str, TeamInvitation] = field(default_factory=dict)  # invitation_id -> TeamInvitation
    projects: Set[str] = field(default_factory=set)  # project_ids
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def get_member(self, user_id: str) -> Optional[TeamMember]:
        return self.members.get(user_id)
    
    def get_role(self, user_id: str) -> Optional[TeamRole]:
        member = self.members.get(user_id)
        return member.role if member else None
    
    def has_permission(self, user_id: str, permission: str) -> bool:
        member = self.members.get(user_id)
        if not member:
            return False
        # Owners have all permissions
        if member.role == TeamRole.OWNER:
            return True
        # Admins have most permissions
        if member.role == TeamRole.ADMIN:
            return permission != "delete_team"
        return permission in member.permissions


@dataclass
class ActivityEvent:
    """Activity feed event."""
    id: str
    team_id: str
    user_id: str
    action: str  # "created", "updated", "deleted", "joined", "left", "commented"
    target_type: str  # "project", "task", "file", "session", "comment"
    target_id: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SharedSession:
    """Real-time collaborative session."""
    id: str
    team_id: str
    project_id: str
    name: str
    owner_id: str
    participants: Set[str] = field(default_factory=set)  # user_ids
    document_state: Dict[str, Any] = field(default_factory=dict)  # Yjs document state
    is_active: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


# ════════════════════════════════════════════════════════════════════════════
# Team Workspace Manager
# ════════════════════════════════════════════════════════════════════════════

class TeamWorkspaceManager:
    """
    Manages team workspaces with collaboration features.
    
    Features:
    - Team CRUD operations
    - Member management with RBAC
    - Invitations
    - Activity feed
    - Shared sessions (co-editing)
    - Project sharing
    """
    
    def __init__(self, workspace: Optional[WorkspaceManager] = None):
        self._workspace = workspace or get_workspace()
        self._teams: Dict[str, Team] = {}
        self._user_teams: Dict[str, Set[str]] = {}  # user_id -> team_ids
        self._activity_feed: List[ActivityEvent] = []
        self._sessions: Dict[str, SharedSession] = {}
        self._lock = threading.Lock()
        self._callbacks: Dict[str, List[Callable]] = {
            "member_added": [],
            "member_removed": [],
            "member_updated": [],
            "invitation_created": [],
            "invitation_accepted": [],
            "activity": [],
            "session_created": [],
            "session_updated": [],
        }
        self._load_teams()
    
    # ----------------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------------
    
    def _get_teams_file(self) -> Path:
        return Path.home() / ".emergentsh_teams.json"
    
    def _load_teams(self) -> None:
        """Load teams from file."""
        teams_file = self._get_teams_file()
        if not teams_file.exists():
            return
        
        try:
            data = json.loads(teams_file.read_text())
            for team_data in data.get("teams", []):
                team = self._deserialize_team(team_data)
                self._teams[team.id] = team
                for member_id in team.members:
                    self._user_teams.setdefault(member_id, set()).add(team.id)
        except Exception as e:
            print(f"Failed to load teams: {e}")
    
    def _save_teams(self) -> None:
        """Save teams to file."""
        teams_file = self._get_teams_file()
        teams_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "teams": [self._serialize_team(t) for t in self._teams.values()],
            "saved_at": datetime.now().isoformat(),
        }
        teams_file.write_text(json.dumps(data, indent=2, default=str))
    
    def _serialize_team(self, team: Team) -> Dict[str, Any]:
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner_id": team.owner_id,
            "members": {uid: self._serialize_member(m) for uid, m in team.members.items()},
            "invitations": {iid: self._serialize_invitation(inv) for iid, inv in team.invitations.items()},
            "projects": list(team.projects),
            "settings": team.settings,
            "created_at": team.created_at.isoformat(),
            "updated_at": team.updated_at.isoformat(),
        }
    
    def _deserialize_team(self, data: Dict[str, Any]) -> Team:
        return Team(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            owner_id=data["owner_id"],
            members={uid: self._deserialize_member(m) for uid, m in data.get("members", {}).items()},
            invitations={iid: self._deserialize_invitation(inv) for iid, inv in data.get("invitations", {}).items()},
            projects=set(data.get("projects", [])),
            settings=data.get("settings", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
    
    def _serialize_member(self, member: TeamMember) -> Dict[str, Any]:
        return {
            "user_id": member.user_id,
            "email": member.email,
            "name": member.name,
            "role": member.role.value,
            "joined_at": member.joined_at.isoformat(),
            "avatar_url": member.avatar_url,
            "permissions": list(member.permissions),
            "is_active": member.is_active,
            "last_active": member.last_active.isoformat() if member.last_active else None,
        }
    
    def _deserialize_member(self, data: Dict[str, Any]) -> TeamMember:
        return TeamMember(
            user_id=data["user_id"],
            email=data["email"],
            name=data["name"],
            role=TeamRole(data["role"]),
            joined_at=datetime.fromisoformat(data["joined_at"]),
            avatar_url=data.get("avatar_url"),
            permissions=set(data.get("permissions", [])),
            is_active=data.get("is_active", True),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None,
        )
    
    def _serialize_invitation(self, inv: TeamInvitation) -> Dict[str, Any]:
        return {
            "id": inv.id,
            "team_id": inv.team_id,
            "email": inv.email,
            "role": inv.role.value,
            "invited_by": inv.invited_by,
            "status": inv.status.value,
            "created_at": inv.created_at.isoformat(),
            "expires_at": inv.expires_at.isoformat(),
            "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        }
    
    def _deserialize_invitation(self, data: Dict[str, Any]) -> TeamInvitation:
        return TeamInvitation(
            id=data["id"],
            team_id=data["team_id"],
            email=data["email"],
            role=TeamRole(data["role"]),
            invited_by=data["invited_by"],
            status=InvitationStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            accepted_at=datetime.fromisoformat(data["accepted_at"]) if data.get("accepted_at") else None,
        )
    
    # ----------------------------------------------------------------------
    # Team Management
    # ----------------------------------------------------------------------
    
    def create_team(
        self,
        name: str,
        owner_id: str,
        owner_email: str,
        owner_name: str,
        description: str = "",
    ) -> Team:
        """Create a new team."""
        with self._lock:
            team = Team(
                id=f"team_{uuid.uuid4().hex[:8]}",
                name=name,
                description=description,
                owner_id=owner_id,
            )
            
            # Add owner as member
            owner = TeamMember(
                user_id=owner_id,
                email=owner_email,
                name=owner_name,
                role=TeamRole.OWNER,
                permissions={"*"},  # All permissions
            )
            team.members[owner_id] = owner
            team.projects = set()
            team.settings = {
                "allow_public_join": False,
                "require_approval": True,
                "default_role": TeamRole.DEVELOPER.value,
            }
            
            self._teams[team.id] = team
            self._user_teams.setdefault(owner_id, set()).add(team.id)
            self._save_teams()
            
            self._emit_activity(team.id, owner_id, "created", "team", team.id, f"Created team '{team.name}'")
            self._trigger_callback("team_created", team)
            
            return team
    
    def get_team(self, team_id: str) -> Optional[Team]:
        with self._lock:
            return self._teams.get(team_id)
    
    def get_user_teams(self, user_id: str) -> List[Team]:
        with self._lock:
            team_ids = self._user_teams.get(user_id, set())
            return [self._teams[tid] for tid in team_ids if tid in self._teams]
    
    def update_team(self, team_id: str, user_id: str, **updates) -> bool:
        """Update team settings (admin/owner only)."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return False
            
            if not team.has_permission(user_id, "update_team"):
                return False
            
            allowed = {"name", "description", "settings"}
            for key, value in updates.items():
                if key in allowed:
                    setattr(team, key, value)
            
            team.updated_at = datetime.now()
            self._save_teams()
            self._emit_activity(team.id, user_id, "updated", "team", team.id, f"Updated team '{team.name}'")
            return True
    
    def delete_team(self, team_id: str, user_id: str) -> bool:
        """Delete a team (owner only)."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return False
            
            if team.owner_id != user_id:
                return False
            
            # Remove from user teams
            for member_id in team.members:
                self._user_teams.get(member_id, set()).discard(team_id)
            
            del self._teams[team_id]
            self._save_teams()
            self._emit_activity(team_id, user_id, "deleted", "team", team_id, f"Deleted team '{team.name}'")
            return True
    
    # ----------------------------------------------------------------------
    # Member Management
    # ----------------------------------------------------------------------
    
    def invite_member(
        self,
        team_id: str,
        inviter_id: str,
        email: str,
        role: TeamRole = TeamRole.DEVELOPER,
    ) -> Optional[TeamInvitation]:
        """Invite a member to the team."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return None
            
            if not team.has_permission(inviter_id, "invite_members"):
                return None
            
            # Check if already a member
            for member in team.members.values():
                if member.email == email:
                    return None
            
            # Check for existing pending invitation
            for inv in team.invitations.values():
                if inv.email == email and inv.status == InvitationStatus.PENDING:
                    return None
            
            invitation = TeamInvitation(
                id=f"inv_{uuid.uuid4().hex[:8]}",
                team_id=team_id,
                email=email,
                role=role,
                invited_by=inviter_id,
            )
            
            team.invitations[invitation.id] = invitation
            team.updated_at = datetime.now()
            self._save_teams()
            
            self._emit_activity(team_id, inviter_id, "invited", "member", invitation.id, f"Invited {email} as {role.value}")
            self._trigger_callback("invitation_created", invitation)
            
            return invitation
    
    def accept_invitation(self, invitation_id: str, user_id: str, user_email: str, user_name: str) -> bool:
        """Accept a team invitation."""
        with self._lock:
            # Find invitation
            invitation = None
            team = None
            for t in self._teams.values():
                inv = t.invitations.get(invitation_id)
                if inv:
                    invitation = inv
                    team = t
                    break
            
            if not invitation or invitation.status != InvitationStatus.PENDING:
                return False
            
            if invitation.email != user_email:
                return False
            
            if invitation.expires_at < datetime.now():
                invitation.status = InvitationStatus.EXPIRED
                return False
            
            # Accept
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = datetime.now()
            
            # Add as member
            member = TeamMember(
                user_id=user_id,
                email=user_email,
                name=user_name,
                role=invitation.role,
                permissions=self._get_default_permissions(invitation.role),
            )
            team.members[user_id] = member
            del team.invitations[invitation_id]
            team.updated_at = datetime.now()
            
            self._user_teams.setdefault(user_id, set()).add(team.id)
            self._save_teams()
            
            self._emit_activity(team.id, user_id, "joined", "team", team.id, f"Joined team '{team.name}' as {invitation.role.value}")
            self._trigger_callback("invitation_accepted", invitation)
            
            return True
    
    def decline_invitation(self, invitation_id: str, user_email: str) -> bool:
        """Decline a team invitation."""
        with self._lock:
            for team in self._teams.values():
                inv = team.invitations.get(invitation_id)
                if inv and inv.email == user_email and inv.status == InvitationStatus.PENDING:
                    inv.status = InvitationStatus.DECLINED
                    team.updated_at = datetime.now()
                    self._save_teams()
                    return True
        return False
    
    def remove_member(self, team_id: str, remover_id: str, member_id: str) -> bool:
        """Remove a member from the team."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return False
            
            if not team.has_permission(remover_id, "remove_members"):
                return False
            
            if member_id == team.owner_id:
                return False  # Cannot remove owner
            
            if member_id not in team.members:
                return False
            
            del team.members[member_id]
            self._user_teams.get(member_id, set()).discard(team_id)
            team.updated_at = datetime.now()
            self._save_teams()
            
            self._emit_activity(team_id, remover_id, "removed", "member", member_id, f"Removed member from team")
            self._trigger_callback("member_removed", {"team_id": team_id, "member_id": member_id, "removed_by": remover_id})
            return True
    
    def update_member_role(self, team_id: str, updater_id: str, member_id: str, new_role: TeamRole) -> bool:
        """Update a member's role."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return False
            
            if not team.has_permission(updater_id, "manage_roles"):
                return False
            
            if member_id == team.owner_id:
                return False  # Cannot change owner role
            
            member = team.members.get(member_id)
            if not member:
                return False
            
            member.role = new_role
            member.permissions = self._get_default_permissions(new_role)
            team.updated_at = datetime.now()
            self._save_teams()
            
            self._emit_activity(team_id, updater_id, "updated", "member_role", member_id, f"Changed role to {new_role.value}")
            self._trigger_callback("member_updated", {"team_id": team_id, "member_id": member_id, "role": new_role.value})
            return True
    
    def _get_default_permissions(self, role: TeamRole) -> Set[str]:
        if role == TeamRole.OWNER:
            return {"*"}
        elif role == TeamRole.ADMIN:
            return {"invite_members", "remove_members", "update_role", "manage_projects", "manage_settings", "create_sessions"}
        elif role == TeamRole.DEVELOPER:
            return {"create_sessions", "edit_files", "run_commands", "create_tasks"}
        elif role == TeamRole.VIEWER:
            return {"view_files", "view_sessions", "view_tasks"}
        return set()
    
    # ----------------------------------------------------------------------
    # Project Sharing
    # ----------------------------------------------------------------------
    
    def share_project(self, team_id: str, user_id: str, project_id: str) -> bool:
        """Share a project with the team."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return False
            
            if not team.has_permission(user_id, "manage_projects"):
                return False
            
            # Verify project exists and user has access
            project = self._workspace.get_project(project_id)
            if not project:
                return False
            
            team.projects.add(project_id)
            team.updated_at = datetime.now()
            self._save_teams()
            
            self._emit_activity(team_id, user_id, "shared", "project", project_id, f"Shared project with team")
            return True
    
    def unshare_project(self, team_id: str, user_id: str, project_id: str) -> bool:
        """Unshare a project from the team."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return False
            
            if not team.has_permission(user_id, "manage_projects"):
                return False
            
            team.projects.discard(project_id)
            team.updated_at = datetime.now()
            self._save_teams()
            return True
    
    def get_team_projects(self, team_id: str) -> List[Project]:
        """Get all projects shared with the team."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return []
            
            projects = []
            for pid in team.projects:
                project = self._workspace.get_project(pid)
                if project:
                    projects.append(project)
            return projects
    
    # ----------------------------------------------------------------------
    # Activity Feed
    # ----------------------------------------------------------------------
    
    def _emit_activity(
        self,
        team_id: str,
        user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = ActivityEvent(
            id=f"evt_{uuid.uuid4().hex[:8]}",
            team_id=team_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            message=message,
            metadata=metadata or {},
        )
        self._activity_feed.append(event)
        
        # Keep only last 10000 events
        if len(self._activity_feed) > 10000:
            self._activity_feed = self._activity_feed[-10000:]
        
        self._trigger_callback("activity", event)
    
    def get_activity_feed(
        self,
        team_id: str,
        limit: int = 50,
        since: Optional[datetime] = None,
    ) -> List[ActivityEvent]:
        """Get activity feed for a team."""
        with self._lock:
            events = [e for e in self._activity_feed if e.team_id == team_id]
            if since:
                events = [e for e in events if e.timestamp > since]
            events.sort(key=lambda e: e.timestamp, reverse=True)
            return events[:limit]
    
    # ----------------------------------------------------------------------
    # Shared Sessions (Co-editing)
    # ----------------------------------------------------------------------
    
    def create_session(
        self,
        team_id: str,
        project_id: str,
        owner_id: str,
        name: str,
    ) -> Optional[SharedSession]:
        """Create a collaborative editing session."""
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                return None
            
            if not team.has_permission(owner_id, "create_sessions"):
                return None
            
            session = SharedSession(
                id=f"session_{uuid.uuid4().hex[:8]}",
                team_id=team_id,
                project_id=project_id,
                name=name,
                owner_id=owner_id,
                participants={owner_id},
            )
            
            self._sessions[session.id] = session
            self._trigger_callback("session_created", session)
            return session
    
    def join_session(self, session_id: str, user_id: str) -> bool:
        """Join a collaborative session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or not session.is_active:
                return False
            
            session.participants.add(user_id)
            session.last_activity = datetime.now()
            self._trigger_callback("session_updated", session)
            return True
    
    def leave_session(self, session_id: str, user_id: str) -> bool:
        """Leave a collaborative session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            session.participants.discard(user_id)
            session.last_activity = datetime.now()
            
            if not session.participants:
                session.is_active = False
            
            self._trigger_callback("session_updated", session)
            return True
    
    def update_session_state(self, session_id: str, user_id: str, state_update: Dict[str, Any]) -> bool:
        """Update collaborative document state (Yjs-style)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session or user_id not in session.participants:
                return False
            
            session.document_state.update(state_update)
            session.last_activity = datetime.now()
            self._trigger_callback("session_updated", session)
            return True
    
    def get_session(self, session_id: str) -> Optional[SharedSession]:
        with self._lock:
            return self._sessions.get(session_id)
    
    def list_active_sessions(self, team_id: str) -> List[SharedSession]:
        with self._lock:
            return [
                s for s in self._sessions.values()
                if s.team_id == team_id and s.is_active
            ]
    
    # ----------------------------------------------------------------------
    # Callbacks
    # ----------------------------------------------------------------------
    
    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for an event."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def off(self, event: str, callback: Callable) -> None:
        """Unregister a callback."""
        if event in self._callbacks:
            self._callbacks[event] = [c for c in self._callbacks[event] if c != callback]
    
    def _trigger_callback(self, event: str, data: Any) -> None:
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception:
                pass
    
    # ----------------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------------
    
    def cleanup_expired_invitations(self) -> int:
        """Remove expired invitations. Returns count removed."""
        with self._lock:
            count = 0
            now = datetime.now()
            for team in self._teams.values():
                expired = [
                    iid for iid, inv in team.invitations.items()
                    if inv.status == InvitationStatus.PENDING and inv.expires_at < now
                ]
                for iid in expired:
                    team.invitations[iid].status = InvitationStatus.EXPIRED
                    count += 1
            if count > 0:
                self._save_teams()
            return count
    
    def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up inactive sessions. Returns count removed."""
        with self._lock:
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            removed = 0
            for sid, session in list(self._sessions.items()):
                if not session.is_active and session.last_activity < cutoff:
                    del self._sessions[sid]
                    removed += 1
            return removed


# ════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ════════════════════════════════════════════════════════════════════════════

def create_team_workspace(workspace: Optional[WorkspaceManager] = None) -> TeamWorkspaceManager:
    return TeamWorkspaceManager(workspace)


def get_team_workspace() -> TeamWorkspaceManager:
    return create_team_workspace()


# Import uuid at module level
import uuid