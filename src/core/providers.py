"""Canonical consumer provider pool for the desktop agent.

The desktop and FastAPI surfaces must share one execution boundary.  This
module keeps the existing rate-limit/failover interface used by the UI, but it
creates exactly one OpenAI-compatible client for the task-owned session-pool
shim.  Provider credentials, model selection, and upstream rotation stay in
OmniRoute; profile keys are display/configuration metadata only.
"""

import os
import time
from typing import List, Optional

from openai import OpenAI

from .rate_limiter import TokenBucket

CANONICAL_CONSUMER_BASE_URL = "http://127.0.0.1:8190/v1"
CANONICAL_CONSUMER_MODEL = "session-pool/auto"


def configured_consumer_base_url() -> str:
    """Return the sole desktop inference endpoint, rejecting configuration drift."""
    configured = os.getenv("OMNIROUTE_BASE_URL", CANONICAL_CONSUMER_BASE_URL).strip().rstrip("/")
    if configured != CANONICAL_CONSUMER_BASE_URL:
        raise ValueError(
            "EmergentSH desktop must use the canonical consumer endpoint "
            f"{CANONICAL_CONSUMER_BASE_URL}; received {configured!r}"
        )
    return CANONICAL_CONSUMER_BASE_URL


class Provider:
    """Wraps a single OpenAI-compatible endpoint with its own rate limiter."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model_id: str,
        rpm: float,
    ):
        selected_base_url = base_url.strip().rstrip("/")
        if selected_base_url != CANONICAL_CONSUMER_BASE_URL:
            raise ValueError(
                "Desktop providers must use the canonical consumer endpoint "
                f"{CANONICAL_CONSUMER_BASE_URL}; received {selected_base_url!r}"
            )
        if model_id != CANONICAL_CONSUMER_MODEL:
            raise ValueError(
                "Desktop providers must use the canonical consumer model "
                f"{CANONICAL_CONSUMER_MODEL}; received {model_id!r}"
            )
        self.name: str = name
        self.model_id: str = model_id
        self.bucket: TokenBucket = TokenBucket(rpm=rpm, min_gap=1.0)
        self.client: OpenAI = OpenAI(
            base_url=selected_base_url, api_key=api_key, timeout=300
        )
        self.cooldown_until: float = 0.0

    def is_available(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def record_success(self) -> None:
        self.bucket.commit()

    def record_rejection(self) -> None:
        self.cooldown_until = time.monotonic() + 60.0


class ProviderPool:
    """Round-robin pool with automatic failover."""

    def __init__(self, providers: List[Provider]):
        self.providers: List[Provider] = providers
        self.idx: int = 0

    def current(self) -> Provider:
        return self.providers[self.idx]

    def rotate(self) -> None:
        self.idx = (self.idx + 1) % len(self.providers)

    def next_available(self) -> Optional[Provider]:
        for _ in range(len(self.providers)):
            if self.current().is_available():
                return self.current()
            self.rotate()
        return None

    def wait_time(self) -> float:
        waits = [
            max(0.0, p.cooldown_until - time.monotonic())
            for p in self.providers
        ]
        return min(waits) if waits else 5.0


def build_provider_pool(profile: dict) -> ProviderPool:
    """Construct a one-route pool backed by the canonical consumer gateway.

    ``profile`` is retained in the API because the desktop UI persists role
    profiles and RPM preferences.  Its historical provider key/model fields
    are intentionally ignored: forwarding either would bypass OmniRoute's
    tenant/session routing and can create the HTTP failures this boundary is
    designed to prevent.
    """
    base_url = configured_consumer_base_url()
    api_key = os.getenv("OMNIROUTE_API_KEY", "").strip()
    return ProviderPool([
        Provider(
            "OmniRoute",
            base_url,
            api_key,
            CANONICAL_CONSUMER_MODEL,
            float(profile.get("rpm", 20.0)),
        )
    ])
