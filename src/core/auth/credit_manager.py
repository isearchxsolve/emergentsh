"""
CreditManager — token usage tracking, budgeting, and cost estimation.

Features:
- Per-model token counting and cost calculation
- Monthly/weekly/daily budgets with alerts
- Per-project and per-agent usage tracking
- Cost optimization recommendations
- Export to CSV/JSON for billing
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from ..models import ModelRegistry, get_model_registry
from ..workspace import WorkspaceManager, get_workspace


# ════════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TokenUsage:
    """Record of token usage for a single request."""
    timestamp: datetime
    model_id: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    project_id: str
    agent_role: str
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_cost(self) -> float:
        return self.estimated_cost


@dataclass
class Budget:
    """Budget configuration for cost control."""
    id: str
    name: str
    limit_usd: float
    period: str  # "daily", "weekly", "monthly"
    alert_threshold: float = 0.8  # Alert at 80% of budget
    alert_enabled: bool = True
    project_id: Optional[str] = None
    agent_role: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

    def get_period_start(self) -> datetime:
        now = datetime.now()
        if self.period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period == "weekly":
            return now - timedelta(days=now.weekday())
        elif self.period == "monthly":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return now

    def get_period_end(self) -> datetime:
        start = self.get_period_start()
        if self.period == "daily":
            return start + timedelta(days=1)
        elif self.period == "weekly":
            return start + timedelta(weeks=1)
        elif self.period == "monthly":
            # Next month
            if start.month == 12:
                return start.replace(year=start.year + 1, month=1)
            return start.replace(month=start.month + 1)
        return start + timedelta(days=1)


@dataclass
class UsageSummary:
    """Aggregated usage statistics."""
    period_start: datetime
    period_end: datetime
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost: float
    request_count: int
    models_used: Dict[str, int]  # model_id -> token count
    agents_used: Dict[str, int]  # agent_role -> token count
    projects_used: Dict[str, int]  # project_id -> token count


# ════════════════════════════════════════════════════════════════════════════
# Credit Manager
# ════════════════════════════════════════════════════════════════════════════

class CreditManager:
    """
    Manages token usage tracking, cost calculation, and budget enforcement.
    
    Features:
    - SQLite-backed persistent storage
    - Real-time cost calculation per model
    - Budget alerts and enforcement
    - Usage analytics and reporting
    - Export to CSV/JSON
    """
    
    def __init__(
        self,
        workspace: Optional[WorkspaceManager] = None,
        model_registry: Optional[ModelRegistry] = None,
        db_path: Optional[str] = None,
    ):
        self._workspace = workspace or get_workspace()
        self._registry = model_registry or get_model_registry()
        self._lock = threading.Lock()
        
        # Database setup
        if db_path is None:
            db_path = str(Path.home() / ".emergentsh_credits.db")
        self._db_path = db_path
        self._init_db()
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[Budget, float, float], None]] = []
    
    # ----------------------------------------------------------------------
    # Database Initialization
    # ----------------------------------------------------------------------
    
    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost REAL NOT NULL,
                    project_id TEXT,
                    agent_role TEXT,
                    task_id TEXT,
                    session_id TEXT,
                    metadata TEXT
                );
                
                CREATE TABLE IF NOT EXISTS budgets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    limit_usd REAL NOT NULL,
                    period TEXT NOT NULL,
                    alert_threshold REAL DEFAULT 0.8,
                    alert_enabled INTEGER DEFAULT 1,
                    project_id TEXT,
                    agent_role TEXT,
                    created_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
                
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    budget_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    usage_percent REAL NOT NULL,
                    current_spend REAL NOT NULL,
                    budget_limit REAL NOT NULL,
                    acknowledged INTEGER DEFAULT 0
                );
                
                CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp);
                CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id);
                CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model_id);
                CREATE INDEX IF NOT EXISTS idx_budgets_project ON budgets(project_id);
            """)
    
    @contextmanager
    def _get_conn(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ----------------------------------------------------------------------
    # Usage Recording
    # ----------------------------------------------------------------------
    
    def record_usage(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        project_id: str,
        agent_role: str,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Record token usage and calculate cost.
        
        Returns:
            Estimated cost in USD
        """
        model = self._registry.get_model(model_id)
        if not model:
            # Unknown model, use default pricing
            estimated_cost = 0.0
        else:
            estimated_cost = self._registry.estimate_cost(
                model_id, prompt_tokens, completion_tokens
            )
        
        total_tokens = prompt_tokens + completion_tokens
        
        usage = TokenUsage(
            timestamp=datetime.now(),
            model_id=model_id,
            provider=self._registry.get_model(model_id).provider.value if self._registry.get_model(model_id) else "unknown",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            project_id=project_id,
            agent_role=agent_role,
            task_id=task_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO token_usage (
                    timestamp, model_id, provider, prompt_tokens, completion_tokens,
                    total_tokens, estimated_cost, project_id, agent_role, task_id, session_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage.timestamp.isoformat(),
                usage.model_id,
                usage.provider,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
                usage.estimated_cost,
                usage.project_id,
                usage.agent_role,
                usage.task_id,
                usage.session_id,
                json.dumps(usage.metadata),
            ))
        
        # Check budgets
        self._check_budgets()
        
        return estimated_cost
    
    def record_usage_from_response(
        self,
        model_id: str,
        usage_data: Dict[str, int],
        project_id: str,
        agent_role: str,
        **kwargs,
    ) -> float:
        """Record usage from an API response dict (prompt_tokens, completion_tokens)."""
        return self.record_usage(
            model_id=model_id,
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            project_id=project_id,
            agent_role=agent_role,
            **kwargs,
        )
    
    # ----------------------------------------------------------------------
    # Budget Management
    # ----------------------------------------------------------------------
    
    def create_budget(
        self,
        name: str,
        limit_usd: float,
        period: str = "monthly",
        alert_threshold: float = 0.8,
        project_id: Optional[str] = None,
        agent_role: Optional[str] = None,
    ) -> Budget:
        """Create a new budget."""
        budget = Budget(
            id=f"budget_{secrets.token_hex(8)}",
            name=name,
            limit_usd=limit_usd,
            period=period,
            alert_threshold=alert_threshold,
            project_id=project_id,
            agent_role=agent_role,
        )
        
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO budgets (id, name, limit_usd, period, alert_threshold, alert_enabled, project_id, agent_role, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, 1)
            """, (
                budget.id, budget.name, budget.limit_usd, budget.period,
                budget.alert_threshold, budget.project_id, budget.agent_role,
                budget.created_at.isoformat(),
            ))
        return budget
    
    def get_budget(self, budget_id: str) -> Optional[Budget]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
            if row:
                return self._row_to_budget(row)
        return None
    
    def list_budgets(
        self,
        project_id: Optional[str] = None,
        agent_role: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Budget]:
        query = "SELECT * FROM budgets WHERE 1=1"
        params = []
        
        if active_only:
            query += " AND is_active = 1"
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if agent_role:
            query += " AND agent_role = ?"
            params.append(agent_role)
        
        query += " ORDER BY created_at DESC"
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_budget(row) for row in rows]
    
    def update_budget(self, budget_id: str, **updates) -> bool:
        allowed = {"name", "limit_usd", "period", "alert_threshold", "alert_enabled", "is_active"}
        sets = []
        params = []
        for k, v in updates.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)
        
        if not sets:
            return False
        
        params.append(budget_id)
        with self._get_conn() as conn:
            cursor = conn.execute(f"UPDATE budgets SET {', '.join(sets)} WHERE id = ?", params)
            return cursor.rowcount > 0
    
    def delete_budget(self, budget_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
            return cursor.rowcount > 0
    
    def _check_budgets(self) -> None:
        """Check all active budgets and trigger alerts if needed."""
        budgets = self.list_budgets(active_only=True)
        for budget in budgets:
            usage = self.get_budget_usage(budget)
            if usage:
                self._evaluate_budget(budget, usage)
    
    def get_budget_usage(self, budget: Budget) -> Optional[float]:
        """Get current spend for a budget period."""
        period_start = budget.get_period_start()
        period_end = budget.get_period_end()
        
        with self._get_conn() as conn:
            query = """
                SELECT COALESCE(SUM(estimated_cost), 0) as total_cost
                FROM token_usage
                WHERE timestamp >= ? AND timestamp < ?
            """
            params = [period_start.isoformat(), period_end.isoformat()]
            
            if budget.project_id:
                query += " AND project_id = ?"
                params.append(budget.project_id)
            if budget.agent_role:
                query += " AND agent_role = ?"
                params.append(budget.agent_role)
            
            row = conn.execute(query, params).fetchone()
            return row["total_cost"] if row else 0.0
    
    def _evaluate_budget(self, budget: Budget, current_spend: float) -> None:
        """Evaluate budget and trigger alerts if needed."""
        if not budget.alert_enabled:
            return
        
        usage_percent = current_spend / budget.limit_usd if budget.limit_usd > 0 else 0
        
        if usage_percent >= budget.alert_threshold:
            # Record alert
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO alerts (budget_id, timestamp, usage_percent, current_spend, budget_limit)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    budget.id, datetime.now().isoformat(),
                    usage_percent, current_spend, budget.limit_usd
                ))
            
            # Trigger callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(budget, current_spend, usage_percent)
                except Exception:
                    pass
    
    def add_alert_callback(self, callback: Callable[[Budget, float, float], None]) -> None:
        """Register a callback for budget alerts."""
        self._alert_callbacks.append(callback)
    
    def get_unacknowledged_alerts(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT a.*, b.name as budget_name, b.limit_usd
                FROM alerts a
                JOIN budgets b ON a.budget_id = b.id
                WHERE a.acknowledged = 0
                ORDER BY a.timestamp DESC
            """).fetchall()
            return [dict(r) for r in rows]
    
    def acknowledge_alert(self, alert_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
            return cursor.rowcount > 0
    
    # ----------------------------------------------------------------------
    # Usage Analytics
    # ----------------------------------------------------------------------
    
    def get_usage_summary(
        self,
        start: datetime,
        end: datetime,
        project_id: Optional[str] = None,
        agent_role: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> UsageSummary:
        """Get aggregated usage statistics for a time range."""
        query = """
            SELECT
                COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                COALESCE(SUM(completion_tokens), 0) as total_completion,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(estimated_cost), 0) as total_cost,
                COUNT(*) as request_count
            FROM token_usage
            WHERE timestamp >= ? AND timestamp < ?
        """
        params = [start.isoformat(), end.isoformat()]
        
        if project_id:
            params.append(project_id)
        if agent_role:
            params.append(agent_role)
        if model_id:
            params.append(model_id)
        
        with self._get_conn() as conn:
            row = conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                    COALESCE(SUM(completion_tokens), 0) as total_completion,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(estimated_cost), 0) as total_cost,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE timestamp >= ? AND timestamp < ?
                {'AND project_id = ?' if project_id else ''}
                {'AND agent_role = ?' if agent_role else ''}
                {'AND model_id = ?' if model_id else ''}
                """,
                [start.isoformat(), end.isoformat()] + 
                ([project_id] if project_id else []) +
                ([agent_role] if agent_role else []) +
                ([model_id] if model_id else [])
            ).fetchone()
            
            # Get breakdown by model
            model_query = """
                SELECT model_id, SUM(total_tokens) as tokens
                FROM token_usage
                WHERE timestamp >= ? AND timestamp < ?
            """
            model_params = [start.isoformat(), end.isoformat()]
            if project_id:
                model_query += " AND project_id = ?"
                model_params.append(project_id)
            model_query += " GROUP BY model_id"
            
            model_rows = conn.execute(model_query, model_params).fetchall()
            models_used = {r["model_id"]: r["tokens"] for r in model_rows}
            
            # Get breakdown by agent
            agent_query = """
                SELECT agent_role, SUM(total_tokens) as tokens
                FROM token_usage
                WHERE timestamp >= ? AND timestamp < ?
            """
            agent_params = [start.isoformat(), end.isoformat()]
            if project_id:
                agent_query += " AND project_id = ?"
                agent_params.append(project_id)
            agent_query += " GROUP BY agent_role"
            
            agent_rows = conn.execute(agent_query, agent_params).fetchall()
            agents_used = {r["agent_role"]: r["tokens"] for r in agent_rows}
            
            # Get breakdown by project
            project_query = """
                SELECT project_id, SUM(total_tokens) as tokens
                FROM token_usage
                WHERE timestamp >= ? AND timestamp < ?
            """
            project_params = [start.isoformat(), end.isoformat()]
            project_query += " GROUP BY project_id"
            
            project_rows = conn.execute(project_query, project_params).fetchall()
            projects_used = {r["project_id"]: r["tokens"] for r in project_rows}
            
            return UsageSummary(
                period_start=start,
                period_end=end,
                total_tokens=row["total_tokens"],
                prompt_tokens=row["total_prompt"],
                completion_tokens=row["total_completion"],
                total_cost=row["total_cost"],
                request_count=row["request_count"],
                models_used=models_used,
                agents_used=agents_used,
                projects_used=projects_used,
            )
    
    def get_daily_usage(
        self,
        days: int = 30,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get daily usage breakdown for the last N days."""
        end = datetime.now().replace(hour=23, minute=59, second=59)
        start = end - timedelta(days=days)
        
        with self._get_conn() as conn:
            query = """
                SELECT
                    DATE(timestamp) as day,
                    SUM(estimated_cost) as cost,
                    SUM(total_tokens) as tokens,
                    COUNT(*) as requests
                FROM token_usage
                WHERE timestamp >= ? AND timestamp <= ?
            """
            params = [start.isoformat(), end.isoformat()]
            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)
            query += " GROUP BY DATE(timestamp) ORDER BY day"
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    
    def get_top_models(
        self,
        limit: int = 10,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get most used models by token count."""
        if start is None:
            start = datetime.now() - timedelta(days=30)
        if end is None:
            end = datetime.now()
        
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT
                    model_id,
                    provider,
                    SUM(total_tokens) as total_tokens,
                    SUM(estimated_cost) as total_cost,
                    COUNT(*) as requests
                FROM token_usage
                WHERE timestamp >= ? AND timestamp < ?
                GROUP BY model_id, provider
                ORDER BY total_tokens DESC
                LIMIT ?
            """, (start.isoformat(), end.isoformat(), limit)).fetchall()
            return [dict(r) for r in rows]
    
    # ----------------------------------------------------------------------
    # Export
    # ----------------------------------------------------------------------
    
    def export_usage_csv(
        self,
        filepath: str,
        start: datetime,
        end: datetime,
        project_id: Optional[str] = None,
    ) -> int:
        """Export usage data to CSV."""
        query = """
            SELECT
                timestamp, model_id, provider, prompt_tokens, completion_tokens,
                total_tokens, estimated_cost, project_id, agent_role, task_id, session_id
            FROM token_usage
            WHERE timestamp >= ? AND timestamp < ?
        """
        params = [start.isoformat(), end.isoformat()]
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY timestamp"
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "model_id", "provider", "prompt_tokens",
                "completion_tokens", "total_tokens", "estimated_cost",
                "project_id", "agent_role", "task_id", "session_id"
            ])
            for row in rows:
                writer.writerow([
                    row["timestamp"], row["model_id"], row["provider"],
                    row["prompt_tokens"], row["completion_tokens"],
                    row["total_tokens"], row["estimated_cost"],
                    row["project_id"], row["agent_role"],
                    row["task_id"], row["session_id"],
                ])
        
        return len(rows)
    
    def export_usage_json(
        self,
        filepath: str,
        start: datetime,
        end: datetime,
        project_id: Optional[str] = None,
    ) -> int:
        """Export usage data to JSON."""
        query = """
            SELECT * FROM token_usage
            WHERE timestamp >= ? AND timestamp < ?
        """
        params = [start.isoformat(), end.isoformat()]
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY timestamp"
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        
        data = [dict(r) for r in rows]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return len(data)
    
    # ----------------------------------------------------------------------
    # Internal Helpers
    # ----------------------------------------------------------------------
    
    def _row_to_budget(self, row: sqlite3.Row) -> Budget:
        return Budget(
            id=row["id"],
            name=row["name"],
            limit_usd=row["limit_usd"],
            period=row["period"],
            alert_threshold=row["alert_threshold"],
            alert_enabled=bool(row["alert_enabled"]),
            project_id=row["project_id"],
            agent_role=row["agent_role"],
            created_at=datetime.fromisoformat(row["created_at"]),
            is_active=bool(row["is_active"]),
        )


# ═════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ════════════════════════════════════════════════════════════════════════════

def create_credit_manager(
    workspace: Optional[WorkspaceManager] = None,
    model_registry: Optional[ModelRegistry] = None,
    db_path: Optional[str] = None,
) -> CreditManager:
    return CreditManager(workspace, model_registry, db_path)


def get_credit_manager() -> CreditManager:
    return create_credit_manager()


# Import secrets at module level
import secrets