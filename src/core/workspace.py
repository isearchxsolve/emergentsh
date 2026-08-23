"""
WorkspaceManager — SQLite-backed persistence for projects, tasks, agents,
artifacts, sessions, and user preferences.

Replaces the JSON-based ConfigManager with a proper relational schema
supporting concurrent access, migrations, and complex queries.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .agent_registry import AgentRole
from .task_graph import ProjectState, Task, TaskStatus, TaskPriority


# ════════════════════════════════════════════════════════════════════════════
# Data Models
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Profile:
    """User profile (API keys, model prefs, rate limits)."""
    id: int
    name: str
    api_key: str
    default_model: str
    rpm: float
    models: Dict[str, Dict[str, str]]  # model_key -> {name, id}
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Profile":
        return cls(
            id=row["id"],
            name=row["name"],
            api_key=row["api_key"],
            default_model=row["default_model"],
            rpm=row["rpm"],
            models=json.loads(row["models_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["models_json"] = json.dumps(self.models)
        return d


@dataclass
class Project:
    """A development project with full configuration."""
    id: str
    name: str
    description: str
    root_dir: str
    tech_stack: Dict[str, str]  # e.g. {"frontend": "nextjs", "backend": "fastapi"}
    target: str  # "web", "mobile", "both"
    profile_id: int
    git_repo_url: Optional[str] = None
    git_branch: str = "main"
    deploy_target: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archived_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Project":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            root_dir=row["root_dir"],
            tech_stack=json.loads(row["tech_stack_json"]),
            target=row["target"],
            profile_id=row["profile_id"],
            git_repo_url=row["git_repo_url"],
            git_branch=row["git_branch"],
            deploy_target=row["deploy_target"],
            environment=json.loads(row["environment_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            archived_at=row["archived_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tech_stack_json"] = json.dumps(self.tech_stack)
        d["environment_json"] = json.dumps(self.environment)
        return d


@dataclass
class TaskRecord:
    """Persisted task record."""
    id: str
    project_id: str
    name: str
    description: str
    role: str  # AgentRole value
    status: str  # TaskStatus value
    priority: int  # TaskPriority value
    dependencies: List[str]
    dependents: List[str]
    input_context: Dict[str, Any]
    output_artifacts: Dict[str, Any]
    assigned_agent_id: Optional[int]
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]
    retry_count: int
    max_retries: int
    tags: List[str]
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TaskRecord":
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            description=row["description"],
            role=row["role"],
            status=row["status"],
            priority=row["priority"],
            dependencies=json.loads(row["dependencies_json"]),
            dependents=json.loads(row["dependents_json"]),
            input_context=json.loads(row["input_context_json"]),
            output_artifacts=json.loads(row["output_artifacts_json"]),
            assigned_agent_id=row["assigned_agent_id"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            tags=json.loads(row["tags_json"]),
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_task(self) -> Task:
        """Convert to in-memory Task object."""
        task = Task(
            id=self.id,
            name=self.name,
            description=self.description,
            role=AgentRole(self.role) if self.role in AgentRole._value2member_map_ else AgentRole.ORCHESTRATOR,
            status=TaskStatus(self.status) if self.status in TaskStatus._value2member_map_ else TaskStatus.PENDING,
            priority=TaskPriority(self.priority),
            dependencies=self.dependencies,
            dependents=self.dependents,
            input_context=self.input_context,
            output_artifacts=self.output_artifacts,
            assigned_agent_id=self.assigned_agent_id,
            started_at=datetime.fromisoformat(self.started_at) if self.started_at else None,
            completed_at=datetime.fromisoformat(self.completed_at) if self.completed_at else None,
            error=self.error,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            tags=set(self.tags),
            metadata=self.metadata,
        )
        return task

    @classmethod
    def from_task(cls, task: Task, project_id: str) -> "TaskRecord":
        return cls(
            id=task.id,
            project_id=project_id,
            name=task.name,
            description=task.description,
            role=task.role.value,
            status=task.status.value,
            priority=task.priority.value,
            dependencies=task.dependencies,
            dependents=task.dependents,
            input_context=task.input_context,
            output_artifacts=task.output_artifacts,
            assigned_agent_id=task.assigned_agent_id,
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            error=task.error,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            tags=list(task.tags),
            metadata=task.metadata,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dependencies_json"] = json.dumps(self.dependencies)
        d["dependents_json"] = json.dumps(self.dependents)
        d["input_context_json"] = json.dumps(self.input_context)
        d["output_artifacts_json"] = json.dumps(self.output_artifacts)
        d["tags_json"] = json.dumps(self.tags)
        d["metadata_json"] = json.dumps(self.metadata)
        return d


@dataclass
class Artifact:
    """Generated artifact (file, spec, config, etc.)."""
    id: str
    project_id: str
    task_id: str
    agent_role: str
    kind: str  # "file", "spec", "config", "test", "doc", "deployment"
    path: str
    content: str
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Artifact":
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            task_id=row["task_id"],
            agent_role=row["agent_role"],
            kind=row["kind"],
            path=row["path"],
            content=row["content"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["metadata_json"] = json.dumps(self.metadata)
        return d


@dataclass
class Session:
    """Agent session (conversation history)."""
    id: str
    project_id: str
    profile_name: str
    messages: List[Dict[str, Any]]
    goal: Optional[str]
    compaction_summary: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Session":
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            profile_name=row["profile_name"],
            messages=json.loads(row["messages_json"]),
            goal=row["goal"],
            compaction_summary=row["compaction_summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["messages_json"] = json.dumps(self.messages)
        return d


@dataclass
class Deployment:
    """Deployment record."""
    id: str
    project_id: str
    target: str  # "vercel", "netlify", "fly", "custom"
    url: Optional[str]
    status: str  # "pending", "building", "deployed", "failed"
    logs: str
    environment: Dict[str, str]
    created_at: str
    completed_at: Optional[str]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Deployment":
        return cls(
            id=row["id"],
            project_id=row["project_id"],
            target=row["target"],
            url=row["url"],
            status=row["status"],
            logs=row["logs"],
            environment=json.loads(row["environment_json"]),
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["environment_json"] = json.dumps(self.environment)
        return d


# ════════════════════════════════════════════════════════════════════════════
# Schema & Migrations
# ════════════════════════════════════════════════════════════════════════════

SCHEMA_VERSION = 3

SCHEMA = """
-- Profiles (API keys, model preferences, rate limits)
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    api_key TEXT NOT NULL,
    default_model TEXT NOT NULL,
    rpm REAL NOT NULL,
    models_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Projects (top-level development projects)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    root_dir TEXT NOT NULL,
    tech_stack_json TEXT NOT NULL DEFAULT '{}',
    target TEXT NOT NULL DEFAULT 'web',
    profile_id INTEGER NOT NULL REFERENCES profiles(id),
    git_repo_url TEXT,
    git_branch TEXT DEFAULT 'main',
    deploy_target TEXT,
    environment_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

