"""
ProviderPool — manages multiple inference providers (NVIDIA NIM, OpenRouter)
with automatic cooldown / rotation on rejection.
"""

import os
import time
from typing import List, Optional

from openai import OpenAI

from .rate_limiter import TokenBucket

NIM_BASE = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_FREE_MODELS = [
    ("OR-Nemotron", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("OR-Qwen3", "qwen/qwen3-coder:free"),
]


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
        self.name: str = name
        self.model_id: str = model_id
        self.bucket: TokenBucket = TokenBucket(rpm=rpm, min_gap=1.0)
        self.client: OpenAI = OpenAI(
            base_url=base_url, api_key=api_key, timeout=300
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
    """Construct a ProviderPool from a profile dict."""
    model_entry = profile["models"][profile["default_model"]]
    providers: List[Provider] = [
        Provider(
            "NVIDIA NIM",
            NIM_BASE,
            profile["key"],
            model_entry["id"],
            profile.get("rpm", 20.0),
        )
    ]
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if or_key:
        for name, mid in OPENROUTER_FREE_MODELS:
            providers.append(
                Provider(name, OPENROUTER_BASE, or_key, mid, 18.0)
            )
    return ProviderPool(providers)
