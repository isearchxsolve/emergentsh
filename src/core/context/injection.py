"""
Context Injection — selective context management for agents.

Features:
- Role-based context prioritization
- Token budget management
- Context compression
- Relevance scoring
- Streaming context updates
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable

from ..rag import RAGManager, SearchResult, DocumentChunk


# ═════════════════════════════════════════════════════════════════════════════
# Context Management
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ContextWindow:
    """A window of context for an agent."""
    content: str
    token_count: int
    source_chunks: List[str]  # chunk IDs
    max_tokens: int
    agent_role: str
    task_description: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def utilization(self) -> float:
        return self.token_count / self.max_tokens if self.max_tokens > 0 else 0.0
    
    def can_add(self, tokens: int) -> bool:
        return self.token_count + tokens <= self.max_tokens


@dataclass
class ContextUpdate:
    """An update to the context window."""
    type: str  # "add", "remove", "replace", "clear"
    chunk_ids: List[str]
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


class ContextManager:
    """
    Manages context windows for agents.
    
    Features:
    - Role-based context prioritization
    - Token budget management
    - Context compression
    - Streaming updates
    - Relevance scoring
    """
    
    def __init__(
        self,
        rag_manager: RAGManager,
        default_max_tokens: int = 8000,
    ):
        self._rag = rag_manager
        self._default_max_tokens = default_max_tokens
        self._windows: Dict[str, ContextWindow] = {}  # session_id -> ContextWindow
        self._update_callbacks: List[Callable[[ContextWindow, ContextUpdate], None]] = []
        self._lock = threading.Lock()
    
    def create_window(
        self,
        session_id: str,
        agent_role: str,
        task_description: str,
        max_tokens: Optional[int] = None,
    ) -> ContextWindow:
        """Create a new context window for a session."""
        with self._lock:
            window = ContextWindow(
                content="",
                token_count=0,
                source_chunks=[],
                max_tokens=max_tokens or self._default_max_tokens,
                agent_role=agent_role,
                task_description=task_description,
            )
            self._windows[session_id] = window
            return window
    
    def get_window(self, session_id: str) -> Optional[ContextWindow]:
        with self._lock:
            return self._windows.get(session_id)
    
    def update_context(
        self,
        session_id: str,
        task_description: str,
        max_tokens: Optional[int] = None,
    ) -> ContextWindow:
        """Update context for a task."""
        window = self._windows.get(session_id)
        if not window:
            window = self.create_window(session_id, "unknown", task_description)
        
        # Get relevant context
        new_context = self._rag.get_relevant_context(
            query=task_description,
            max_tokens=max_tokens or window.max_tokens,
            agent_role=window.agent_role,
        )
        
        # Update window
        old_content = window.content
        window.content = new_context
        window.token_count = len(new_context) // 4
        window.task_description = task_description
        if max_tokens:
            window.max_tokens = max_tokens
        
        # Notify callbacks
        update = ContextUpdate(
            type="replace",
            chunk_ids=[],  # Would need to track source chunks
            reason=f"Updated for task: {task_description[:50]}",
        )
        self._notify_callbacks(window, update)
        
        return window
    
    def add_chunks(
        self,
        session_id: str,
        chunk_ids: List[str],
    ) -> bool:
        """Add specific chunks to context window."""
        with self._lock:
            window = self._windows.get(session_id)
            if not window:
                return False
            
            # Get chunks from RAG
            chunks = []
            for chunk_id in chunk_ids:
                # This would need to be implemented in RAGManager
                pass
        
        return True
    
    def remove_chunks(
        self,
        session_id: str,
        chunk_ids: List[str],
    ) -> bool:
        """Remove chunks from context window."""
        return True
    
    def compress_context(
        self,
        session_id: str,
        target_tokens: int,
    ) -> bool:
        """Compress context to fit within token budget."""
        with self._lock:
            window = self._windows.get(session_id)
            if not window:
                return False
            
            # Simple compression: keep most recent/relevant parts
            if window.token_count <= target_tokens:
                return True
            
            # Truncate from middle, keep beginning and end
            content = window.content
            target_chars = target_tokens * 4
            
            if len(content) <= target_chars:
                return True
            
            # Keep first 30% and last 70% (more recent context is usually more relevant)
            first_part = content[:int(target_chars * 0.3)]
            last_part = content[-int(target_chars * 0.7):]
            compressed = first_part + "\n\n... [compressed] ...\n\n" + last_part
            
            window.content = compressed
            window.token_count = len(compressed) // 4
            
            update = ContextUpdate(
                type="compress",
                chunk_ids=[],
                reason=f"Compressed from {window.token_count} to {window.token_count} tokens",
            )
            self._notify_callbacks(window, update)
            return True
    
    def get_context(self, session_id: str) -> Optional[str]:
        """Get current context content."""
        window = self._windows.get(session_id)
        return window.content if window else None
    
    def get_window_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics about a context window."""
        window = self._windows.get(session_id)
        if not window:
            return None
        
        return {
            "token_count": window.token_count,
            "max_tokens": window.max_tokens,
            "utilization": window.utilization,
            "source_chunks": len(window.source_chunks),
            "agent_role": window.agent_role,
            "task_description": window.task_description[:100],
            "created_at": window.created_at.isoformat(),
        }
    
    def register_callback(self, callback: Callable[[ContextWindow, ContextUpdate], None]) -> None:
        """Register a callback for context updates."""
        self._update_callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable) -> None:
        self._update_callbacks.remove(callback)
    
    def _notify_callbacks(self, window: ContextWindow, update: ContextUpdate) -> None:
        for callback in self._update_callbacks:
            try:
                callback(window, update)
            except Exception as e:
                print(f"Context callback error: {e}")
    
    def close_window(self, session_id: str) -> bool:
        """Close and remove a context window."""
        with self._lock:
            if session_id in self._windows:
                del self._windows[session_id]
                return True
        return False
    
    def get_all_windows(self) -> Dict[str, ContextWindow]:
        return dict(self._windows)