-- Tasks (work items in a project)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 50,
    dependencies_json TEXT NOT NULL DEFAULT '[]',
    dependents_json TEXT NOT NULL DEFAULT '[]',
    input_context_json TEXT NOT NULL DEFAULT '{}',
    output_artifacts_json TEXT NOT NULL DEFAULT '{}',
    assigned_agent_id INTEGER,
    started_at TEXT,
    completed_at TEXT,
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 2,
    tags_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Artifacts (generated files, specs, configs)
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent_role TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Sessions (conversation history per project+profile)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    profile_name TEXT NOT NULL,
    messages_json TEXT NOT NULL DEFAULT '[]',
    goal TEXT,
    compaction_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Deployments (deployment history)
CREATE TABLE IF NOT EXISTS deployments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target TEXT NOT NULL,
    url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    logs TEXT DEFAULT '',
    environment_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

-- User preferences (key-value settings)
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_artifacts_project ON artifacts(project_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_deployments_project ON deployments(project_id);
"""


# ════════════════════════════════════════════════════════════════════════════
# WorkspaceManager
# ════════════════════════════════════════════════════════════════════════════

class WorkspaceManager:
    """
    SQLite-backed workspace persistence.

    Thread-safe via per-thread connections. Handles schema migrations,
    provides CRUD for all entities, and supports the orchestration layer.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / ".emergentsh_workspace.db")
        self._db_path = db_path
        self._local = threading.local()
        self._init_db()

    # ----------------------------------------------------------------------
    # Connection management
    # ----------------------------------------------------------------------
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self) -> None:
        """Initialize database and run migrations."""
        conn = self._get_conn()
        conn.executescript(SCHEMA)
        self._migrate(conn)
        conn.commit()

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Run schema migrations."""
        # Check current version
        row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
        current_version = row["version"] if row else 0

        if current_version < SCHEMA_VERSION:
            # Migration 1: Add preferences table (already in base schema)
            if current_version < 1:
                conn.execute("""
                    INSERT OR REPLACE INTO schema_version (version, applied_at)
                    VALUES (1, ?)
                """, (datetime.now().isoformat(),))

            # Migration 2: Add deployments table (already in base schema)
            if current_version < 2:
                conn.execute("""
                    INSERT OR REPLACE INTO schema_version (version, applied_at)
                    VALUES (2, ?)
                """, (datetime.now().isoformat(),))

            # Migration 3: Add artifact kind column (already in base schema)
            if current_version < 3:
                conn.execute("""
                    INSERT OR REPLACE INTO schema_version (version, applied_at)
                    VALUES (3, ?)
                """, (datetime.now().isoformat(),))

    # ----------------------------------------------------------------------
    # Profiles
    # ----------------------------------------------------------------------
    def create_profile(
        self,
        name: str,
        api_key: str,
        default_model: str = "glm",
        rpm: float = 40.0,
        models: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> int:
        """Create a new profile. Returns profile ID."""
        now = datetime.now().isoformat()
        if models is None:
            models = {
                "glm": {"name": "GLM-5.2", "id": "z-ai/glm-5.2"},
                "nemotron": {"name": "Nemotron-Ultra", "id": "nvidia/nemotron-3-ultra-550b-a55b"},
            }
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO profiles (name, api_key, default_model, rpm, models_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, api_key, default_model, rpm, json.dumps(models), now, now))
            return cursor.lastrowid

    def get_profile(self, profile_id: int) -> Optional[Profile]:
        row = self._get_conn().execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        return Profile.from_row(row) if row else None

    def get_profile_by_name(self, name: str) -> Optional[Profile]:
        row = self._get_conn().execute(
            "SELECT * FROM profiles WHERE name = ?", (name,)
        ).fetchone()
        return Profile.from_row(row) if row else None

    def list_profiles(self) -> List[Profile]:
        rows = self._get_conn().execute(
            "SELECT * FROM profiles ORDER BY created_at DESC"
        ).fetchall()
        return [Profile.from_row(r) for r in rows]

    def update_profile(self, profile_id: int, **updates) -> bool:
        """Update profile fields. Allowed: name, api_key, default_model, rpm, models."""
        allowed = {"name", "api_key", "default_model", "rpm", "models"}
        sets = []
        values = []
        for k, v in updates.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                values.append(json.dumps(v) if k == "models" else v)
        if not sets:
            return False
        sets.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(profile_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE profiles SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0

    def delete_profile(self, profile_id: int) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            return cursor.rowcount > 0

    # ----------------------------------------------------------------------
    # Projects
    # ----------------------------------------------------------------------
    def create_project(self, project: Project) -> str:
        """Create a new project. Returns project ID."""
        data = project.to_dict()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO projects (id, name, description, root_dir, tech_stack_json, target,
                                    profile_id, git_repo_url, git_branch, deploy_target,
                                    environment_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["id"], data["name"], data["description"], data["root_dir"],
                data["tech_stack_json"], data["target"], data["profile_id"],
                data["git_repo_url"], data["git_branch"], data["deploy_target"],
                data["environment_json"], data["created_at"], data["updated_at"]
            ))
        return project.id

    def get_project(self, project_id: str) -> Optional[Project]:
        row = self._get_conn().execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return Project.from_row(row) if row else None

    def get_project_by_name(self, name: str) -> Optional[Project]:
        row = self._get_conn().execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return Project.from_row(row) if row else None

    def list_projects(self, include_archived: bool = False) -> List[Project]:
        query = "SELECT * FROM projects"
        if not include_archived:
            query += " WHERE archived_at IS NULL"
        query += " ORDER BY updated_at DESC"
        rows = self._get_conn().execute(query).fetchall()
        return [Project.from_row(r) for r in rows]

    def update_project(self, project_id: str, **updates) -> bool:
        """Update project fields."""
        allowed = {
            "name", "description", "root_dir", "tech_stack", "target",
            "profile_id", "git_repo_url", "git_branch", "deploy_target",
            "environment", "archived_at"
        }
        sets = []
        values = []
        for k, v in updates.items():
            if k in allowed:
                col = k
                if k in ("tech_stack", "environment"):
                    col = f"{k}_json"
                    v = json.dumps(v)
                sets.append(f"{col} = ?")
                values.append(v)
        if not sets:
            return False
        sets.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(project_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE projects SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0

    def delete_project(self, project_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    # ----------------------------------------------------------------------
    # Tasks
    # ----------------------------------------------------------------------
    def save_task(self, task: Task, project_id: str) -> None:
        """Insert or update a task."""
        record = TaskRecord.from_task(task, project_id)
        data = record.to_dict()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO tasks (id, project_id, name, description, role, status, priority,
                                 dependencies_json, dependents_json, input_context_json,
                                 output_artifacts_json, assigned_agent_id, started_at,
                                 completed_at, error, retry_count, max_retries,
                                 tags_json, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, description=excluded.description, role=excluded.role,
                    status=excluded.status, priority=excluded.priority,
                    dependencies_json=excluded.dependencies_json, dependents_json=excluded.dependents_json,
                    input_context_json=excluded.input_context_json, output_artifacts_json=excluded.output_artifacts_json,
                    assigned_agent_id=excluded.assigned_agent_id, started_at=excluded.started_at,
                    completed_at=excluded.completed_at, error=excluded.error,
                    retry_count=excluded.retry_count, max_retries=excluded.max_retries,
                    tags_json=excluded.tags_json, metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
            """, (
                data["id"], data["project_id"], data["name"], data["description"],
                data["role"], data["status"], data["priority"],
                data["dependencies_json"], data["dependents_json"],
                data["input_context_json"], data["output_artifacts_json"],
                data["assigned_agent_id"], data["started_at"], data["completed_at"],
                data["error"], data["retry_count"], data["max_retries"],
                data["tags_json"], data["metadata_json"],
                data["created_at"], data["updated_at"]
            ))

    def get_task(self, task_id: str) -> Optional[Task]:
        row = self._get_conn().execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return TaskRecord.from_row(row).to_task() if row else None

    def get_tasks_for_project(self, project_id: str) -> List[Task]:
        rows = self._get_conn().execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at", (project_id,)
        ).fetchall()
        return [TaskRecord.from_row(r).to_task() for r in rows]

    def get_ready_tasks(self, project_id: str, completed_ids: set) -> List[Task]:
        """Get tasks that are pending and have all dependencies satisfied."""
        rows = self._get_conn().execute(
            "SELECT * FROM tasks WHERE project_id = ? AND status = 'pending'",
            (project_id,)
        ).fetchall()
        ready = []
        for row in rows:
            task = TaskRecord.from_row(row).to_task()
            if task.is_ready(completed_ids):
                ready.append(task)
        ready.sort(key=lambda t: (-t.priority.value, t.id))
        return ready

    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        with self.transaction() as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, task_id),
            )
            return cursor.rowcount > 0

    def delete_task(self, task_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    # ----------------------------------------------------------------------
    # Artifacts
    # ----------------------------------------------------------------------
    def save_artifact(self, artifact: Artifact) -> None:
        data = artifact.to_dict()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO artifacts (id, project_id, task_id, agent_role, kind, path, content,
                                     metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id, task_id=excluded.task_id,
                    agent_role=excluded.agent_role, kind=excluded.kind, path=excluded.path,
                    content=excluded.content, metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
            """, (
                data["id"], data["project_id"], data["task_id"], data["agent_role"],
                data["kind"], data["path"], data["content"], data["metadata_json"],
                data["created_at"], data["updated_at"]
            ))

    def get_artifacts_for_project(self, project_id: str) -> List[Artifact]:
        rows = self._get_conn().execute(
            "SELECT * FROM artifacts WHERE project_id = ? ORDER BY created_at", (project_id,)
        ).fetchall()
        return [Artifact.from_row(r) for r in rows]

    def get_artifacts_for_task(self, task_id: str) -> List[Artifact]:
        rows = self._get_conn().execute(
            "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at", (task_id,)
        ).fetchall()
        return [Artifact.from_row(r) for r in rows]

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        row = self._get_conn().execute(
            "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        return Artifact.from_row(row) if row else None

    def delete_artifact(self, artifact_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
            return cursor.rowcount > 0

    # ----------------------------------------------------------------------
    # Sessions
    # ----------------------------------------------------------------------
    def save_session(self, session: Session) -> None:
        data = session.to_dict()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO sessions (id, project_id, profile_name, messages_json, goal,
                                    compaction_summary, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    messages_json=excluded.messages_json, goal=excluded.goal,
                    compaction_summary=excluded.compaction_summary, updated_at=excluded.updated_at
            """, (
                data["id"], data["project_id"], data["profile_name"],
                data["messages_json"], data["goal"], data["compaction_summary"],
                data["created_at"], data["updated_at"]
            ))

    def get_session(self, session_id: str) -> Optional[Session]:
        row = self._get_conn().execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return Session.from_row(row) if row else None

    def get_sessions_for_project(self, project_id: str) -> List[Session]:
        rows = self._get_conn().execute(
            "SELECT * FROM sessions WHERE project_id = ? ORDER BY updated_at DESC", (project_id,)
        ).fetchall()
        return [Session.from_row(r) for r in rows]

    def delete_session(self, session_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    # ----------------------------------------------------------------------
    # Deployments
    # ----------------------------------------------------------------------
    def save_deployment(self, deployment: Deployment) -> None:
        data = deployment.to_dict()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO deployments (id, project_id, target, url, status, logs,
                                       environment_json, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url, status=excluded.status, logs=excluded.logs,
                    environment_json=excluded.environment_json, completed_at=excluded.completed_at
            """, (
                data["id"], data["project_id"], data["target"], data["url"],
                data["status"], data["logs"], data["environment_json"],
                data["created_at"], data["completed_at"]
            ))

    def get_deployments_for_project(self, project_id: str) -> List[Deployment]:
        rows = self._get_conn().execute(
            "SELECT * FROM deployments WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
        return [Deployment.from_row(r) for r in rows]

    # ----------------------------------------------------------------------
    # Preferences
    # ----------------------------------------------------------------------
    def set_preference(self, key: str, value: Any) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO preferences (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """, (key, json.dumps(value), datetime.now().isoformat()))

    def get_preference(self, key: str, default: Any = None) -> Any:
        row = self._get_conn().execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row["value"]) if row else default

    # ----------------------------------------------------------------------
    # Migration from old JSON config
    # ----------------------------------------------------------------------
    def migrate_from_json(self, json_config_path: str, json_sessions_path: str) -> Dict[str, int]:
        """Migrate from old JSON-based ConfigManager files."""
        stats = {"profiles": 0, "sessions": 0, "projects": 0}

        # Migrate profiles
        if os.path.exists(json_config_path):
            with open(json_config_path, "r") as f:
                data = json.load(f)
            for pid, p in data.get("profiles", {}).items():
                if not self.get_profile_by_name(p.get("name", "")):
                    self.create_profile(
                        name=p.get("name", f"Profile {pid}"),
                        api_key=p.get("key", ""),
                        default_model=p.get("default_model", "glm"),
                        rpm=p.get("rpm", 40.0),
                        models=p.get("models"),
                    )
                    stats["profiles"] += 1

        # Migrate sessions (create a default project if needed)
        if os.path.exists(json_sessions_path):
            with open(json_sessions_path, "r") as f:
                sessions_data = json.load(f)
            for key, s in sessions_data.items():
                # Parse key: "ProfileName::/path/to/dir"
                if "::" in key:
                    profile_name, project_dir = key.split("::", 1)
                    profile = self.get_profile_by_name(profile_name)
                    if not profile:
                        continue
                    # Create or find project
                    project_name = os.path.basename(project_dir) or "Migrated Project"
                    project = self.get_project_by_name(project_name)
                    if not project:
                        project = Project(
                            id=f"migrated-{abs(hash(key)) % 1000000:06d}",
                            name=project_name,
                            description="Migrated from JSON config",
                            root_dir=project_dir,
                            tech_stack={},
                            target="web",
                            profile_id=profile.id,
                        )
                        self.create_project(project)
                        stats["projects"] += 1
                    # Create session
                    session = Session(
                        id=f"session-{abs(hash(key)) % 1000000:06d}",
                        project_id=project.id,
                        profile_name=profile_name,
                        messages=s.get("messages", []),
                        goal=s.get("goal"),
                        compaction_summary=s.get("compaction_summary"),
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )
                    self.save_session(session)
                    stats["sessions"] += 1

        return stats

    # ----------------------------------------------------------------------
    # ProjectState serialization
    # ----------------------------------------------------------------------
    def save_project_state(self, state: ProjectState) -> None:
        """Persist the full ProjectState to the database."""
        project_id = state.project_id
        # Save/update project
        project = self.get_project(project_id)
        if not project:
            project = Project(
                id=state.project_id,
                name=state.name,
                description=state.description,
                root_dir=state.root_dir if hasattr(state, "root_dir") else ".",
                tech_stack=state.tech_stack,
                target="web",
                profile_id=1,  # default, will be updated
            )
            self.create_project(project)

        # Update project with state
        self.update_project(project_id, tech_stack=state.tech_stack)

        # Save all tasks
        for task in state.tasks.values() if hasattr(state, "tasks") else []:
            self.save_task(task, project_id)

        # Save all artifacts
        for task_id, artifacts in state.artifacts.items():
            for kind, content in artifacts.items():
                if isinstance(content, str) and (content.startswith("/") or "/" in content):
                    # It's a file path
                    artifact = Artifact(
                        id=f"art-{abs(hash(f'{task_id}:{kind}')) % 1000000:06d}",
                        project_id=project_id,
                        task_id=task_id,
                        agent_role="unknown",
                        kind="file",
                        path=kind,
                        content=content,
                        metadata={},
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )
                    self.save_artifact(artifact)

    def load_project_state(self, project_id: str) -> Optional[ProjectState]:
        """Load a full ProjectState from the database."""
        project = self.get_project(project_id)
        if not project:
            return None

        tasks = self.get_tasks_for_project(project_id)
        artifacts_by_task: Dict[str, Dict[str, Any]] = {}

        for task in tasks:
            artifacts = self.get_artifacts_for_task(task.id)
            artifacts_by_task[task.id] = {a.path: a.content for a in artifacts}

        state = ProjectState(
            project_id=project.id,
            name=project.name,
            description=project.description,
            tech_stack=project.tech_stack,
            architecture_decisions=[],
        )
        # Note: ProjectState doesn't have a tasks dict by default
        # This would need to be extended if we want full round-trip
        return state


# Global singleton
_WORKSPACE: Optional[WorkspaceManager] = None


def get_workspace(db_path: Optional[str] = None) -> WorkspaceManager:
    global _WORKSPACE
    if _WORKSPACE is None:
        _WORKSPACE = WorkspaceManager(db_path)
    return _WORKSPACE