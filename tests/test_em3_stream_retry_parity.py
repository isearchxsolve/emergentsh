"""EM-3 regression tests: stream_run() retry parity with run().

Guards the audit gap: run() had a 3-retry self-heal loop for validation
failures, but stream_run() -- the path the UI actually uses -- had none, so
a transient designer/frontend validation failure killed the whole stream
after 2 of 7 agents. The retry policy now lives in ONE function
(_run_agent_with_retry) used by both paths, and stream retries resume
in-place so SSE consumers never see duplicated events for a stage that
eventually succeeds.
"""
import pytest
from unittest.mock import AsyncMock

from backend.agent_pipeline import (
    AgentPipeline,
    AgentRole,
    BaseAgent,
    PipelineContext,
    PipelineStatus,
)


class _FlakyAgent(BaseAgent):
    """Fails with ValueError (retryable) for the first N attempts."""

    role = AgentRole.DESIGNER

    def __init__(self, fail_times: int):
        super().__init__(AsyncMock())
        self.fail_times = fail_times
        self.attempts = 0

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise ValueError(f"transient validation failure #{self.attempts}")
        ctx.set_artifact("PLAN.md", "# recovered")
        ctx.status = PipelineStatus.COMPLETE
        return ctx


class _FatalAgent(BaseAgent):
    """Raises a non-ValueError (non-retryable) immediately."""

    role = AgentRole.BACKEND

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        raise RuntimeError("fatal infra failure")


def _pipeline_with(agents) -> AgentPipeline:
    pipeline = AgentPipeline(AsyncMock())
    pipeline._agents = agents
    return pipeline


class TestSharedRetryPolicy:
    @pytest.mark.asyncio
    async def test_run_retries_transient_failure(self):
        agent = _FlakyAgent(fail_times=2)
        pipeline = _pipeline_with([agent])
        ctx = await pipeline.run(user_prompt="x")
        assert ctx.status != PipelineStatus.FAILED
        assert agent.attempts == 3, "run() must retry through transient failures"
        assert "PLAN.md" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_stream_retries_transient_failure_mid_stream(self):
        """The EM-3 acceptance test: transient failure mid-stream completes via retry."""
        agent = _FlakyAgent(fail_times=2)
        pipeline = _pipeline_with([agent])
        events = [e async for e in pipeline.stream_run(user_prompt="x")]
        assert events[-1]["event"] == "pipeline_complete"
        assert events[-1]["data"]["status"] == "complete"
        assert agent.attempts == 3, "stream_run() must have the SAME retry policy as run()"

    @pytest.mark.asyncio
    async def test_stream_does_not_duplicate_events_on_retry(self):
        """Resume-from-stage: one agent_start/agent_done per stage, ever."""
        agent = _FlakyAgent(fail_times=2)
        pipeline = _pipeline_with([agent])
        events = [e async for e in pipeline.stream_run(user_prompt="x")]
        starts = [e for e in events if e["event"] == "agent_start"]
        dones = [e for e in events if e["event"] == "agent_done"]
        assert len(starts) == 1, "retries must not re-emit agent_start"
        assert len(dones) == 1, "retries must not re-emit agent_done"

    @pytest.mark.asyncio
    async def test_exhausted_retries_fail_loudly_in_stream(self):
        agent = _FlakyAgent(fail_times=AgentPipeline.MAX_AGENT_RETRIES)  # never succeeds
        pipeline = _pipeline_with([agent])
        events = [e async for e in pipeline.stream_run(user_prompt="x")]
        errors = [e for e in events if e["event"] == "agent_error"]
        assert len(errors) == 1
        complete = events[-1]
        assert complete["event"] == "pipeline_complete"
        assert complete["data"]["status"] == "failed"
        assert agent.attempts == AgentPipeline.MAX_AGENT_RETRIES

    @pytest.mark.asyncio
    async def test_fatal_error_not_retried_in_either_path(self):
        agent = _FatalAgent(AsyncMock())
        pipeline = _pipeline_with([agent])

        ctx = await pipeline.run(user_prompt="x")
        assert ctx.status == PipelineStatus.FAILED

        events = [e async for e in pipeline.stream_run(user_prompt="x")]
        assert events[-1]["data"]["status"] == "failed"
        assert any(e["event"] == "agent_error" for e in events)

    @pytest.mark.asyncio
    async def test_run_and_stream_share_one_policy_function(self):
        """Both paths must route through _run_agent_with_retry (no drift)."""
        import inspect

        from backend.agent_pipeline import AgentPipeline as AP

        run_src = inspect.getsource(AP.run)
        stream_src = inspect.getsource(AP.stream_run)
        assert "_run_agent_with_retry" in run_src
        assert "_run_agent_with_retry" in stream_src


class TestSevenAgentChain:
    def test_default_chain_is_seven_agents(self):
        pipeline = AgentPipeline(AsyncMock())
        roles = [a.role.value for a in pipeline._agents]
        assert roles == [
            "planner", "designer", "frontend", "backend",
            "integration", "qa", "devops",
        ], f"the generated-project contract is a 7-agent chain, got {roles}"
