"""Compatibility entry point for EmergentSH code-generation runs.

The executable pipeline lives in :mod:`backend.agent_pipeline`.  Keeping this
small adapter preserves the historical module path while routing callers to
the maintained implementation instead of leaving a corrupted generated file
that cannot be imported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from .agent_pipeline import AgentPipeline, PipelineContext


async def generate_project(
    nim_client: Any,
    prompt: str,
    project_dir: Union[str, Path] = "",
) -> PipelineContext:
    """Run the standard generation pipeline for a non-empty project prompt."""
    if not prompt or not prompt.strip():
        raise ValueError("prompt must not be empty")
    return await AgentPipeline(nim_client).run(
        user_prompt=prompt.strip(),
        project_dir=str(project_dir),
    )


__all__ = ["generate_project", "AgentPipeline", "PipelineContext"]
