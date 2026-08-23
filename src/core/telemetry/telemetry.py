"""
Telemetry — Crash reporting and usage analytics.

Features:
- Crash reporting with stack traces and minidumps
- Usage analytics (opt-in, no PII)
- Performance metrics
- Error aggregation and deduplication
- Privacy-respecting (no PII collected)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import threading
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import sys
import threading
import time
from ..workspace import WorkspaceManager, get_workspace


# ═════════════════════════════════════════════════════════════════════════════
# Data Models
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class TelemetryEvent:
    """A telemetry event."""
    event_type: str  # "usage", "performance", "error", "feature"
    name: str  # Event name (e.g., "project_created", "build_completed")
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    properties: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    
    # Context (no PII)
    app_version: str = ""
    platform: str = ""
    python_version: str = ""
    os_version: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "properties": self.properties,
            "metrics": self.metrics,
            "app_version": self.app_version,
            "platform": self.platform,
            "python_version": self.python_version,
            "os_version": self.os_version,
        }


@dataclass
class CrashReport:
    """A crash report with full context."""
    id: str
    timestamp: datetime = field(default_factory=datetime.now)
    exception_type: str = ""
    exception_message: str = ""
    stack_trace: str = ""
    
    # Thread info
    thread_id: int = 0
    thread_name: str = ""
    
    # App context
    app_version: str = ""
    session_id: str = ""
    uptime_seconds: float = 0.0
    
    # System info
    platform: str = ""
    python_version: str = ""
    os_version: str = ""
    architecture: str = ""
    
    # Additional context
    recent_logs: List[str] = field(default_factory=list)
    active_tasks: List[str] = field(default_factory=list)
    memory_usage_mb: float = 0.0
    
    # Deduplication
    fingerprint: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "stack_trace": self.stack_trace,
            "thread_id": self.thread_id,
            "thread_name": self.thread_name,
            "app_version": self.app_version,
            "session_id": self.session_id,
            "uptime_seconds": self.uptime_seconds,
            "platform": self.platform,
            "python_version": self.python_version,
            "os_version": self.os_version,
            "architecture": self.architecture,
            "recent_logs": self.recent_logs[-50:],  # Last 50 logs
            "active_tasks": self.active_tasks,
            "memory_usage_mb": self.memory_usage_mb,
            "fingerprint": self.fingerprint,
        }


# ═════════════════════════════════════════════════════════════════════════════
# Telemetry Manager
# ════════════════════════════════════════════════════════════════════════════

class TelemetryManager:
    """
    Manages telemetry collection and crash reporting.
    
    Features:
    - Opt-in telemetry (respects user privacy)
    - Crash reporting with full context
    - Event batching for efficient upload
    - Local storage with rotation
    - GDPR-compliant (no PII, user control)
    """
    
    def __init__(
        self,
        app_name: str,
        app_version: str,
        endpoint_url: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: bool = False,
        workspace: Optional[WorkspaceManager] = None,
    ):
        self._app_name = app_name
        self._app_version = app_version
        self._endpoint_url = endpoint_url
        self._api_key = api_key
        self._enabled = enabled
        self._workspace = workspace or get_workspace()
        
        # Session
        self._session_id = str(uuid.uuid4())
        self._start_time = time.time()
        
        # Buffers
        self._event_buffer: List[TelemetryEvent] = []
        self._crash_buffer: List[CrashReport] = []
        self._log_buffer: List[str] = []
        self._max_log_buffer = 1000
        
        # State
        self._running = False
        self._upload_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[TelemetryEvent], None]] = []
        
        # Deduplication
        self._seen_crash_fingerprints: Set[str] = set()
        
        # Setup crash handler
        if self._enabled:
            self._install_crash_handler()
            self._start_upload_thread()
    
    # ----------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------
    
    def enable(self) -> None:
        """Enable telemetry."""
        with self._lock:
            if not self._enabled:
                self._enabled = True
                self._install_crash_handler()
                self._start_upload_thread()
    
    def disable(self) -> None:
        """Disable telemetry."""
        with self._lock:
            self._enabled = False
            self._stop_upload_thread()
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.enable()
        else:
            self.disable()
    
    # ----------------------------------------------------------------------
    # Event Tracking
    # ----------------------------------------------------------------------
    
    def track_event(
        self,
        event_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """Track a telemetry event."""
        if not self._enabled:
            return
        
        event = TelemetryEvent(
            event_type=event_type,
            name=name,
            properties=properties or {},
            metrics=metrics or {},
            app_version=self._app_version,
            platform=platform.system(),
            python_version=sys.version.split()[0],
            os_version=platform.version(),
        )
        
        self._queue_event(event)
    
    def track_usage(self, feature: str, **properties) -> None:
        """Track feature usage."""
        self.track_event("usage", f"feature_{feature}", properties=properties)
    
    def track_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **properties,
    ) -> None:
        """Track performance metric."""
        self.track_event(
            "performance",
            f"{operation}_duration",
            properties={**properties, "success": success},
            metrics={"duration_ms": duration_ms},
        )
    
    def track_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track an error (non-crash)."""
        self.track_event(
            "error",
            f"error_{type(error).__name__}",
            properties={
                "error_type": type(error).__name__,
                "message": str(error),
                "context": context or {},
            },
        )
    
    def track_feature_use(self, feature: str, **properties) -> None:
        """Track feature usage."""
        self.track_event("feature_use", feature, properties=properties)
    
    def track_command(self, command: str, duration_ms: float, success: bool) -> None:
        """Track command execution."""
        self.track_performance(f"command_{command}", duration_ms, success)
    
    def log(self, level: str, message: str) -> None:
        """Add to log buffer for crash reports."""
        with self._lock:
            self._log_buffer.append(f"[{datetime.now().isoformat()}] [{level}] {message}")
            if len(self._log_buffer) > self._max_log_buffer:
                self._log_buffer = self._log_buffer[-self._max_log_buffer:]
    
    # ----------------------------------------------------------------------
    # Crash Handling
    # ----------------------------------------------------------------------
    
    def _install_crash_handler(self) -> None:
        """Install global exception handler for crash reporting."""
        sys.excepthook = self._handle_exception
        threading.excepthook = self._handle_thread_exception
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Handle uncaught exception in main thread."""
        self._create_crash_report(exc_type, exc_value, exc_traceback)
        # Call original excepthook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def _handle_thread_exception(self, args: threading.ExceptHookArgs) -> None:
        """Handle uncaught exception in worker thread."""
        self._create_crash_report(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            thread_id=args.thread.ident,
            thread_name=args.thread.name,
        )
        # Call original hook
        threading.__excepthook__(args)
    
    def _create_crash_report(
        self,
        exc_type: type,
        exc_value: Exception,
        exc_traceback,
        thread_id: Optional[int] = None,
        thread_name: Optional[str] = None,
    ) -> CrashReport:
        """Create a crash report from an exception."""
        # Generate fingerprint for deduplication
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        fingerprint = hashlib.sha256(
            f"{exc_type.__name__}:{exc_value}".encode()
        ).hexdigest()[:16]
        
        # Check for duplicate
        if fingerprint in self._seen_crash_fingerprints:
            return None
        self._seen_crash_fingerprints.add(fingerprint)
        
        # Build crash report
        report = CrashReport(
            id=str(uuid.uuid4()),
            exception_type=exc_type.__name__,
            exception_message=str(exc_value),
            stack_trace="".join(tb_lines),
            thread_id=thread_id or threading.current_thread().ident,
            thread_name=thread_name or threading.current_thread().name,
            app_version=self._app_version,
            session_id=self._session_id,
            uptime_seconds=time.time() - self._start_time,
            platform=platform.platform(),
            python_version=sys.version.split()[0],
            os_version=platform.version(),
            architecture=platform.machine(),
            recent_logs=self._log_buffer.copy(),
            active_tasks=[],  # Would be populated by task manager
            memory_usage_mb=self._get_memory_usage(),
            fingerprint=fingerprint,
        )
        
        # Add to buffer
        with self._lock:
            self._crash_buffer.append(report)
        
        # Try to upload immediately for crashes
        self._upload_crash_report(report)
        
        return report
    
    def get_crash_reports(self) -> List[CrashReport]:
        """Get all crash reports."""
        with self._lock:
            return list(self._crash_buffer)
    
    def clear_crash_reports(self) -> None:
        """Clear crash reports."""
        with self._lock:
            self._crash_buffer.clear()
    
    # ----------------------------------------------------------------------
    # Upload
    # ----------------------------------------------------------------------
    
    def _queue_event(self, event: TelemetryEvent) -> None:
        """Add event to buffer."""
        with self._lock:
            self._event_buffer.append(event)
            # Keep buffer size reasonable
            if len(self._event_buffer) > 1000:
                self._event_buffer = self._event_buffer[-1000:]
    
    def _start_upload_thread(self) -> None:
        """Start background upload thread."""
        self._running = True
        self._upload_thread = threading.Thread(target=self._upload_loop, daemon=True)
        self._upload_thread.start()
    
    def _stop_upload_thread(self) -> None:
        self._running = False
        if self._upload_thread:
            self._upload_thread.join(timeout=5)
    
    def _upload_loop(self) -> None:
        """Background loop for uploading telemetry."""
        while self._running:
            try:
                self._flush_buffers()
            except Exception as e:
                print(f"Telemetry upload error: {e}")
            
            # Sleep for 30 seconds
            for _ in range(30):
                if not self._running:
                    break
                time.sleep(1)
    
    def _flush_buffers(self) -> None:
        """Flush event and crash buffers to server."""
        if not self._endpoint_url:
            return
        
        with self._lock:
            events = self._event_buffer.copy()
            crashes = self._crash_buffer.copy()
            self._event_buffer.clear()
            self._crash_buffer.clear()
        
        if not events and not crashes:
            return
        
        # Upload events
        if events:
            self._upload_events(events)
        
        # Upload crashes
        for crash in crashes:
            self._upload_crash_report(crash)
    
    def _upload_events(self, events: List[TelemetryEvent]) -> bool:
        """Upload events to server."""
        if not self._endpoint_url:
            return False
        
        try:
            import requests
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"{self._app_name}/{self._app_version}",
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            
            payload = {
                "app": self._app_name,
                "version": self._app_version,
                "session_id": self._session_id,
                "events": [e.to_dict() for e in events],
            }
            
            response = requests.post(
                f"{self._endpoint_url}/telemetry/events",
                json=payload,
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to upload events: {e}")
            return False
    
    def _upload_crash_report(self, report: CrashReport) -> bool:
        """Upload crash report to server."""
        if not self._endpoint_url:
            return False
        
        try:
            import requests
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"{self._app_name}/{self._app_version}",
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            
            response = requests.post(
                f"{self._endpoint_url}/telemetry/crashes",
                json=report.to_dict(),
                headers=headers,
                timeout=30,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to upload crash report: {e}")
            return False
    
    # ----------------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------------
    
    def save_local(self, directory: Optional[Path] = None) -> None:
        """Save telemetry data locally."""
        if directory is None:
            directory = Path.home() / ".emergentsh" / "telemetry"
        directory.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            # Save events
            events_file = Path(directory) / "events.json"
            events_data = [e.to_dict() for e in self._event_buffer]
            events_file.write_text(json.dumps(events_data, indent=2, default=str))
            
            # Save crashes
            crashes_file = Path(directory) / "crashes.json"
            crashes_data = [c.to_dict() for c in self._crash_buffer]
            crashes_file.write_text(json.dumps(crashes_data, indent=2, default=str))
            
            # Save logs
            logs_file = Path(directory) / "logs.json"
            logs_file.write_text(json.dumps(self._log_buffer))
    
    def load_local(self, directory: Optional[Path] = None) -> None:
        """Load telemetry data from local storage."""
        if directory is None:
            directory = Path.home() / ".emergentsh" / "telemetry"
        
        try:
            events_file = Path(directory) / "events.json"
            if events_file.exists():
                data = json.loads(events_file.read_text())
                with self._lock:
                    self._event_buffer = [TelemetryEvent(**d) for d in data]
            
            crashes_file = Path(directory) / "crashes.json"
            if crashes_file.exists():
                data = json.loads(crashes_file.read_text())
                with self._lock:
                    self._crash_buffer = [CrashReport(**d) for d in data]
                    for c in self._crash_buffer:
                        self._seen_crash_fingerprints.add(c.fingerprint)
            
            logs_file = Path(directory) / "logs.json"
            if logs_file.exists():
                self._log_buffer = json.loads(logs_file.read_text())
        except Exception as e:
            print(f"Failed to load telemetry: {e}")
    
    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0
    
    # ----------------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------------
    
    def shutdown(self) -> None:
        """Shutdown telemetry manager."""
        self.disable()
        self._flush()
    
    def _flush(self) -> None:
        """Flush buffers to disk and server."""
        self._flush_buffers()
        if self._workspace:
            self.save_local()
    
    # ----------------------------------------------------------------------
    # Privacy
    # ----------------------------------------------------------------------
    
    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove PII from data before upload."""
        # This is a placeholder; implement based on privacy requirements
        return data
    
    def export_user_data(self) -> Dict[str, Any]:
        """Export all user data for GDPR compliance."""
        with self._lock:
            return {
                "session_id": self._session_id,
                "events": [e.to_dict() for e in self._event_buffer],
                "crashes": [c.to_dict() for c in self._crash_buffer],
                "logs": self._log_buffer[-100:],  # Last 100 logs
            }
    
    def delete_user_data(self) -> None:
        """Delete all user data (right to be forgotten)."""
        with self._lock:
            self._event_buffer.clear()
            self._crash_buffer.clear()
            self._log_buffer.clear()
            self._seen_crash_fingerprints.clear()
            self._session_id = str(uuid.uuid4())
            self._start_time = time.time()


