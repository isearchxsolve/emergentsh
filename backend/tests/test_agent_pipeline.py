import json
from pathlib import Path
import subprocess
import sys

import pytest

from backend.agent_pipeline import (
    AgentPipeline,
    BackendAgent,
    DesignerAgent,
    FrontendAgent,
    QAAgent,
    PlannerAgent,
    PipelineContext,
    PipelineStatus,
    complete_design_tokens,
    GENERATED_TEST_BOOTSTRAP,
    deterministic_project_smoke_tests,
    validate_preview_html,
    validate_plan_contract,
    validate_design_contract,
    validate_frontend_contract,
    validate_backend_contract,
    validate_fullstack_handoff,
    validate_qa_contract,
    validate_integration_artifacts,
    validate_devops_artifacts,
    evaluate_delivery_quality,
    infer_product_blueprint,
    validate_mobile_contract,
    parse_design_tokens,
    unwrap_generated_code,
)


@pytest.fixture(autouse=True)
def canonical_consumer_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep pipeline tests on the documented consumer boundary."""
    monkeypatch.setenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:8190/v1")
    monkeypatch.delenv("OMNIROUTE_FALLBACK_MODELS", raising=False)
    for name in (
        "OMNIROUTE_PLANNER_ROUTE",
        "OMNIROUTE_BACKEND_ROUTE",
        "OMNIROUTE_DESIGNER_ROUTE",
        "OMNIROUTE_FRONTEND_ROUTE",
        "OMNIROUTE_INTEGRATION_ROUTE",
        "OMNIROUTE_PREVIEW_ROUTE",
        "OMNIROUTE_QA_ROUTE",
        "OMNIROUTE_DEVOPS_ROUTE",
    ):
        monkeypatch.delenv(name, raising=False)
from backend.app.api.pipeline import _deliverable_file


VALID_BACKEND = '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jose import jwt
import os
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
engine = create_engine("sqlite:///./app.db")
SessionLocal = sessionmaker(bind=engine)
SECRET_KEY = os.getenv("SECRET_KEY", "local-development-only")
class Item(BaseModel): name: str
@app.get("/api/v1/health")
def health(): return {"ok": True}
@app.get("/api/v1/items")
def items(): return []
@app.post("/api/v1/items")
def create_item(item: Item): return item
@app.patch("/api/v1/items/{item_id}")
def update_item(item_id: int, item: Item): return item
@app.delete("/api/v1/items/{item_id}")
def delete_item(item_id: int): return {"deleted": item_id}
'''

VALID_FRONTEND = '''import React, {useEffect, useState} from 'react';
const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
export default function App(){const [items,setItems]=useState<any[]>([]);const [loading,setLoading]=useState(true);const [error,setError]=useState('');
useEffect(()=>{fetch(`${API_BASE}/items`).then(r=>r.json()).then(setItems).catch(()=>setError('error')).finally(()=>setLoading(false))},[]);
async function submit(e:React.FormEvent){e.preventDefault();await fetch(`${API_BASE}/items`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'Ready'})});}
return <main className="min-h-screen transition-colors hover:opacity-95 focus:ring-2" style={{color:'#76B900'}}><form data-testid="primary-form" onSubmit={submit} className="p-4"><input aria-label="Name"/><button data-testid="primary-submit">Save</button></form>{loading?'Loading':error||(!items.length?'Empty':items.map(x=><p key={x.name}>{x.name}</p>))}</main>}
'''


class FencedPipelineClient:
    """Deterministic provider stand-in that emits common fenced variants."""

    async def chat_stream(self, messages, **_kwargs):
        system = messages[0]["content"].lower()
        if "software architect" in system:
            yield "# Plan\n\n## Business Vision\nFlowForge is a focused item workflow for operators.\n## Primary User Journeys\nAn operator creates and reviews items.\n## Success Metrics\nA created item is visible on refresh.\n## Out of Scope\nThird-party marketplace integrations.\n## Permissions\nOperator roles own and authorize their items.\n## Features\nPrimary journey.\n## API Endpoints\nGET /api/v1/items\nPOST /api/v1/items\nDELETE /api/v1/items/{id}\n## Database Schema\nItems table.\n## Acceptance Tests\nCRUD smoke test.\n## Local Startup\nRun backend and frontend."
        elif "ui/ux designer" in system:
            yield '```json\n{"visual": {"colorPalette": {"primary": "#76B900"}, "fonts": {"body": "Inter"}}}\n```'
        elif "frontend engineer" in system:
            yield f"```tsx\n{VALID_FRONTEND}\n```"
        elif "fastapi backend engineer" in system:
            yield f"```python\n{VALID_BACKEND}\n```"
        elif "qa engineer" in system:
            yield "```python\nfrom fastapi.testclient import TestClient\nfrom backend.main import app\nclient=TestClient(app)\ndef test_health(): assert client.get('/api/v1/health').status_code == 200\ndef test_create_item(): assert client.post('/api/v1/items', json={'name':'Ready'}).status_code < 400\n```"
        elif "preview engineer" in system:
            yield "<!doctype html><html><head><style>body{color:#fff;background:linear-gradient(#07110d,#111);box-shadow:0 0 20px #000}@media(max-width:600px){body{padding:8px}}</style></head><body><button onclick=\"this.textContent='Ready'\">Run</button><button>Save</button><script>document.body.dataset.ready='true'</script></body></html>"
        else:
            request = messages[-1]["content"].lower()
            if "env.example" in request:
                yield "API_URL=/api/v1\nDATABASE_URL=sqlite:///./app.db\nSECRET_KEY=replace-me"
            elif "github actions" in request:
                yield "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n      - run: pytest\n      - run: npm run build"
            elif "deployment checklist" in request:
                yield "# Deployment\n- Run migration\n- Configure secret\n- Verify health\n- Document rollback"
            elif "docker-compose" in request:
                yield "services:\n  frontend: {build: ./frontend}\n  backend: {build: ./backend}"
            else:
                yield "FROM python:3.12-slim"


@pytest.mark.asyncio
async def test_pipeline_completes_with_common_model_presentation_variants() -> None:
    ctx = await AgentPipeline(FencedPipelineClient()).run("Build FlowForge")

    assert ctx.status == PipelineStatus.COMPLETE
    assert ctx.artifacts["design_tokens.json"].startswith("{")
    assert ctx.artifacts["frontend/App.tsx"].startswith("import React")
    assert ctx.artifacts["backend/main.py"].startswith("from fastapi")
    assert "def test_health" in ctx.artifacts["tests/test_backend.py"]
    assert "TestClient" in ctx.artifacts["tests/test_backend.py"]
    assert json.loads(ctx.artifacts["QUALITY_GATE.json"])["passed"] is True
    assert json.loads(ctx.artifacts["PRODUCT_BLUEPRINT.json"])["category"] == "custom_product"


def test_terse_zoho_prompt_receives_business_suite_scaffold() -> None:
    blueprint = infer_product_blueprint("Build an app similar to Zoho")
    assert blueprint["category"] == "business_suite"
    assert {"organizations", "contacts", "work items"}.issubset(blueprint["capabilities"])


def test_react_native_quality_contract_requires_real_mobile_product_evidence() -> None:
    source = "import {SafeAreaView,TextInput,Dimensions} from 'react-native'; async function load(){return fetch('/api/v1/items')} const loading='loading'; const error='error'; const empty='empty'; const green='#34D399'; export default function App(){return <SafeAreaView accessibilityLabel='App'><TextInput /></SafeAreaView>}"
    assert validate_mobile_contract(source, "react-native", {"colors": {"primary": "#34D399"}}) == []


class RepairingBackendClient:
    def __init__(self) -> None:
        self.calls = 0

    async def chat_stream(self, messages, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            yield "def broken(:\n    pass"
        else:
            yield VALID_BACKEND


class RepairingFrontendClient:
    def __init__(self) -> None:
        self.requests: list[str] = []

    async def chat_stream(self, messages, **_kwargs):
        self.requests.append(messages[-1]["content"])
        if len(self.requests) == 1:
            yield "This is not a React component."
        else:
            yield VALID_FRONTEND


class RecordingRouteClient:
    def __init__(self) -> None:
        self.models: list[str | None] = []

    async def chat_stream(self, messages, **kwargs):
        self.models.append(kwargs.get("model"))
        yield "route selected"


@pytest.mark.asyncio
async def test_agents_select_omniroute_policy_by_stage(monkeypatch) -> None:
    monkeypatch.setenv("INFERENCE_PROVIDER", "omniroute")
    client = RecordingRouteClient()

    await DesignerAgent(client)._call_nim("design this")
    await FrontendAgent(client)._call_nim("build the frontend")
    await BackendAgent(client)._call_nim("build this")

    assert client.models == ["session-pool/auto"] * 3


@pytest.mark.asyncio
async def test_planner_retries_with_the_exact_missing_contract(monkeypatch) -> None:
    class PlannerRepairClient:
        def __init__(self) -> None:
            self.requests: list[str] = []

        async def chat_stream(self, messages, **_kwargs):
            self.requests.append(messages[-1]["content"])
            if len(self.requests) == 1:
                yield "# Overview\n\n## Features\n- Invoice management\n"
            else:
                yield (
                    "# Overview\n\n## Tech Stack\nFastAPI and React\n\n## Features\nInvoices\n"
                    "## API Endpoints\nGET /api/v1/invoices\nPOST /api/v1/invoices\nPATCH /api/v1/invoices/{id}\n"
                        "## Database Schema\ninvoices table\n\n## Acceptance Tests\nCreate invoice journey\n"
                        "## Local Startup\nRun backend and frontend\n\n## Milestones\nBuild and verify\n"
                        "## Business Vision\nInvoice workflow and business outcome for finance teams.\n"
                        "## Primary User Journeys\nRole-based actors create and approve invoices with authorization.\n"
                        "## Success Metrics\nReduce invoice processing time.\n"
                        "## Out of Scope\nPayroll is a non-goal."
                    )

    # Even a hermetic repair client should exercise the application transport
    # policy; direct NIM is retired rather than a valid test execution mode.
    monkeypatch.setenv("INFERENCE_PROVIDER", "omniroute")
    client = PlannerRepairClient()
    result = await AgentPipeline(client)._run_agent_with_retry(
        PlannerAgent(client), PipelineContext(user_prompt="Build an invoice app")
    )

    assert result.status != PipelineStatus.FAILED
    assert len(client.requests) == 2
    assert "PREVIOUS VALIDATION FAILURE" in client.requests[1]
    assert "missing API endpoints" in client.requests[1]


@pytest.mark.asyncio
async def test_transient_omniroute_failure_retries_after_circuit_backoff(monkeypatch) -> None:
    class FlakyInferenceAgent(PlannerAgent):
        def __init__(self) -> None:
            super().__init__(RecordingRouteClient())
            self.attempts = 0

        async def run(self, ctx):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("All configured OmniRoute routes failed: auto/best-reasoning (HTTP 403).")
            return ctx

    monkeypatch.setenv("INFERENCE_RETRY_BACKOFF_SECONDS", "0")
    agent = FlakyInferenceAgent()
    result = await AgentPipeline(agent.nim)._run_agent_with_retry(agent, PipelineContext())

    assert result.status != PipelineStatus.FAILED
    assert agent.attempts == 2


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


@pytest.mark.asyncio
async def test_frontend_retry_receives_the_invalid_attempt_and_self_repairs() -> None:
    client = RepairingFrontendClient()
    context = PipelineContext(user_prompt="Build an app")
    context.set_artifact("PLAN.md", "# Plan\n\n## Features\nItems")
    context.set_artifact("design_tokens.json", json.dumps({"colors": {"primary": "#76B900"}}))

    repaired = await AgentPipeline(client)._run_agent_with_retry(FrontendAgent(client), context)

    assert repaired.artifacts["frontend/App.tsx"].startswith("import React")
    assert "_frontend_last_attempt.tsx" not in repaired.artifacts
    assert len(client.requests) == 2
    assert "DELIVERY ENVELOPE (non-negotiable)" in client.requests[0]
    assert "Do not split it into parts" in client.requests[0]
    assert "PREVIOUS INVALID FRONTEND OUTPUT" in client.requests[1]
    assert "This is not a React component." in client.requests[1]


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


def test_complete_design_tokens_preserves_partial_palette_and_fills_contract() -> None:
    completed = complete_design_tokens('{"colorPalette": {"primary": "#ABCDEF"}}')

    assert completed["colors"]["primary"] == "#ABCDEF"
    assert completed["typography"]["body"]
    assert completed["components"]
    assert completed["responsive"]


def test_complete_design_tokens_preserves_partial_nested_palette() -> None:
    completed = complete_design_tokens('{"visualLanguage": {"palette": {"primary": "#123456"}}}')
    assert completed["colors"]["primary"] == "#123456"


class IncompleteDesignerClient:
    def __init__(self) -> None:
        self.calls = 0

    async def chat_stream(self, messages, **_kwargs):
        self.calls += 1
        yield '{"colorPalette": {"primary": "#ABCDEF"}}'


@pytest.mark.asyncio
async def test_designer_exhaustion_uses_deterministic_defaults_and_continues() -> None:
    client = IncompleteDesignerClient()
    pipeline = AgentPipeline(client)
    context = PipelineContext(user_prompt="Build a field service app")
    context.set_artifact("PLAN.md", "# Plan")

    recovered = await pipeline._run_agent_with_retry(DesignerAgent(client), context)

    assert recovered.status != PipelineStatus.FAILED
    assert client.calls == pipeline.MAX_AGENT_RETRIES
    tokens = json.loads(recovered.artifacts["design_tokens.json"])
    assert tokens["colors"]["primary"] == "#ABCDEF"
    assert tokens["typography"]["body"]
    assert "DESIGN_RECOVERY.json" in recovered.artifacts
    assert "_designer_last_attempt.json" not in recovered.artifacts


@pytest.mark.asyncio
async def test_stream_reports_repairs_before_deterministic_recovery() -> None:
    client = IncompleteDesignerClient()
    pipeline = AgentPipeline(client)
    pipeline._agents = [DesignerAgent(client)]

    events = [event async for event in pipeline.stream_run("Build a field service app")]
    retries = [event for event in events if event["event"] == "agent_retry"]

    assert [event["data"]["recovered"] for event in retries] == [False, False, True]
    assert events[-1]["data"]["status"] != "failed"


class InvalidQATestClient:
    async def chat_stream(self, messages, **_kwargs):
        yield "def broken():\n    value = 'unterminated"


@pytest.mark.asyncio
async def test_qa_syntax_failure_cannot_downgrade_to_superficial_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_ISOLATION", "host")
    context = PipelineContext(user_prompt="Build an app", project_dir=str(tmp_path))
    context.set_artifact("backend/main.py", VALID_BACKEND)
    context.set_artifact("frontend/App.tsx", VALID_FRONTEND)
    context.set_artifact("index.html", "<!doctype html><style>body{color:white}</style><button>Go</button><script>document.body.dataset.ready='1'</script>")
    client = InvalidQATestClient()

    result = await AgentPipeline(client)._run_agent_with_retry(QAAgent(client), context)

    assert result.status == PipelineStatus.FAILED
    assert "QA_RECOVERY.json" not in result.artifacts
    assert any("QA validation failed" in item for item in result.errors)


def test_unwrap_generated_code_removes_language_fence_only() -> None:
    assert unwrap_generated_code("```python\nprint('ok')\n```") == "print('ok')"
    assert unwrap_generated_code("Here is the module:\n```python\nprint('ok')\n```") == "print('ok')"
    assert unwrap_generated_code("print('ok')") == "print('ok')"


def test_deterministic_project_smoke_fallback_is_valid_python() -> None:
    source = deterministic_project_smoke_tests()
    compile(source, "tests/test_backend.py", "exec")
    assert "test_backend_is_valid_fastapi_module" in source
    assert "test_frontend_has_runnable_component_contract" in source
    assert "test_preview_is_offline_and_interactive" in source


def test_artifact_inventory_excludes_python_caches_and_normalizes_at_callsite(tmp_path) -> None:
    source = tmp_path / "frontend" / "App.tsx"
    source.parent.mkdir()
    source.write_text("export default function App(){}", encoding="utf-8")
    cache = tmp_path / "tests" / "__pycache__" / "test_app.pyc"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"cache")

    assert _deliverable_file(tmp_path, source)
    assert not _deliverable_file(tmp_path, cache)
    assert source.relative_to(tmp_path).as_posix() == "frontend/App.tsx"


def test_preview_validator_rejects_runtime_syntax_and_placeholder_interactions() -> None:
    broken = """<!doctype html><style>@media(max-width:600px){body{box-shadow:0 0 2px #000}}</style>
    <button>One</button><button>Two</button><script>const x = `${var(--space)}`; alert('would open here')</script>"""
    violations = validate_preview_html(broken)
    assert any("CSS var()" in item or "syntax is invalid" in item for item in violations)
    assert any("placeholder interaction" in item for item in violations)


def test_preview_validator_accepts_deterministic_polished_contract() -> None:
    polished = """<!doctype html><style>@media(max-width:600px){body{box-shadow:0 0 2px #000;background:linear-gradient(#000,#111)}}</style>
    <button id='a'>One</button><button>Two</button><script>document.getElementById('a').onclick=()=>true</script>"""
    assert validate_preview_html(polished) == []


def test_planner_node_rejects_vague_scaffold_plan() -> None:
    violations = validate_plan_contract("# Plan\nBuild a dashboard quickly.")
    assert {"missing API endpoints", "missing database schema", "missing acceptance tests"}.issubset(set(violations))


def test_designer_node_requires_complete_mobile_quality_contract() -> None:
    violations = validate_design_contract({"colors": {"primary": "#fff"}, "typography": {"body": "Inter"}})
    assert "missing spacing" in violations
    assert "missing motion" in violations
    assert "390px mobile breakpoint is not specified" in violations


def test_frontend_node_rejects_the_exact_mock_scaffold_pattern() -> None:
    scaffold = """import React,{useEffect} from 'react';
    export default function App(){useEffect(()=>{/* Simulate API call – replace with real fetch */ const mock=[]},[]);return <main className='transition hover:x focus:x' style={{color:'#34D399'}}><p className='x'>Ready</p><p className='x'>More</p></main>}"""
    violations = validate_frontend_contract(scaffold, {"colors": {"primary": "#34D399"}})
    assert "no real backend API call (fetch/axios)" in violations
    assert "primary journey has no API mutation" in violations
    assert any("mock/placeholder" in item for item in violations)


def test_backend_node_rejects_syntax_only_fastapi_scaffold() -> None:
    violations = validate_backend_contract("from fastapi import FastAPI\napp=FastAPI()\n@app.get('/health')\ndef health(): return {}")
    assert "fewer than five concrete API routes" in violations
    assert "persistent SQLAlchemy database integration is missing" in violations
    assert "authentication/authorization boundary is missing" in violations


def test_integration_node_requires_frontend_backend_resource_overlap() -> None:
    frontend = VALID_FRONTEND.replace("items", "customers")
    violations = validate_fullstack_handoff(frontend, VALID_BACKEND)
    assert "frontend API calls do not reference any backend product resource" in violations


def test_qa_node_rejects_tautological_or_non_api_tests() -> None:
    violations = validate_qa_contract("def test_health():\n    assert True\n")
    assert "fewer than two executable tests" in violations
    assert "tautological assert True is not a product test" in violations
    assert "no API client execution" in violations


def test_qa_node_rejects_ambiguous_generated_backend_import() -> None:
    tests = """from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
def test_health(): assert client.get('/health').status_code == 200
def test_create(): assert client.post('/items', json={}).status_code < 500
"""

    assert "tests must import the generated API from backend.main, not ambiguous main" in validate_qa_contract(tests)


def test_generated_test_bootstrap_prioritizes_project_backend(tmp_path) -> None:
    backend = tmp_path / "backend"
    tests = tmp_path / "tests"
    backend.mkdir()
    tests.mkdir()
    (backend / "main.py").write_text("SOURCE = 'generated-backend'\n", encoding="utf-8")
    (tests / "conftest.py").write_text(GENERATED_TEST_BOOTSTRAP, encoding="utf-8")
    (tests / "test_import.py").write_text(
        "import main\n\ndef test_import_targets_generated_backend():\n    assert main.SOURCE == 'generated-backend'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_import.py", "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_integration_artifact_node_requires_host_and_environment_contracts() -> None:
    violations = validate_integration_artifacts({"docker-compose.yml": "services: {}"})
    assert "compose does not connect frontend and backend services" in violations
    assert "host-native local startup workflow is missing" in violations


def test_devops_node_requires_both_stacks_and_safe_release_procedure() -> None:
    violations = validate_devops_artifacts({".github/workflows/ci.yml": "steps: []", "DEPLOYMENT_CHECKLIST.md": "# Deploy"})
    assert "CI omits backend tests" in violations
    assert "CI omits frontend build" in violations
    assert any("rollback" in item for item in violations)
