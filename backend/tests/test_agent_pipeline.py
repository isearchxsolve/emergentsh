import pytest

from backend.agent_pipeline import (
    AgentPipeline,
    BackendAgent,
    PipelineContext,
    PipelineStatus,
    parse_design_tokens,
    unwrap_generated_code,
)


class FencedPipelineClient:
    """Deterministic provider stand-in that emits common fenced variants."""

    async def chat_stream(self, messages, **_kwargs):
        system = messages[0]["content"].lower()
        if "software architect" in system:
            yield "# Plan\n\nBuild FlowForge."
        elif "ui/ux designer" in system:
            yield '```json\n{"visual": {"colorPalette": {"primary": "#76B900"}, "fonts": {"body": "Inter"}}}\n```'
        elif "frontend engineer" in system:
            yield "```tsx\nimport React from 'react';\nexport default function App(){ return <main className='transition-colors hover:opacity-90 focus:ring-2' style={{color:'#76B900'}}><h1 className='animate-pulse'>FlowForge</h1><p className='transition-opacity'>Ready</p></main>; }\n```"
        elif "fastapi backend engineer" in system:
            yield "```python\nfrom fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'ok': True}\n```"
        elif "qa engineer" in system:
            yield "```python\ndef test_health():\n    assert True\n```"
        elif "preview engineer" in system:
            yield "<!doctype html><html><head><style>body{color:#fff;background:#07110d}</style></head><body><button onclick=\"this.textContent='Ready'\">Run</button><script>document.body.dataset.ready='true'</script></body></html>"
        else:
            yield "```yaml\nservices: {}\n```"


@pytest.mark.asyncio
async def test_pipeline_completes_with_common_model_presentation_variants() -> None:
    ctx = await AgentPipeline(FencedPipelineClient()).run("Build FlowForge")

    assert ctx.status == PipelineStatus.COMPLETE
    assert ctx.artifacts["design_tokens.json"].startswith("{")
    assert ctx.artifacts["frontend/App.tsx"].startswith("import React")
    assert ctx.artifacts["backend/main.py"].startswith("from fastapi")
    assert ctx.artifacts["tests/test_backend.py"].startswith("def test_health")


class RepairingBackendClient:
    def __init__(self) -> None:
        self.calls = 0

    async def chat_stream(self, messages, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            yield "def broken(:\n    pass"
        else:
            yield "from fastapi import FastAPI\napp = FastAPI()\n"


@pytest.mark.asyncio
async def test_backend_retry_receives_failed_attempt_and_self_repairs() -> None:
    client = RepairingBackendClient()
    pipeline = AgentPipeline(client)
    context = PipelineContext(user_prompt="Build an app")
    context.set_artifact("PLAN.md", "# Plan")

    repaired = await pipeline._run_agent_with_retry(BackendAgent(client), context)

    assert repaired.artifacts["backend/main.py"].startswith("from fastapi")
    assert "_backend_last_attempt.py" not in repaired.artifacts
    assert client.calls == 2


@pytest.mark.parametrize(
    ("raw", "expected_color"),
    [
        ('{"colors": {"primary": "#112233"}, "typography": {"body": "Inter"}}', "#112233"),
        (
            '```json\n{"designTokens": {"colorPalette": {"primary": "#445566"}, "fonts": {"body": "Inter"}}}\n```',
            "#445566",
        ),
        (
            'Here is the requested spec: {"theme": {"palette": {"primary": "#778899"}, "textStyles": {"body": "Inter"}}}',
            "#778899",
        ),
    ],
)
def test_parse_design_tokens_normalizes_common_model_variants(raw: str, expected_color: str) -> None:
    parsed = parse_design_tokens(raw)

    assert parsed["colors"]["primary"] == expected_color
    assert parsed["typography"]["body"] == "Inter"


def test_parse_design_tokens_reports_missing_canonical_sections() -> None:
    with pytest.raises(ValueError, match="Missing required token categories typography"):
        parse_design_tokens('{"colorPalette": {"primary": "#112233"}}')


def test_parse_design_tokens_descends_into_recognizable_custom_section() -> None:
    parsed = parse_design_tokens(
        '{"visualLanguage": {"color_palette": {"primary": "#ABCDEF"}, "font_styles": {"body": "Inter"}}}'
    )

    assert parsed["colors"]["primary"] == "#ABCDEF"
    assert parsed["typography"]["body"] == "Inter"


def test_unwrap_generated_code_removes_language_fence_only() -> None:
    assert unwrap_generated_code("```python\nprint('ok')\n```") == "print('ok')"
    assert unwrap_generated_code("Here is the module:\n```python\nprint('ok')\n```") == "print('ok')"
    assert unwrap_generated_code("print('ok')") == "print('ok')"