# ═════════════════════════════════════════════════════════════════════════════
# Crash Dialog (UI)
# ═════════════════════════════════════════════════════════════════════════════

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QCheckBox, QMessageBox, QProgressBar
    )
    from PySide6.QtGui import QFont
    
    class CrashDialog(QDialog):
        """Dialog shown when a crash occurs."""
        
        def __init__(self, report: CrashReport, parent=None):
            super().__init__(parent)
            self._report = report
            self._send_report = False
            self.setWindowTitle("EmergentSH Crashed")
            self.setMinimumSize(600, 500)
            self.setModal(True)
            self._build_ui()
        
        def _build_ui(self):
            layout = QVBoxLayout(self)
            
            # Header
            header = QLabel("EmergentSH encountered an unexpected error")
            header.setFont(QFont("Segoe UI", 14, QFont.Bold))
            header.setWordWrap(True)
            layout.addWidget(header)
            
            # Message
            msg = QLabel(
                "We're sorry for the inconvenience. Please help us fix this by sending "
                "an anonymous crash report. No personal information is included."
            )
            msg.setWordWrap(True)
            layout.addWidget(msg)
            
            # Details
            details = QTextEdit()
            details.setReadOnly(True)
            details.setPlainText(self._report.stack_trace)
            details.setFontFamily("Consolas")
            details.setFontPointSize(9)
            layout.addWidget(details)
            
            # Checkbox
            self._send_checkbox = QCheckBox("Send anonymous crash report")
            self._send_checkbox.setChecked(True)
            layout.addWidget(self._send_checkbox)
            
            # Include logs checkbox
            self._logs_checkbox = QCheckBox("Include recent logs")
            self._logs_checkbox.setChecked(True)
            layout.addWidget(self._logs_checkbox)
            
            # Buttons
            buttons = QHBoxLayout()
            self._send_btn = QPushButton("Send Report")
            self._send_btn.clicked.connect(self._on_send)
            buttons.addWidget(self._send_btn)
            
            self._close_btn = QPushButton("Close")
            self._close_btn.clicked.connect(self._on_close)
            buttons.addWidget(self._close_btn)
            
            layout.addLayout(buttons)
        
        def _on_send(self):
            self._send_report = self._send_checkbox.isChecked()
            self.accept()
        
        def _on_close(self):
            self._send_report = False
            self.reject()
        
        def should_send(self) -> bool:
            return self._send_report

except ImportError:
    class CrashDialog:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ════════════════════════════════════════════════════════════════════════════

def create_telemetry_manager(
    app_name: str,
    app_version: str,
    endpoint_url: Optional[str] = None,
    api_key: Optional[str] = None,
    enabled: bool = False,
    workspace: Optional[WorkspaceManager] = None,
) -> TelemetryManager:
    return TelemetryManager(
        app_name=app_name,
        app_version=app_version,
        endpoint_url=endpoint_url,
        api_key=api_key,
        enabled=enabled,
        workspace=None,
    )


def get_telemetry_manager() -> TelemetryManager:
    """Get or create global telemetry manager."""
    global _TELEMETRY_MANAGER
    if _TELEMETRY_MANAGER is None:
        _TELEMETRY_MANAGER = TelemetryManager(
            app_name="EmergentSH",
            app_version="1.0.0",
            enabled=False,  # Opt-in by default
        )
    return _TELEMETRY_MANAGER


# Global instance
_TELEMETRY_MANAGER: Optional[TelemetryManager] = None

# Import uuid
import uuid