"""Perform a non-mutating OmniRoute inference health probe.

The probe treats a route as live only if a small real completion returns
non-empty content. It never prints credentials or response bodies.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.nim_client import AsyncOmniRouteClient


async def main() -> int:
    if not os.getenv("OMNIROUTE_API_KEY"):
        print(json.dumps({"ready": False, "live": False, "error": "OMNIROUTE_API_KEY is not set"}))
        return 2
    client = AsyncOmniRouteClient(timeout=float(os.getenv("OMNIROUTE_PROBE_TIMEOUT", "15")))
    try:
        result = await client.health_check()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["live"] else 1
    finally:
        await client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
