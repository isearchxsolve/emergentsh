"""
IntegrationGenerator — code generation engine for the IntegrationAgent.

Generates glue code that wires frontend ↔ backend: API client modules,
environment configuration, and integration test scaffolds. Materializes file
artifacts from specs; does not call the LLM directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EndpointBinding:
    """A frontend→backend endpoint binding."""
    name: str
    method: str
    path: str
    request_type: str = "any"
    response_type: str = "any"


class IntegrationGenerator:
    """Generates integration glue code (API clients, env config, test scaffolds)."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def generate_api_client(self, bindings: List[EndpointBinding]) -> str:
        """Render a typed API client module from endpoint bindings."""
        lines = ["// Auto-generated API client", ""]
        for b in bindings:
            lines.append(
                f"export async function {b.name}(input: {b.request_type}): Promise<{b.response_type}> {{"
            )
            lines.append(f"  const res = await fetch('{b.path}', {{ method: '{b.method.upper()}' }});")
            lines.append("  return res.json();")
            lines.append("}")
            lines.append("")
        return "\n".join(lines)

    def generate_env_config(self, base_url: str = "http://localhost:8000") -> str:
        return f"NEXT_PUBLIC_API_URL={base_url}\n"

    def generate(self, bindings: List[EndpointBinding], base_url: str = "http://localhost:8000") -> List[str]:
        created: List[str] = []
        client = self.project_root / "lib/apiClient.ts"
        client.parent.mkdir(parents=True, exist_ok=True)
        client.write_text(self.generate_api_client(bindings), encoding="utf-8")
        created.append(str(client))
        env = self.project_root / ".env.local"
        env.write_text(self.generate_env_config(base_url), encoding="utf-8")
        created.append(str(env))
        return created