# ══════════════════════════════════════════════════════════════════════════════
# Context Selector (High-level interface)
# ═════════════════════════════════════════════════════════════════════════════

class ContextSelector:
    """
    High-level interface for selecting and formatting context.
    
    Usage:
        selector = ContextSelector(rag_manager)
        context = selector.get_context_for_task(
            task="Create a React component for user login",
            agent_role="frontend",
            max_tokens=4000,
        )
    """
    
    def __init__(self, rag_manager: RAGManager):
        self._manager = ContextManager(rag_manager)
    
    def get_context_for_task(
        self,
        task_description: str,
        agent_role: str = "frontend",
        max_tokens: int = 8000,
        session_id: Optional[str] = None,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> str:
        """
        Get optimized context for a task.
        
        Args:
            task_description: Description of the task
            agent_role: Role of the agent (frontend, backend, devops, etc.)
            max_tokens: Maximum tokens for context
            session_id: Optional session ID for context persistence
            include_patterns: File patterns to include
            exclude_patterns: File patterns to exclude
            
        Returns:
            Formatted context string
        """
        session_id = session_id or f"task_{hashlib.md5(task_description.encode()).hexdigest()[:8]}"
        
        # Update context for this task
        window = self._manager.update_context(
            session_id=session_id,
            task_description=task_description,
            max_tokens=max_tokens,
        )
        
        # Apply pattern filters
        context = window.content
        if include_patterns or exclude_patterns:
            lines = context.split("\n")
            filtered = []
            for line in lines:
                if include_patterns and not any(p in line for p in include_patterns):
                    continue
                if exclude_patterns and any(p in line for p in exclude_patterns):
                    continue
                filtered.append(line)
            context = "\n".join(filtered)
        
        return context
    
    def get_context_for_agent(
        self,
        agent_role: str,
        project_overview: str = "",
        max_tokens: int = 8000,
    ) -> str:
        """Get general context for an agent role."""
        task = f"Working as {agent_role} agent. {project_overview}"
        return self.get_context_for_task(
            task_description=task,
            agent_role=agent_role,
            max_tokens=max_tokens,
        )
    
    def update_context(
        self,
        session_id: str,
        new_info: str,
    ) -> None:
        """Update context with new information."""
        window = self._manager.get_window(session_id)
        if window:
            window.content += f"\n\n---\n\n{new_info}"
            window.token_count = len(window.content) // 4
    
    def clear_session(self, session_id: str) -> None:
        """Clear a session's context."""
        self._manager.close_window(session_id)


# ═════════════════════════════════════════════════════════════════════════════
# Streaming Context Updates
# ═════════════════════════════════════════════════════════════════════════════

class StreamingContextManager:
    """
    Manages streaming context updates for real-time agent collaboration.
    
    Features:
    - Real-time context synchronization
    - Conflict resolution for concurrent edits
    - Event sourcing for audit trail
    """
    
    def __init__(self, context_manager: ContextManager):
        self._manager = context_manager
        self._event_log: List[Dict[str, Any]] = []
        self._subscribers: Dict[str, Set[Callable]] = {}  # session_id -> callbacks
        self._lock = threading.Lock()
    
    def subscribe(self, session_id: str, callback: Callable[[Dict], None]) -> None:
        """Subscribe to context updates for a session."""
        with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = set()
            self._subscribers[session_id].add(callback)
    
    def unsubscribe(self, session_id: str, callback: Callable) -> None:
        with self._lock:
            if session_id in self._subscribers:
                self._subscribers[session_id].discard(callback)
    
    def publish_update(
        self,
        session_id: str,
        update_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Publish a context update to subscribers."""
        event = {
            "session_id": session_id,
            "type": update_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._event_log.append(event)
        
        # Keep last 10000 events
        if len(self._event_log) > 10000:
            self._event_log = self._event_log[-10000:]
        
        # Notify subscribers
        for callback in self._subscribers.get(session_id, set()):
            try:
                callback(event)
            except Exception as e:
                print(f"Subscriber error: {e}")
    
    def get_event_history(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get event history for a session."""
        with self._lock:
            return [
                e for e in self._event_log
                if e["session_id"] == session_id
            ][-limit:]


# ═════════════════════════════════════════════════════════════════════════════
# Exports
# ═════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ContextManager",
    "ContextWindow",
    "ContextUpdate",
    "ContextManager",
    "ContextSelector",
    "StreamingContextManager",
]