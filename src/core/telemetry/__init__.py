"""
Telemetry Package — Crash reporting and usage analytics.

Features:
- Crash reporting with stack traces
- Usage analytics (opt-in)
- Performance metrics
- Error aggregation
- Privacy-respecting (no PII)
"""

from .telemetry import (
    TelemetryManager,
    TelemetryEvent,
    CrashReport,
    create_telemetry_manager,
    get_telemetry_manager,
)

__all__ = [
    "TelemetryManager",
    "TelemetryEvent",
    "CrashReport",
    "create_telemetry_manager",
    "get_telemetry_manager",
]