"""
Agent Pipeline — Orchestrates multi-agent task execution for NeonBuild.

This module defines the AgentPipeline class which coordinates the lifecycle of
a user-initiated app generation request through the full agent chain:
  Planning → Design → Frontend → Backend → Integration → QA → DevOps

Inference is provider-agnostic: production requests use OmniRoute's
multi-provider routes, while direct NVIDIA NIM remains an explicit fallback.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional
import ast
import copy
import html
import re
import json
import shutil
import subprocess
import tempfile

from .nim_client import NIMClient, NIMConfig
from .sandbox_executor import SandboxExecutor
from .mobile_targets import detect_target, scaffold_for, verify_mobile_build
from .app.services.nim_client import configured_inference_provider, configured_omniroute_route


# Product capabilities users should receive without having to understand or
# repeatedly request an implementation checklist.  The user prompt describes
# the *differentiating product idea*; this baseline is the quality floor for
# every generated full-stack application.
DEFAULT_PRODUCT_BASELINE = """
Every generated application must include this production baseline by default:
- polished responsive web UI with accessible keyboard interactions, loading,
  empty, success, and error states;
- authentication, secure authorization boundaries, input validation, and
  useful seeded/demo data where the product needs user-owned records;
- a complete frontend, backend API, persistent relational data model, and
  documented local startup workflow;
- structured logging and user-safe runtime error handling;
- unit/API tests plus smoke coverage for the primary user journey;
- a quality bar suitable for a product demo, not a static mockup.

Treat these as mandatory defaults. The user request only needs to specify the
product, audience, and any capabilities that are unique to that product.
""".strip()


# A visual quality contract, separate from product functionality, keeps terse
# prompts from producing generic scaffolds. User-specified branding can replace
# the hues, but never the depth, hierarchy, responsiveness, or state coverage.
DEFAULT_VISUAL_QUALITY_BASELINE = """
Every generated user interface must meet the Aurora Metal quality bar by default:
- use a premium, dimensional 2026 visual language: deep metallic surfaces,
  layered translucent glass, controlled emerald energy glows, and restrained
  magenta/fuchsia highlights for focus and delight;
- establish a deliberate type scale, generous spatial rhythm, strong hierarchy,
  bespoke product-relevant components, and crisp iconography;
- include subtle purposeful motion, tactile hover/pressed/focus states, polished
  skeleton/loading, empty, validation, success, and runtime-error experiences;
- remain responsive and touch-friendly from 390px mobile through wide desktop,
  with accessible contrast, reduced-motion support, and keyboard-visible focus;
- avoid flat template grids, newspaper-like layouts, placeholder copy, excessive
  neon, decorative clutter, and repeated generic cards.

If the user provides brand colors, adapt the palette while preserving this same
level of metallic depth, luminous glass, interaction polish, and accessibility.
""".strip()


# Generated projects always place the FastAPI application at backend/main.py.
# Test modules are model-authored and may otherwise use an ambiguous bare
# ``import main``; on a host running NeonBuild, that can resolve to the
# platform's main.py instead of the generated application. This bootstrap
# makes both import styles deterministic while backend.main remains the public
# project contract.
GENERATED_TEST_BOOTSTRAP = """from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Prepend in this exact order: `from backend.main import app` resolves through
# ROOT, and legacy `import main` resolves to the generated backend.
for candidate in (str(ROOT), str(BACKEND)):
    while candidate in sys.path:
        sys.path.remove(candidate)
sys.path[:0] = [str(BACKEND), str(ROOT)]
"""


# A malformed designer response must not terminate an otherwise valid build.
# These deterministic tokens are the platform quality floor; model output can
# override them, but missing categories are always completed here.
DEFAULT_DESIGN_TOKENS: Dict[str, Any] = {
    "colors": {"background": "#07110D", "surface": "#101A17", "surfaceElevated": "#17231F", "primary": "#34D399", "secondary": "#22D3EE", "accent": "#E879F9", "text": "#F5F7F6", "textMuted": "#94A3B8", "success": "#4ADE80", "warning": "#FBBF24", "error": "#FB7185"},
    "typography": {"fontFamily": "Inter, ui-sans-serif, system-ui, sans-serif", "display": "clamp(2.25rem, 5vw, 4.5rem)", "heading": "clamp(1.5rem, 3vw, 2.5rem)", "body": "1rem", "caption": "0.8125rem"},
    "spacing": {"xs": "0.25rem", "sm": "0.5rem", "md": "1rem", "lg": "1.5rem", "xl": "2rem", "2xl": "3rem"},
    "radii": {"sm": "0.5rem", "md": "0.875rem", "lg": "1.25rem", "pill": "999px"},
    "shadows": {"glass": "0 20px 60px rgba(0,0,0,.35)", "glow": "0 0 32px rgba(52,211,153,.16)"},
    "motion": {"fast": "140ms", "normal": "220ms", "slow": "360ms", "easing": "cubic-bezier(.2,.8,.2,1)"},
    "components": {"surface": "translucent metallic glass", "controls": "tactile, accessible, state-complete"},
    "layouts": {"mobile": "single-column touch-first", "desktop": "responsive product workspace"},
    "responsive": {"mobile": "390px", "tablet": "768px", "desktop": "1280px"},
}


def _looks_like_model_refusal(value: str) -> bool:
    """Recognize an actual refusal without rejecting ordinary safety features."""
    opening = value.strip().lower()[:800]
    return any(phrase in opening for phrase in (
        "i cannot fulfill", "i can't fulfill", "i am unable to comply",
        "i'm unable to comply", "i cannot assist", "i can't assist",
        "cannot comply with this request", "violates the safety policy",
    ))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PipelineStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    DESIGNING = "designing"
    BUILDING_FRONTEND = "building_frontend"
    BUILDING_BACKEND = "building_backend"
    INTEGRATING = "integrating"
    QA = "qa"
    DEPLOYING = "deploying"
    COMPLETE = "complete"
    FAILED = "failed"


class AgentRole(str, Enum):
    PLANNER = "planner"
    DESIGNER = "designer"
    FRONTEND = "frontend"
    BACKEND = "backend"
    INTEGRATION = "integration"
    PREVIEW = "preview"
    QA = "qa"
    DEVOPS = "devops"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    """A structured message exchanged between agents in the pipeline."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_role: AgentRole = AgentRole.PLANNER
    to_role: Optional[AgentRole] = None
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PipelineContext:
    """Shared execution context passed across all agents in a pipeline run."""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_prompt: str = ""
    project_dir: str = ""  # Root directory for generated project
    target: str = "web"
    status: PipelineStatus = PipelineStatus.PENDING
    messages: List[AgentMessage] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)  # filename -> content
    errors: List[str] = field(default_factory=list)
    recoveries: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def add_message(self, msg: AgentMessage) -> None:
        self.messages.append(msg)

    def set_artifact(self, name: str, content: str) -> None:
        if name.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                self.errors.append(f"AST validation failed for {name}: {e}")
        elif name.endswith((".js", ".jsx", ".ts", ".tsx")):
            if re.search(r'^\s*import\s+', content, re.MULTILINE) is None and re.search(r'^\s*export\s+', content, re.MULTILINE) is None and re.search(r'function', content) is None and re.search(r'const|let|var', content) is None:
                self.errors.append(f"JS validation failed for {name}: No valid JS/TS constructs found")
                
        self.artifacts[name] = content
        # Also write to disk if project_dir is set
        if self.project_dir:
            self._write_artifact_to_disk(name, content)

    def _write_artifact_to_disk(self, name: str, content: str) -> None:
        """Write artifact to the project directory."""
        if not self.project_dir:
            return
        try:
            project_path = Path(self.project_dir)
            artifact_path = project_path / name
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(content, encoding="utf-8")
        except Exception as e:
            self.errors.append(f"Failed to write artifact {name}: {e}")

    def fail(self, reason: str) -> None:
        self.status = PipelineStatus.FAILED
        self.errors.append(reason)
        self.completed_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class BaseAgent:
    """Abstract base for pipeline agents using the configured inference path."""

    SYSTEM_PROMPT: str = "You are a helpful AI assistant."
    role: AgentRole = AgentRole.PLANNER

    def __init__(self, nim_client: NIMClient) -> None:
        self.nim = nim_client

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError

    def recover_validation_failure(
        self, ctx: PipelineContext, error: ValueError
    ) -> Optional[PipelineContext]:
        """Return a deterministic recovery when this stage has a safe one."""
        return None

    def _selected_model(self, requested_model: Optional[str]) -> Optional[str]:
        """Select an OmniRoute stage policy unless a caller pins a model."""
        if requested_model:
            return requested_model
        if configured_inference_provider() == "omniroute":
            return configured_omniroute_route(self.role.value)
        return None

    async def _call_nim(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> str:
        """Call NIM and return the full response string."""
        messages = [
            {"role": "system", "content": system_prompt or self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        response_parts: List[str] = []
        async for chunk in self.nim.chat_stream(
            messages=messages,
            model=self._selected_model(model),
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            response_parts.append(chunk)
        return "".join(response_parts)

    async def _stream_nim(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Stream NIM response tokens as they arrive."""
        messages = [
            {"role": "system", "content": system_prompt or self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        async for chunk in self.nim.chat_stream(
            messages=messages,
            model=self._selected_model(model),
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield chunk


# ---------------------------------------------------------------------------
# Specialized Agents
# ---------------------------------------------------------------------------

def _design_markdown(design_json: Dict[str, Any]) -> str:
    """Render the validated design tokens as a human-readable DESIGN.md."""
    lines = ["# Design Specification", ""]
    for section, value in design_json.items():
        lines.append(f"## {section.replace('_', ' ').title()}")
        lines.append("")
        if isinstance(value, dict):
            for k, v in value.items():
                lines.append(f"- **{k}**: {v}")
        elif isinstance(value, list):
            for item in value:
                lines.append(f"- {item}")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines)


def parse_design_tokens(raw_design: str) -> Dict[str, Any]:
    """Parse and normalize a designer response into the downstream contract.

    Chat models commonly place valid JSON in a Markdown fence or wrap the
    design system in a named envelope.  Those are presentation variants, not
    generation failures, so this boundary normalizes them to canonical
    ``colors`` and ``typography`` sections before later agents consume them.
    """
    cleaned = raw_design.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        first_object = cleaned.find("{")
        last_object = cleaned.rfind("}")
        if first_object >= 0 and last_object > first_object:
            cleaned = cleaned[first_object:last_object + 1]

    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Designer validation failed: design specification must be a JSON object.")

    for envelope in ("designTokens", "design_tokens", "designSystem", "design_system", "tokens", "theme"):
        nested = parsed.get(envelope)
        if isinstance(nested, dict):
            parsed = nested
            break

    aliases = {
        "colors": ("colorPalette", "color_palette", "palette", "colourPalette", "colour_palette"),
        "typography": ("fonts", "fontStyles", "font_styles", "textStyles", "text_styles"),
    }
    for canonical, alternatives in aliases.items():
        if canonical not in parsed:
            for alternative in alternatives:
                if alternative in parsed:
                    parsed[canonical] = parsed[alternative]
                    break

    # Some models add an arbitrary single section (for example ``visual``)
    # around the actual token set.  Descend only when one of the candidate
    # objects contains recognizable token category names; never guess values.
    if "colors" not in parsed or "typography" not in parsed:
        candidate_names = {"colors", "typography", *aliases["colors"], *aliases["typography"]}
        for value in parsed.values():
            if not isinstance(value, dict) or not (candidate_names & set(value)):
                continue
            merged = dict(value)
            for canonical, alternatives in aliases.items():
                if canonical not in merged:
                    for alternative in alternatives:
                        if alternative in merged:
                            merged[canonical] = merged[alternative]
                            break
            parsed = merged
            break

    missing = [key for key in ("colors", "typography") if key not in parsed]
    if missing:
        received = ", ".join(sorted(str(key) for key in parsed.keys())[:12]) or "none"
        raise ValueError(
            "Designer validation failed: Missing required token categories "
            f"{', '.join(missing)}. Received top-level keys: {received}."
        )
    return parsed


def complete_design_tokens(raw_design: str) -> Dict[str, Any]:
    """Complete partial designer JSON with NeonBuild's deterministic baseline."""
    completed = copy.deepcopy(DEFAULT_DESIGN_TOKENS)
    cleaned = raw_design.strip()
    first_object, last_object = cleaned.find("{"), cleaned.rfind("}")
    if first_object >= 0 and last_object > first_object:
        cleaned = cleaned[first_object:last_object + 1]
    try:
        partial = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        partial = {}
    if not isinstance(partial, dict):
        partial = {}
    for envelope in ("designTokens", "design_tokens", "designSystem", "design_system", "tokens", "theme"):
        if isinstance(partial.get(envelope), dict):
            partial = partial[envelope]
            break
    aliases = {
        "colors": ("colorPalette", "color_palette", "palette", "colourPalette", "colour_palette"),
        "typography": ("fonts", "fontStyles", "font_styles", "textStyles", "text_styles"),
    }
    candidate_names = {"colors", "typography", *aliases["colors"], *aliases["typography"]}
    if not (candidate_names & set(partial)):
        for value in partial.values():
            if isinstance(value, dict) and candidate_names & set(value):
                partial = value
                break
    for canonical, alternatives in aliases.items():
        if canonical not in partial:
            for alternative in alternatives:
                if alternative in partial:
                    partial[canonical] = partial[alternative]
                    break
    for key, value in partial.items():
        if isinstance(value, dict) and isinstance(completed.get(key), dict):
            completed[key].update(value)
        elif isinstance(completed.get(key), dict):
            # Required structured categories cannot be replaced by a model's
            # shorthand list/string representation.
            continue
        elif value not in (None, "", [], {}):
            completed[key] = value
    return completed


def unwrap_generated_code(raw_output: str) -> str:
    """Extract model-generated code from a Markdown fence when present."""
    output = raw_output.strip()
    fenced = re.search(r"```[^\n]*\n(.*?)\n?```", output, re.DOTALL)
    return fenced.group(1).strip() if fenced else output


def validate_plan_contract(plan: str) -> List[str]:
    """Reject plans that omit the contracts downstream generators require."""
    lowered = plan.lower()
    required = {
        "features": ("features", "user journeys"),
        "API endpoints": ("api endpoints", "api contract"),
        "database schema": ("database schema", "data model"),
        "acceptance tests": ("acceptance", "test strategy"),
        "local startup": ("local startup", "local development", "run locally"),
    }
    violations = [f"missing {label}" for label, aliases in required.items() if not any(alias in lowered for alias in aliases)]
    if len(re.findall(r"\b(?:get|post|put|patch|delete)\s+/", lowered)) < 3:
        violations.append("fewer than three concrete API endpoint declarations")
    return violations


def validate_design_contract(design: Dict[str, Any]) -> List[str]:
    required = ("colors", "typography", "spacing", "radii", "shadows", "motion", "components", "layouts", "responsive")
    violations = [f"missing {name}" for name in required if not isinstance(design.get(name), dict) or not design[name]]
    breakpoints = json.dumps(design.get("responsive", {})).lower()
    if "390" not in breakpoints:
        violations.append("390px mobile breakpoint is not specified")
    return violations


def validate_frontend_contract(code: str, design_json: Optional[Dict[str, Any]] = None) -> List[str]:
    """Require a real API-driven, state-complete, responsive product UI."""
    violations = lint_frontend_design_tokens(code, design_json)
    lowered = code.lower()
    if not re.search(r"\b(fetch|axios\.)\s*\(", code):
        violations.append("no real backend API call (fetch/axios)")
    if not re.search(r"(?:vite_api|api_url|/api/v\d|['\"]/api/)", code, re.I):
        violations.append("no configurable or versioned API base URL")
    if not re.search(r"method\s*:\s*['\"](?:post|put|patch|delete)['\"]", code, re.I):
        violations.append("primary journey has no API mutation")
    if not re.search(r"<(?:form|input|textarea|select)\b", code, re.I):
        violations.append("primary data-entry interaction is missing")
    if "data-testid=\"primary-form\"" not in code and "data-testid='primary-form'" not in code:
        violations.append("primary form lacks the stable E2E test contract")
    if "data-testid=\"primary-submit\"" not in code and "data-testid='primary-submit'" not in code:
        violations.append("primary submit action lacks the stable E2E test contract")
    if not all(term in lowered for term in ("loading", "error")):
        violations.append("loading and error states are not both implemented")
    if not re.search(r"(?:empty|\.length\s*===\s*0|!\w+\.length)", code, re.I):
        violations.append("empty state is not implemented")
    forbidden = ("simulate api", "pretend network", "replace with real fetch", "placeholder icon", "todo: implement", "would open here")
    found = [phrase for phrase in forbidden if phrase in lowered]
    if found:
        violations.append("mock/placeholder implementation detected: " + ", ".join(found))
    return violations


def validate_backend_contract(code: str) -> List[str]:
    violations: List[str] = []
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return [f"invalid Python: {exc}"]
    lowered = code.lower()
    routes = re.findall(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)", code, re.I)
    methods = {method.lower() for method, _ in routes}
    if len(routes) < 5:
        violations.append("fewer than five concrete API routes")
    if not {"get", "post"}.issubset(methods):
        violations.append("read and create API operations are not both present")
    if not any("health" in path.lower() for _, path in routes):
        violations.append("health/readiness endpoint is missing")
    if "sqlalchemy" not in lowered or not re.search(r"create_engine|async_engine|sessionmaker|asyncsession", code, re.I):
        violations.append("persistent SQLAlchemy database integration is missing")
    if not re.search(r"jwt|oauth2|authorization", code, re.I):
        violations.append("authentication/authorization boundary is missing")
    if "corsmiddleware" not in lowered:
        violations.append("CORS integration is missing")
    if not re.search(r"BaseModel|pydantic", code):
        violations.append("Pydantic request validation is missing")
    if re.search(r"SECRET_KEY\s*=\s*['\"][^'\"]+['\"]", code) and "getenv" not in lowered:
        violations.append("secret is hard-coded instead of environment-driven")
    return violations


def validate_fullstack_handoff(frontend: str, backend: str) -> List[str]:
    """Check that the frontend API vocabulary overlaps the backend's real routes."""
    violations: List[str] = []
    backend_paths = [path.lower() for _, path in re.findall(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)", backend, re.I)]
    # Normalize resource names from paths, ignoring generic API/version segments.
    resources = {part for path in backend_paths for part in path.split("/") if part and not part.startswith(("api", "v1", "v2", "{")) and part not in {"health", "auth", "me"}}
    if not resources:
        violations.append("backend exposes no product resource routes")
    elif not any(re.search(rf"\b{re.escape(resource)}\b", frontend, re.I) for resource in resources):
        violations.append("frontend API calls do not reference any backend product resource")
    if not re.search(r"(?:vite_api|api_url|/api/)", frontend, re.I):
        violations.append("frontend has no backend API base configuration")
    return violations


def validate_qa_contract(tests: str) -> List[str]:
    violations: List[str] = []
    try:
        ast.parse(tests)
    except SyntaxError as exc:
        return [f"invalid Python tests: {exc}"]
    lowered = tests.lower()
    if len(re.findall(r"^def\s+test_", tests, re.M)) < 2:
        violations.append("fewer than two executable tests")
    if "assert true" in lowered:
        violations.append("tautological assert True is not a product test")
    if not re.search(r"testclient|httpx|client\.(?:get|post|put|patch|delete)", tests, re.I):
        violations.append("no API client execution")
    if "health" not in lowered:
        violations.append("health/readiness smoke test is missing")
    if not re.search(r"client\.(?:post|put|patch|delete)", tests, re.I):
        violations.append("primary mutation journey is not tested")
    # Generated projects expose their FastAPI application as backend.main.
    # Bare `main` imports can silently select NeonBuild's own module when a
    # generated project is verified from within the platform workspace.
    if re.search(r"^\s*(?:from\s+main\s+import|import\s+main(?:\s|$))", tests, re.M) or re.search(
        r"import_module\(\s*['\"]main['\"]", tests
    ):
        violations.append("tests must import the generated API from backend.main, not ambiguous main")
    return violations


def validate_integration_artifacts(artifacts: Dict[str, str]) -> List[str]:
    violations: List[str] = []
    compose = artifacts.get("docker-compose.yml", "").lower()
    env = artifacts.get(".env.example", "") + artifacts.get("frontend/.env.example", "")
    if "services:" not in compose or "frontend" not in compose or "backend" not in compose:
        violations.append("compose does not connect frontend and backend services")
    if not all(name in env for name in ("API", "DATABASE", "SECRET")):
        violations.append("environment templates omit API, DATABASE, or SECRET configuration")
    if "backend/requirements.txt" not in artifacts:
        violations.append("backend dependency lock contract is missing")
    if "frontend/package.json" not in artifacts:
        violations.append("frontend build contract is missing")
    test_bootstrap = artifacts.get("tests/conftest.py", "")
    if "BACKEND" not in test_bootstrap or "sys.path" not in test_bootstrap:
        violations.append("generated API test import bootstrap is missing")
    if "RUN_LOCAL.md" not in artifacts or "no Docker required" not in artifacts["RUN_LOCAL.md"]:
        violations.append("host-native local startup workflow is missing")
    return violations


def validate_devops_artifacts(artifacts: Dict[str, str]) -> List[str]:
    ci = artifacts.get(".github/workflows/ci.yml", "").lower()
    checklist = artifacts.get("DEPLOYMENT_CHECKLIST.md", "").lower()
    violations: List[str] = []
    for label, marker in (("backend tests", "pytest"), ("frontend build", "npm run build"), ("checkout", "actions/checkout")):
        if marker not in ci:
            violations.append(f"CI omits {label}")
    if not all(term in checklist for term in ("migration", "secret", "health", "rollback")):
        violations.append("deployment checklist omits migrations, secrets, health checks, or rollback")
    return violations


async def run_host_command(command: List[str], cwd: Path, timeout: int = 600) -> tuple[bool, str]:
    """Run a generated-project verifier without Docker and capture diagnostics."""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        text_output = output.decode("utf-8", errors="replace")[-12000:]
        return process.returncode == 0, text_output
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return False, f"Command timed out after {timeout}s: {' '.join(command)}"
    except OSError as exc:
        return False, f"Could not run {' '.join(command)}: {exc}"


def deterministic_project_smoke_tests() -> str:
    """Executable fallback checks that never depend on generated imports."""
    return '''from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]


def test_backend_is_valid_fastapi_module():
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert "FastAPI" in source
    routes = re.findall(r"@\\w+\\.(get|post|put|patch|delete)\\(", source, re.I)
    assert len(routes) >= 5
    assert "health" in source.lower()
    assert "sqlalchemy" in source.lower()
    assert re.search(r"jwt|oauth2|authorization", source, re.I)


def test_frontend_has_runnable_component_contract():
    source = (ROOT / "frontend" / "App.tsx").read_text(encoding="utf-8")
    assert re.search(r"^\\s*(import|export)\\s", source, re.MULTILINE)
    assert re.search(r"(function\\s+[A-Z]|const\\s+[A-Z].*=>|export\\s+default)", source)
    assert "className=" in source or "style={{" in source
    assert re.search(r"\\b(fetch|axios\\.)\\s*\\(", source)
    compact = re.sub(r"\\s+", "", source.lower())
    assert any(f"method:'{method}'" in compact or f'method:"{method}"' in compact for method in ("post", "put", "patch", "delete"))
    assert not any(term in source.lower() for term in ("simulate api", "pretend network", "replace with real fetch", "would open here"))


def test_frontend_declares_versioned_backend_contract():
    frontend = (ROOT / "frontend" / "App.tsx").read_text(encoding="utf-8")
    assert re.search(r"(?:vite_api|api_url|/api/)", frontend, re.I)


def test_preview_is_offline_and_interactive():
    source = (ROOT / "index.html").read_text(encoding="utf-8").lower()
    assert "<!doctype html" in source
    assert "<style" in source and "<script" in source
    assert not re.search(r"(?:src|href)=[\\\"']https?://", source)
    assert "${var(" not in source
    assert "would open here" not in source
'''


def validate_preview_html(source: str) -> List[str]:
    """Validate preview syntax, offline behavior, responsiveness, and polish."""
    violations: List[str] = []
    lowered = source.lower()
    if "<!doctype html" not in lowered or "<script" not in lowered or "<style" not in lowered:
        violations.append("expected self-contained HTML with inline style and script")
    if re.search(r"(?:src|href)=[\"']https?://", source, re.I):
        violations.append("remote preview dependency is not allowed")
    if re.search(r"<script[^>]+src=", source, re.I):
        violations.append("script dependencies must be inline")
    if "@media" not in source:
        violations.append("responsive media query is missing")
    if len(re.findall(r"<button\b", source, re.I)) < 2:
        violations.append("primary interactions are incomplete")
    if any(phrase in lowered for phrase in ("would open here", "placeholder interaction", "todo: implement")):
        violations.append("placeholder interaction text is not allowed")
    quality_markers = sum(bool(re.search(pattern, source, re.I)) for pattern in (
        r"backdrop-filter\s*:", r"(?:linear|radial)-gradient\(", r"box-shadow\s*:",
    ))
    if quality_markers < 2:
        violations.append("visual quality floor is missing dimensional glass/gradient/shadow treatment")

    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script\s*>", source, re.I | re.S)
    inline_javascript = "\n".join(scripts).strip()
    if inline_javascript:
        if "${var(" in inline_javascript:
            violations.append("JavaScript contains an invalid CSS var() template expression")
        node = shutil.which("node")
        if node:
            script_path = ""
            try:
                with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
                    handle.write(inline_javascript)
                    script_path = handle.name
                checked = subprocess.run([node, "--check", script_path], capture_output=True, text=True, timeout=15)
                if checked.returncode != 0:
                    diagnostic = (checked.stderr or checked.stdout).strip().splitlines()
                    violations.append("inline JavaScript syntax is invalid: " + (diagnostic[-1] if diagnostic else "node --check failed"))
            except (OSError, subprocess.SubprocessError) as exc:
                violations.append(f"inline JavaScript syntax check could not run: {exc}")
            finally:
                if script_path:
                    Path(script_path).unlink(missing_ok=True)
    return violations


# ---------------------------------------------------------------------------
# EM-4: Structural design-token lint (replaces the "backdrop-blur" string
# search). A generated frontend must demonstrate, structurally, that the
# designer's tokens were actually applied: module structure, a component
# definition, a minimum number of styling applications, at least one
# motion/interaction primitive, and fidelity to the designer's palette.
# ---------------------------------------------------------------------------

MIN_STYLE_APPLICATIONS = 3
_MOTION_PRIMITIVES = re.compile(
    r"transition|animate|animation|keyframes|motion\.|hover:|active:|focus:"
)
_STYLE_APPLICATIONS = re.compile(r"className=|style=\{|styled\.|css\(|sx=\{")
_COMPONENT_DEF = re.compile(
    r"function\s+[A-Z]\w*|const\s+[A-Z]\w*\s*=|class\s+[A-Z]\w*"
)
_MODULE_STRUCTURE = re.compile(r"^\s*(import|export)\s", re.MULTILINE)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\b")


def extract_palette_colors(design_json: Dict[str, Any]) -> List[str]:
    """Pull hex colors out of the validated designer tokens."""
    colors: List[str] = []
    section = design_json.get("colors") or design_json.get("color_palette") or {}
    if isinstance(section, dict):
        for value in section.values():
            if isinstance(value, str):
                colors.extend(_HEX_COLOR.findall(value))
    elif isinstance(section, list):
        for value in section:
            if isinstance(value, str):
                colors.extend(_HEX_COLOR.findall(value))
    return [c.lower() for c in colors]


def lint_frontend_design_tokens(code: str, design_json: Optional[Dict[str, Any]] = None) -> List[str]:
    """Return a list of structural violations (empty list = compliant)."""
    violations: List[str] = []
    if not _MODULE_STRUCTURE.search(code):
        violations.append("no module structure: generated frontend has no import/export statements")
    if not _COMPONENT_DEF.search(code):
        violations.append("no component definition: expected function/const/class React component")
    style_applications = len(_STYLE_APPLICATIONS.findall(code))
    if style_applications < MIN_STYLE_APPLICATIONS:
        violations.append(
            f"only {style_applications} styling application(s) found "
            f"(< {MIN_STYLE_APPLICATIONS}): design tokens are not actually applied"
        )
    if not _MOTION_PRIMITIVES.search(code):
        violations.append(
            "no motion/interaction primitives (transition/animation/hover/focus states)"
        )
    if design_json:
        palette = extract_palette_colors(design_json)
        if palette:
            code_lower = code.lower()
            if not any(color in code_lower for color in palette):
                violations.append(
                    "palette fidelity failure: none of the designer's palette colors "
                    f"({', '.join(sorted(set(palette))[:6])}) appear in the generated code"
                )
    return violations


class PlannerAgent(BaseAgent):
    role = AgentRole.PLANNER
    SYSTEM_PROMPT = (
        "You are a senior software architect. Given a user request, produce a "
        "detailed project plan in Markdown. Use these exact headings: Overview, "
        "Tech Stack, Features, API Endpoints, Database Schema, Acceptance Tests, "
        "Local Startup, and Milestones. Under API Endpoints declare at least three "
        "concrete METHOD /path operations. Be specific and thorough."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.PLANNING
        ctx.target = detect_target(ctx.user_prompt)
        error_context = ""
        if ctx.errors and "Planner validation" in ctx.errors[-1]:
            error_context = (
                "\n\nPREVIOUS VALIDATION FAILURE — correct every missing item "
                f"in this replacement plan:\n{ctx.errors[-1]}"
            )
        plan = await self._call_nim(
            user_message=(
                "Plan a full-stack application for the user's product idea below. "
                "Apply the mandatory product baseline without asking the user to repeat it.\n\n"
                f"PRODUCT BASELINE:\n{DEFAULT_PRODUCT_BASELINE}\n\n"
                f"VISUAL QUALITY BASELINE:\n{DEFAULT_VISUAL_QUALITY_BASELINE}\n\n"
                f"DELIVERY TARGET: {ctx.target}\n"
                "Plan for this exact platform and its deployment requirements. "
                "Return Markdown with all of these exact headings: Overview, Tech Stack, "
                "Features, API Endpoints, Database Schema, Acceptance Tests, Local Startup, "
                "Milestones. Include at least three lines formatted like `GET /api/v1/resource`.\n\n"
                f"USER PRODUCT IDEA:\n{ctx.user_prompt}"
                f"{error_context}"
            ),
            temperature=0.3,
            max_tokens=3000,
        )
        
        if _looks_like_model_refusal(plan):
             raise ValueError("NVIDIA AI Safety Filter Triggered: The upstream model refused to generate a plan for this prompt due to safety guidelines. Please try a different prompt.")
        violations = validate_plan_contract(plan)
        if violations:
            raise ValueError("Planner validation failed: " + "; ".join(violations))
             
        ctx.set_artifact("PLAN.md", plan)
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.DESIGNER,
            content=plan,
            metadata={"artifact": "PLAN.md"},
        ))
        return ctx


class DesignerAgent(BaseAgent):
    role = AgentRole.DESIGNER
    SYSTEM_PROMPT = (
        "You are a senior UI/UX designer and frontend architect. Given a project plan, "
        "produce a complete JSON design specification covering: color palette, typography, "
        "component hierarchy, page layouts, responsive breakpoints, and specific CSS classes to use (like backdrop-blur). "
        "The supplied Aurora Metal visual quality baseline is mandatory. Translate it "
        "into product-specific tokens and components instead of a generic dashboard. "
        "Output ONLY a valid JSON object—no Markdown fences or prose—with this exact top-level shape: "
        '{"colors": {...}, "typography": {...}, "components": {...}, "layouts": {...}, "responsive": {...}}.'
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.DESIGNING
        plan = ctx.artifacts.get("PLAN.md", "")
        
        error_context = ""
        if ctx.errors and "Designer validation" in ctx.errors[-1]:
            error_context = f"\n\nPREVIOUS ERROR TO FIX:\n{ctx.errors[-1]}"

        design = await self._call_nim(
            user_message=(f"Design the UI tokens for this project:\n\n{plan}\n\n"
                          f"VISUAL QUALITY BASELINE:\n{DEFAULT_VISUAL_QUALITY_BASELINE}"
                          f"{error_context}"),
            temperature=0.5,
            max_tokens=3000,
        )
        ctx.artifacts["_designer_last_attempt.json"] = design
        
        # Normalize harmless model presentation/schema variants at the
        # inference boundary before downstream agents consume the artifact.
        try:
            design_json = parse_design_tokens(design)
        except json.JSONDecodeError:
            if _looks_like_model_refusal(design):
                raise ValueError("NVIDIA AI Safety Filter Triggered: The upstream model refused to generate content for this prompt due to safety guidelines. Please try a different prompt.")
            raise ValueError(f"Designer validation failed: Output must be valid JSON. (Got: {design[:50]}...)")

        design_json = complete_design_tokens(json.dumps(design_json))
        violations = validate_design_contract(design_json)
        if violations:
            raise ValueError("Designer validation failed: " + "; ".join(violations))
        ctx.artifacts.pop("_designer_last_attempt.json", None)
        ctx.set_artifact("design_tokens.json", json.dumps(design_json, indent=2))
        # DESIGN.md: human-readable design spec artifact (expected by the
        # generated-project contract alongside design_tokens.json).
        ctx.set_artifact("DESIGN.md", _design_markdown(design_json))
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.FRONTEND,
            content=json.dumps(design_json),
            metadata={"artifact": "design_tokens.json"},
        ))
        return ctx

    def recover_validation_failure(
        self, ctx: PipelineContext, error: ValueError
    ) -> Optional[PipelineContext]:
        if "Designer validation failed" not in str(error):
            return None
        raw_design = ctx.artifacts.pop("_designer_last_attempt.json", "")
        design_json = complete_design_tokens(raw_design)
        ctx.set_artifact("design_tokens.json", json.dumps(design_json, indent=2))
        ctx.set_artifact("DESIGN_RECOVERY.json", json.dumps({
            "strategy": "deterministic_neonbuild_baseline",
            "reason": str(error),
            "preserved_partial_output": bool(raw_design.strip()),
        }, indent=2))
        ctx.set_artifact("DESIGN.md", _design_markdown(design_json))
        ctx.add_message(AgentMessage(from_role=self.role, to_role=AgentRole.FRONTEND, content=json.dumps(design_json), metadata={"artifact": "design_tokens.json", "recovered": True}))
        return ctx


class FrontendAgent(BaseAgent):
    role = AgentRole.FRONTEND
    SYSTEM_PROMPT = (
        "You are an expert React/TypeScript frontend engineer. Given a design spec, "
        "generate complete, production-ready React component code using Tailwind CSS. "
        "You MUST ensure the UI exactly matches the premium design tokens provided. "
        "Apply the supplied Aurora Metal quality baseline, all responsive breakpoints, "
        "accessible interaction states, and polished loading/empty/error states. "
        "Build a real API-driven application, never demo data or simulated calls. Use only "
        "React and browser APIs so the supplied Vite scaffold builds without undeclared packages. "
        "The primary journey must read and mutate the FastAPI /api/v1 contract, include a real "
        "data-entry form, and expose loading, empty, success, validation, and error states. "
        "Output only valid, runnable code with no placeholders, TODOs, or fake interactions."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.BUILDING_FRONTEND
        design = ctx.artifacts.get("design_tokens.json", "")
        plan = ctx.artifacts.get("PLAN.md", "")
        
        error_context = ""
        if ctx.errors and "Frontend validation" in ctx.errors[-1]:
            previous_attempt = ctx.artifacts.get("_frontend_last_attempt.tsx", "")
            error_context = (
                f"\n\nPREVIOUS ERROR TO FIX:\n{ctx.errors[-1]}\n\n"
                "PREVIOUS INVALID FRONTEND OUTPUT (replace it completely with runnable App.tsx):\n"
                f"{previous_attempt[:12000]}"
            )

        if ctx.target == "flutter":
            request = (
                "Build the complete Flutter presentation layer as lib/main.dart. "
                "Use Material 3, responsive LayoutBuilder patterns, semantic labels, "
                "complete loading/empty/error states, and the supplied design tokens. "
                "Declare a public const GeneratedApp widget. Output only runnable Dart."
            )
        elif ctx.target == "react-native":
            request = (
                "Build the complete Expo Router React Native screen as app/index.tsx. "
                "Use only React Native primitives and Expo-compatible packages, SafeAreaView, "
                "responsive dimensions, accessibility labels, and complete state surfaces. "
                "Do not use DOM elements or Tailwind CSS. Output runnable TypeScript only."
            )
        else:
            request = (
                "DELIVERY ENVELOPE (non-negotiable): return one complete, compact App.tsx in this "
                "single response. Do not split it into parts, promise a later message, explain size "
                "limits, use Markdown fences, or omit any required behavior. Keep the source below "
                "350 TypeScript lines by using focused components and shared helpers; concise code is "
                "preferred to a partial implementation.\n\n"
                "Build the complete React frontend as one self-contained App.tsx. Use fetch with "
                "const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'. Implement at least "
                "one real GET and one real POST/PATCH/DELETE in the primary user journey. Do not "
                "use mock arrays, artificial delays, placeholder alerts, external icon packages, "
                "or imports other than React. Include an inline SVG icon system if needed. Put "
                "data-testid=\"primary-form\" on the main form and data-testid=\"primary-submit\" "
                "on its submit button so the supplied browser QA can execute the journey."
            )
        code = await self._call_nim(
            user_message=(
                f"{request}\n\nPLAN:\n{plan}\n\n"
                f"DESIGN TOKENS:\n{design}\n\n"
                "VISUAL DELIVERY: implement a premium Aurora Metal interface with deep metallic "
                "glass surfaces, emerald energy and restrained fuchsia focus accents, deliberate "
                "type hierarchy, responsive 390px-to-desktop layout, accessible focus states, and "
                "purposeful subtle motion. Avoid generic cards and placeholder copy."
                f"{error_context}"
            ),
            temperature=0.2,
            max_tokens=4800,
        )
        code = unwrap_generated_code(code)
        # Keep an invalid response in transient pipeline context so a retry can
        # correct the actual attempted source. It is intentionally not written
        # to the generated project until it passes the structural contract.
        ctx.artifacts["_frontend_last_attempt.tsx"] = code
        
        if ctx.target == "flutter":
            if "GeneratedApp" not in code or "MaterialApp" not in code or "Widget" not in code:
                raise ValueError("Frontend validation failed: Flutter entrypoint must declare GeneratedApp and MaterialApp")
            artifact_name = "mobile/lib/main.dart"
        elif ctx.target == "react-native":
            if "react-native" not in code or not re.search(r"export\s+default", code):
                raise ValueError("Frontend validation failed: Expo screen must import react-native and default-export a component")
            artifact_name = "mobile/app/index.tsx"
        else:
          # EM-4: structural design-token lint (replaces the old single-keyword
        # string-search gate).
          design_json: Optional[Dict[str, Any]] = None
          try:
              design_json = json.loads(design) if design else None
          except (json.JSONDecodeError, TypeError):
              design_json = None
          violations = validate_frontend_contract(code, design_json)
          if violations:
              raise ValueError("Frontend validation failed: design tokens not structurally applied -- " + "; ".join(violations))
          artifact_name = "frontend/App.tsx"

        ctx.artifacts.pop("_frontend_last_attempt.tsx", None)
        ctx.set_artifact(artifact_name, code)
        for name, content in scaffold_for(ctx.target, "NeonBuild App").items():
            if name != artifact_name:
                ctx.set_artifact(name, content)
        ctx.set_artifact("TARGET.json", json.dumps({"target": ctx.target, "platforms": ["android", "ios"] if ctx.target in {"flutter", "react-native"} else ["web"]}, indent=2))
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.BACKEND,
            content=code,
            metadata={"artifact": artifact_name, "target": ctx.target},
        ))
        return ctx


class BackendAgent(BaseAgent):
    role = AgentRole.BACKEND
    SYSTEM_PROMPT = (
        "You are an expert Python/FastAPI backend engineer. Given a project plan, "
        "generate a complete, production-ready FastAPI application with all routes, "
        "Pydantic models, database integration (SQLAlchemy), and auth (JWT). "
        "BACKEND REQUIREMENT (THE HARDENING): You MUST ensure the backend is fully hardened. "
        "Implement defensive programming, strict thread safety (use Locks across shared state), "
        "comprehensive input validation, and proper error boundaries. "
        "Output only valid, runnable Python code."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.BUILDING_BACKEND
        plan = ctx.artifacts.get("PLAN.md", "")
        repair_context = ""
        if ctx.errors and "Backend validation failed" in ctx.errors[-1]:
            previous_attempt = ctx.artifacts.get("_backend_last_attempt.py", "")
            repair_context = (
                "\n\nA previous backend attempt failed validation. Return a corrected, "
                "complete module only; do not repeat the syntax error.\n"
                f"VALIDATION ERROR:\n{ctx.errors[-1]}\n\n"
                f"PREVIOUS ATTEMPT:\n{previous_attempt}"
            )
        code = await self._call_nim(
            user_message=("Build the complete FastAPI backend for the plan below. It must expose "
                          "at least five concrete routes under /api/v1 including health, auth, and "
                          "persistent CRUD for the primary product resource. Use SQLAlchemy, Pydantic, "
                          "CORS, environment-driven secrets, and a SQLite local default. The module "
                          "must import and start on a clean host after installing backend/requirements.txt.\n\n"
                          f"{plan}{repair_context}"),
            temperature=0.2,
            max_tokens=12000,
        )
        code = unwrap_generated_code(code)
        violations = validate_backend_contract(code)
        if violations:
            # Preserve the exact failed attempt for the next repair pass
            # without writing unvalidated code into the project workspace.
            ctx.artifacts["_backend_last_attempt.py"] = code
            raise ValueError("Backend validation failed: " + "; ".join(violations))
        ctx.artifacts.pop("_backend_last_attempt.py", None)
        ctx.set_artifact("backend/main.py", code)
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.INTEGRATION,
            content=code,
            metadata={"artifact": "backend/main.py"},
        ))
        return ctx


class PreviewAgent(BaseAgent):
    """Guarantee that every successful job has a loadable interactive preview."""
    role = AgentRole.PREVIEW
    SYSTEM_PROMPT = (
        "You are a preview engineer. Produce one complete self-contained index.html for the "
        "supplied product and design. It must use inline CSS and JavaScript only: no imports, "
        "CDNs, remote fonts, remote images, placeholders, or network requirements. Implement "
        "the primary interaction, responsive desktop/mobile layouts, and loading/empty/error "
        "states. For native targets this is explicitly a faithful interactive simulation, not "
        "a native runtime. Output HTML only, beginning with <!doctype html>."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        html = unwrap_generated_code(await self._call_nim(
            user_message=(
                f"TARGET: {ctx.target}\nPLAN:\n{ctx.artifacts.get('PLAN.md','')}\n"
                f"DESIGN:\n{ctx.artifacts.get('design_tokens.json','')}\n"
                "IMPLEMENTED FRONTEND TO REPRODUCE FAITHFULLY:\n"
                f"{ctx.artifacts.get('frontend/App.tsx', '')[:12000]}"
            ),
            temperature=0.2, max_tokens=6000,
        ))
        ctx.artifacts["_preview_last_attempt.html"] = html
        violations = validate_preview_html(html)
        if violations:
            raise ValueError("Preview validation failed: " + "; ".join(violations))
        ctx.artifacts.pop("_preview_last_attempt.html", None)
        ctx.set_artifact("index.html", html)
        mode = "mobile_simulation" if ctx.target in {"flutter", "react-native"} else "interactive_web"
        ctx.set_artifact("PREVIEW_MODE.json", json.dumps({"mode": mode, "target": ctx.target, "native_runtime": False if mode == "mobile_simulation" else None}, indent=2))
        ctx.add_message(AgentMessage(from_role=self.role, to_role=AgentRole.QA, content="Interactive preview generated.", metadata={"artifact": "index.html", "mode": mode}))
        return ctx

    def recover_validation_failure(
        self, ctx: PipelineContext, error: ValueError
    ) -> Optional[PipelineContext]:
        return None


class IntegrationAgent(BaseAgent):
    role = AgentRole.INTEGRATION
    SYSTEM_PROMPT = (
        "You are a DevOps and integration specialist. Given frontend and backend code, "
        "produce docker-compose.yml, environment variable templates (.env.example), "
        "Dockerfile for frontend, Dockerfile for backend, and integration glue code "
        "to wire the full stack together. Output each file as a separate artifact."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.INTEGRATING
        frontend = ctx.artifacts.get("frontend/App.tsx", "")
        backend = ctx.artifacts.get("backend/main.py", "")
        plan = ctx.artifacts.get("PLAN.md", "")
        violations = validate_fullstack_handoff(frontend, backend)
        if violations:
            raise ValueError("Integration validation failed: " + "; ".join(violations))

        # A generated app must run on a clean host without Docker. Container
        # files below are optional deployment conveniences only.
        ctx.set_artifact("backend/requirements.txt", "fastapi>=0.115,<1\nuvicorn[standard]>=0.30,<1\nSQLAlchemy>=2,<3\npydantic[email]>=2,<3\npython-jose[cryptography]>=3.3,<4\npasslib[bcrypt]>=1.7,<2\npython-multipart>=0.0.9,<1\nhttpx>=0.27,<1\npytest>=8,<9\n")
        ctx.set_artifact("backend/__init__.py", "\"\"\"Generated FastAPI application package.\"\"\"\n")
        ctx.set_artifact("tests/conftest.py", GENERATED_TEST_BOOTSTRAP)
        ctx.set_artifact("RUN_LOCAL.md", "# Run locally (no Docker required)\n\n## Backend\n`python -m pip install -r backend/requirements.txt`\n\n`python -m uvicorn backend.main:app --reload --port 8000`\n\n## Frontend\n`cd frontend`\n\n`npm install`\n\n`npm run dev`\n\nThe Vite development server proxies `/api` to the backend. Copy each `.env.example` before supplying production secrets.\n")
        repair_context = f"\nPREVIOUS INTEGRATION FAILURE TO FIX:\n{ctx.errors[-1]}" if ctx.errors and "Integration validation failed" in ctx.errors[-1] else ""
        
        # Generate docker-compose.yml
        docker_compose = await self._call_nim(
            user_message=(
                f"Generate a complete docker-compose.yml for this project:\n\n"
                f"PLAN:\n{plan[:2000]}\n\n"
                f"FRONTEND (React/Next.js):\n{frontend[:1000]}\n\n"
                f"BACKEND (FastAPI):\n{backend[:1000]}\nThe services must be named frontend and backend.{repair_context}"
            ),
            temperature=0.2,
            max_tokens=3000,
        )
        docker_compose = unwrap_generated_code(docker_compose)
        ctx.set_artifact("docker-compose.yml", docker_compose)
        
        # Generate .env.example
        env_example = await self._call_nim(
            user_message=(
                f"Generate a complete .env.example file for this project:\n\n"
                f"PLAN:\n{plan[:2000]}\nInclude API_URL, DATABASE_URL, and SECRET_KEY with safe example values.{repair_context}"
            ),
            temperature=0.2,
            max_tokens=1000,
        )
        env_example = unwrap_generated_code(env_example)
        ctx.set_artifact(".env.example", env_example)
        
        # Generate frontend Dockerfile
        frontend_dockerfile = await self._call_nim(
            user_message=(
                f"Generate a production Dockerfile for the frontend:\n\n"
                f"FRONTEND:\n{frontend[:1000]}"
            ),
            temperature=0.2,
            max_tokens=1500,
        )
        frontend_dockerfile = unwrap_generated_code(frontend_dockerfile)
        ctx.set_artifact("frontend/Dockerfile", frontend_dockerfile)
        
        # Generate backend Dockerfile
        backend_dockerfile = await self._call_nim(
            user_message=(
                f"Generate a production Dockerfile for the backend:\n\n"
                f"BACKEND:\n{backend[:1000]}"
            ),
            temperature=0.2,
            max_tokens=1500,
        )
        backend_dockerfile = unwrap_generated_code(backend_dockerfile)
        ctx.set_artifact("backend/Dockerfile", backend_dockerfile)
        integration_violations = validate_integration_artifacts(ctx.artifacts)
        if integration_violations:
            raise ValueError("Integration validation failed: " + "; ".join(integration_violations))
        
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.QA,
            content="Integration complete: docker-compose.yml, .env.example, frontend/Dockerfile, backend/Dockerfile generated",
        ))
        return ctx


class QAAgent(BaseAgent):
    role = AgentRole.QA
    SYSTEM_PROMPT = (
        "You are a QA engineer specializing in automated testing. Given project artifacts, "
        "generate comprehensive pytest test suites covering unit tests and API endpoint tests. "
        "Output only valid, runnable Python test code."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.QA
        backend = ctx.artifacts.get("backend/main.py", "")
        if ctx.errors and any(marker in ctx.errors[-1] for marker in ("Frontend production build failed", "Generated full-stack browser E2E failed")):
            current_frontend = ctx.artifacts.get("frontend/App.tsx", "")
            repaired_frontend = unwrap_generated_code(await self._call_nim(
                user_message=("Repair this React App.tsx from the exact production build or full-stack browser failure. "
                              "Use only React and browser APIs; preserve real GET and mutation calls, product "
                              "behavior, responsive Aurora Metal styling, and all runtime states. Return only "
                              f"the complete App.tsx.\n\nSOURCE:\n{current_frontend}\n\nBUILD FAILURE:\n{ctx.errors[-1]}"),
                system_prompt=FrontendAgent.SYSTEM_PROMPT, temperature=0.1, max_tokens=10000,
            ))
            try:
                design_json = json.loads(ctx.artifacts.get("design_tokens.json", "{}"))
            except json.JSONDecodeError:
                design_json = None
            frontend_violations = validate_frontend_contract(repaired_frontend, design_json)
            if frontend_violations:
                raise ValueError("Frontend production build repair failed validation: " + "; ".join(frontend_violations))
            ctx.set_artifact("frontend/App.tsx", repaired_frontend)

        if ctx.errors and "Generated backend import failed" in ctx.errors[-1]:
            repaired_backend = unwrap_generated_code(await self._call_nim(
                user_message=("Repair this FastAPI module from the exact import/startup failure. Preserve all "
                              "persistent CRUD, auth, CORS, validation, and /api/v1 routes. Use only dependencies "
                              "listed in backend/requirements.txt. Return only complete Python.\n\n"
                              f"SOURCE:\n{backend}\n\nIMPORT FAILURE:\n{ctx.errors[-1]}"),
                system_prompt=BackendAgent.SYSTEM_PROMPT, temperature=0.1, max_tokens=12000,
            ))
            backend_violations = validate_backend_contract(repaired_backend)
            if backend_violations:
                raise ValueError("Backend import repair failed validation: " + "; ".join(backend_violations))
            backend = repaired_backend
            ctx.set_artifact("backend/main.py", backend)
        if ctx.target in {"flutter", "react-native"} and ctx.errors and "Mobile build verification failed" in ctx.errors[-1]:
            entry = "mobile/lib/main.dart" if ctx.target == "flutter" else "mobile/app/index.tsx"
            repaired = unwrap_generated_code(await self._call_nim(
                user_message=(f"Repair this {ctx.target} entrypoint using the exact build failure. "
                              "Return only the complete runnable source file.\n\n"
                              f"CURRENT SOURCE:\n{ctx.artifacts.get(entry, '')}\n\nFAILURE:\n{ctx.errors[-1]}"),
                system_prompt=(f"You are an expert {ctx.target} mobile engineer. Repair the supplied "
                               "entrypoint from the exact compiler/test output. Preserve product behavior "
                               "and accessibility. Output source code only."), temperature=0.1, max_tokens=8000,
            ))
            ctx.set_artifact(entry, repaired)
        
        error_context = ""
        if ctx.errors and "Pytest execution failed" in ctx.errors[-1]:
            error_context = f"\n\nTEST EXECUTION FAILED. FIX THE TESTS OR BACKEND CODE:\n{ctx.errors[-1]}"
            failure = ctx.errors[-1].lower()
            test_import_failure = (
                "module 'main' has no attribute" in failure
                or "no module named 'main'" in failure
                or "import_module(\"main\")" in failure
                or "import_module('main')" in failure
            )
            if test_import_failure:
                # The application did not run. Regenerate tests with the
                # canonical package import instead of mutating healthy source.
                error_context += (
                    "\n\nPROJECT LAYOUT REQUIREMENT: the FastAPI module is "
                    "backend/main.py. Import it only as `from backend.main import ...`; "
                    "never use `import main`, `from main import`, or dynamic import_module('main')."
                )
            else:
                # A retry must repair the artifact that actually failed, not
                # merely emit a new superficial test file. The repaired module
                # is written back before tests are regenerated and rerun.
                repaired_backend = await self._call_nim(
                    user_message=(
                        "Repair this FastAPI backend after its generated smoke/API tests failed. "
                        "Return only complete runnable Python code. Preserve the requested "
                        "product behavior, fix the concrete failure, and keep validation and "
                        "authorization intact.\n\n"
                        f"CURRENT BACKEND:\n{backend}\n\n"
                        f"TEST FAILURE:\n{ctx.errors[-1]}"
                    ),
                    system_prompt=BackendAgent.SYSTEM_PROMPT,
                    temperature=0.1,
                    max_tokens=12000,
                )
                backend = unwrap_generated_code(repaired_backend)
                try:
                    ast.parse(backend)
                except SyntaxError as exc:
                    raise ValueError(f"Self-healing backend repair is invalid Python: {exc}") from exc
                ctx.set_artifact("backend/main.py", backend)

        if ctx.errors and "QA validation failed" in ctx.errors[-1]:
            error_context += f"\n\nPREVIOUS QA CONTRACT FAILURE TO FIX:\n{ctx.errors[-1]}"
        tests = await self._call_nim(
            user_message=(
                "Write complete executable pytest tests for this FastAPI backend using FastAPI "
                "TestClient or httpx. Include at least two tests: health/readiness and a real "
                "create/read primary journey. Never use assert True, mocks, or placeholder tests. "
                "The generated application module is backend/main.py: import it only as "
                "`from backend.main import ...`, never as bare `main`.\n\n"
                f"BACKEND:\n{backend[:10000]}{error_context}"
            ),
            temperature=0.2,
            max_tokens=5000,
        )
        tests = unwrap_generated_code(tests)
        qa_violations = validate_qa_contract(tests)
        if qa_violations:
            raise ValueError("QA validation failed: " + "; ".join(qa_violations))
        ctx.set_artifact("tests/test_backend.py", tests)
        
        # Execution Loop (The Moat)
        if ctx.project_dir:
            # Inference strictness and local execution isolation are separate
            # concerns. Never require Docker merely because live NIM is used.
            isolation = os.getenv("SANDBOX_ISOLATION", "auto")
            executor = SandboxExecutor(ctx.project_dir, isolation=isolation)
            success, output = await executor.run_pytest_async("tests/test_backend.py")
            if not success:
                raise ValueError(f"Pytest execution failed:\n{output}")

            verification: Dict[str, Any] = {"pytest": "passed", "isolation": "host"}
            project_root = Path(ctx.project_dir)
            python_executable = shutil.which("python") or shutil.which("python3")
            if python_executable:
                imported, import_output = await run_host_command(
                    [python_executable, "-c", "import backend.main; print('backend-import-ok')"],
                    project_root,
                    timeout=600,
                )
                verification["backend_import"] = "passed" if imported else "failed"
                if not imported:
                    raise ValueError(f"Generated backend import failed:\n{import_output}")

            frontend_root = project_root / "frontend"
            package_json = frontend_root / "package.json"
            verify_generated = os.getenv("VERIFY_GENERATED_BUILDS", "true").lower() in {"1", "true", "yes"}
            if ctx.target in {"web", "pwa"} and package_json.is_file() and verify_generated:
                npm = shutil.which("npm")
                if not npm:
                    raise ValueError("Frontend production build failed: npm is unavailable on the QA worker")
                installed, install_output = await run_host_command([npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"], frontend_root, timeout=600)
                if not installed:
                    raise ValueError(f"Frontend dependency installation failed:\n{install_output}")
                built, build_output = await run_host_command([npm, "run", "build"], frontend_root, timeout=600)
                verification["frontend_production_build"] = "passed" if built else "failed"
                if not built:
                    raise ValueError(f"Frontend production build failed:\n{build_output}")
                e2e_ok, e2e_output = await run_host_command([npm, "run", "e2e"], frontend_root, timeout=600)
                verification["fullstack_browser_e2e"] = "passed" if e2e_ok else "failed"
                if not e2e_ok:
                    raise ValueError(f"Generated full-stack browser E2E failed:\n{e2e_output}")
            ctx.set_artifact("BUILD_VERIFICATION.json", json.dumps(verification, indent=2))

        if ctx.target in {"flutter", "react-native"}:
            readiness = verify_mobile_build(ctx.project_dir, ctx.target, enabled=os.getenv("VERIFY_MOBILE_BUILDS", "true").lower() in {"1", "true", "yes"})
            ctx.set_artifact("BUILD_READINESS.json", readiness.json())
            if readiness.status == "build_failed":
                raise ValueError(f"Mobile build verification failed:\n{readiness.message}")
                
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.DEVOPS,
            content=tests,
        ))
        return ctx


class SeleniumQAAgent(BaseAgent):
    role = AgentRole.QA
    SYSTEM_PROMPT = (
        "You are an End-to-End Test Automation Engineer. "
        "Given the frontend React code and the backend API details, "
        "generate a complete Playwright/Selenium Python script to test the user flows visually and functionally. "
        "Output ONLY valid Python testing code."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.QA
        frontend = ctx.artifacts.get("frontend/App.tsx", "")
        
        error_context = ""
        if ctx.errors and "Selenium execution failed" in ctx.errors[-1]:
            error_context = f"\n\nTEST EXECUTION FAILED. FIX THE LOCATORS:\n{ctx.errors[-1]}"

        tests = await self._call_nim(
            user_message=f"Write a Playwright/Selenium test script for this React frontend:\n\n{frontend[:2000]}{error_context}",
            temperature=0.2,
            max_tokens=3000,
        )
        ctx.set_artifact("tests/test_e2e.py", tests)
        
        # Execute the Selenium E2E test script in the Sandbox
        if ctx.project_dir:
            isolation = os.getenv("SANDBOX_ISOLATION", "auto")
            executor = SandboxExecutor(ctx.project_dir, isolation=isolation)
            success, output = await executor.run_pytest_async("tests/test_e2e.py")
            if not success:
                raise ValueError(f"Selenium execution failed:\n{output}")
                
            if "playwright" not in tests and "selenium" not in tests.lower():
                raise ValueError("Selenium execution failed: Missing webdriver or playwright imports.")
                
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.DEVOPS,
            content="Selenium tests generated and structurally validated.",
        ))
        return ctx



class DevOpsAgent(BaseAgent):
    role = AgentRole.DEVOPS
    SYSTEM_PROMPT = (
        "You are a DevOps engineer. Given a complete project, produce a GitHub Actions CI/CD "
        "pipeline workflow YAML, a production Dockerfile, and a deployment checklist in Markdown. "
        "Output each as a separate artifact."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.DEPLOYING
        plan = ctx.artifacts.get("PLAN.md", "")
        
        # Generate CI/CD pipeline
        ci_cd = await self._call_nim(
            user_message=("Create a complete GitHub Actions CI workflow. It must check out source, "
                          "set up Python and Node, install backend and frontend dependencies, run "
                          "pytest, run npm run build, and retain useful failure logs.\n\n" + plan),
            temperature=0.2,
            max_tokens=3000,
        )
        ctx.set_artifact(".github/workflows/ci.yml", unwrap_generated_code(ci_cd))
        
        # Generate deployment checklist
        deployment_checklist = await self._call_nim(
            user_message=("Create a deployment checklist covering database migrations, secret "
                          "management, health checks, smoke tests, observability, backups, and an "
                          "explicit rollback procedure.\n\n" + plan),
            temperature=0.3,
            max_tokens=2000,
        )
        ctx.set_artifact("DEPLOYMENT_CHECKLIST.md", deployment_checklist)
        
        # Generate production docker-compose override
        docker_compose_prod = await self._call_nim(
            user_message=f"Create a docker-compose.prod.yml for production deployment:\n\n{plan}",
            temperature=0.2,
            max_tokens=2000,
        )
        ctx.set_artifact("docker-compose.prod.yml", unwrap_generated_code(docker_compose_prod))
        devops_violations = validate_devops_artifacts(ctx.artifacts)
        if devops_violations:
            raise ValueError("DevOps validation failed: " + "; ".join(devops_violations))

        if ctx.target in {"flutter", "react-native"} and "BUILD_READINESS.json" not in ctx.artifacts:
            ctx.set_artifact("BUILD_READINESS.json", verify_mobile_build(ctx.project_dir, ctx.target, enabled=False).json())
        
        ctx.status = PipelineStatus.COMPLETE
        ctx.completed_at = datetime.utcnow()
        ctx.add_message(AgentMessage(
            from_role=self.role,
            content="Deployment artifacts generated: CI/CD pipeline, deployment checklist, production docker-compose",
        ))
        return ctx


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

class AgentPipeline:
    """
    Orchestrates the sequential multi-agent pipeline for app generation.

    Usage:
        nim_client = NIMClient(NIMConfig(api_key="..."))
        pipeline = AgentPipeline(nim_client)
        ctx = await pipeline.run("Build a task management SaaS app")
        print(ctx.artifacts.keys())
    """

    def __init__(self, nim_client: NIMClient) -> None:
        self.nim = nim_client
        # Required chain includes preview materialization before QA.
        # opt-in use but is not part of the default contract.)
        self._agents: List[BaseAgent] = [
            PlannerAgent(nim_client),
            DesignerAgent(nim_client),
            FrontendAgent(nim_client),
            BackendAgent(nim_client),
            IntegrationAgent(nim_client),
            PreviewAgent(nim_client),
            QAAgent(nim_client),
            DevOpsAgent(nim_client),
        ]

    # EM-3: ONE retry policy shared by run() and stream_run(). Validation
    # failures (ValueError) are retryable up to MAX_AGENT_RETRIES with the
    # error fed back to the agent; any other exception fails the pipeline.
    MAX_AGENT_RETRIES = 3

    @staticmethod
    def _is_retryable_inference_error(error: Exception) -> bool:
        """Retry transient live-gateway failures while retaining fatal failures."""
        message = str(error).lower()
        return any(marker in message for marker in (
            "all configured omniroute routes failed",
            "omniroute fallback circuit is open",
            "timed out",
            "connecterror",
            "readerror",
        ))

    async def _run_agent_with_retry(
        self,
        agent: BaseAgent,
        ctx: PipelineContext,
        on_retry: Optional[Callable[[int, str, bool], Awaitable[None]]] = None,
    ) -> PipelineContext:
        errors_before = len(ctx.errors)
        for attempt in range(self.MAX_AGENT_RETRIES):
            try:
                result = await agent.run(ctx)
                if len(ctx.errors) > errors_before:
                    ctx.recoveries.extend(ctx.errors[errors_before:])
                    del ctx.errors[errors_before:]
                return result
            except ValueError as ve:
                if attempt == self.MAX_AGENT_RETRIES - 1:
                    recovered = agent.recover_validation_failure(ctx, ve)
                    if recovered is not None:
                        ctx.recoveries.extend([*ctx.errors[errors_before:], str(ve)])
                        del ctx.errors[errors_before:]
                        if on_retry:
                            await on_retry(attempt + 2, str(ve), True)
                        return recovered
                    ctx.fail(f"{agent.role.value} validation completely failed: {ve}")
                    return ctx
                ctx.errors.append(str(ve))
                if on_retry:
                    await on_retry(attempt + 2, str(ve), False)
            except Exception as exc:  # noqa: BLE001
                if self._is_retryable_inference_error(exc) and attempt < self.MAX_AGENT_RETRIES - 1:
                    ctx.errors.append(str(exc))
                    if on_retry:
                        await on_retry(attempt + 2, str(exc), False)
                    # OmniRoute opens its circuit after a total route failure.
                    # Wait through that window before reissuing an entire
                    # stage; an immediate retry can only fail locally.
                    backoff = float(os.getenv("INFERENCE_RETRY_BACKOFF_SECONDS", "35"))
                    if backoff > 0:
                        await asyncio.sleep(backoff)
                    continue
                ctx.fail(f"{agent.role.value} agent failed: {exc}")
                return ctx
        return ctx  # unreachable; keeps type-checkers happy

    async def run(self, user_prompt: str, project_dir: str = "") -> PipelineContext:
        """
        Execute the full multi-agent pipeline synchronously with execution loops.
        """
        ctx = PipelineContext(user_prompt=user_prompt, project_dir=project_dir)
        for agent in self._agents:
            if ctx.status == PipelineStatus.FAILED:
                break
            ctx = await self._run_agent_with_retry(agent, ctx)
        return ctx

    async def stream_run(
        self, user_prompt: str, project_dir: str = ""
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute the pipeline and yield real-time status events as dicts.

        Each yielded dict has keys: 'event', 'role', 'data'.

        EM-3: retry parity with run(). A retryable failure re-runs the SAME
        agent in place (resume-from-stage): agent_start is yielded once per
        stage, so SSE consumers never see duplicated events for a stage that
        eventually succeeds.
        """
        ctx = PipelineContext(user_prompt=user_prompt, project_dir=project_dir)
        for agent in self._agents:
            if ctx.status == PipelineStatus.FAILED:
                break
            yield {"event": "agent_start", "role": agent.role.value, "data": {}}
            retry_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

            async def report_retry(attempt: int, error: str, recovered: bool) -> None:
                await retry_queue.put({"event": "agent_retry", "role": agent.role.value, "data": {"attempt": attempt, "reason": error[:500], "recovered": recovered}})

            run_task = asyncio.create_task(self._run_agent_with_retry(agent, ctx, report_retry))
            while not run_task.done():
                get_retry = asyncio.create_task(retry_queue.get())
                done, _ = await asyncio.wait({run_task, get_retry}, return_when=asyncio.FIRST_COMPLETED)
                if get_retry in done:
                    yield get_retry.result()
                else:
                    get_retry.cancel()
            ctx = await run_task
            while not retry_queue.empty():
                yield retry_queue.get_nowait()
            if ctx.status == PipelineStatus.FAILED:
                yield {
                    "event": "agent_error",
                    "role": agent.role.value,
                    "data": {"error": ctx.errors[-1] if ctx.errors else "agent failed"},
                }
                break
            yield {
                "event": "agent_done",
                "role": agent.role.value,
                "data": {
                    "artifacts": list(ctx.artifacts.keys()),
                    "status": ctx.status.value,
                    "target": ctx.target,
                },
            }

        yield {
            "event": "pipeline_complete",
            "role": "orchestrator",
            "data": {
                "status": ctx.status.value,
                "artifacts": list(ctx.artifacts.keys()),
                "errors": ctx.errors,
                "recoveries": ctx.recoveries,
                "target": ctx.target,
            },
        }
