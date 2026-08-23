"""
Agent Pipeline — Orchestrates multi-agent task execution for Emergent.sh clone.

This module defines the AgentPipeline class which coordinates the lifecycle of
a user-initiated app generation request through the full agent chain:
  Planning → Design → Frontend → Backend → Integration → QA → DevOps

All inference calls route exclusively through NVIDIA NIM endpoints.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
import ast
import re
import json

from .nim_client import NIMClient, NIMConfig
from .sandbox_executor import SandboxExecutor
from .mobile_targets import detect_target, scaffold_for, verify_mobile_build


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
    """Abstract base for all pipeline agents using NVIDIA NIM inference."""

    SYSTEM_PROMPT: str = "You are a helpful AI assistant."
    role: AgentRole = AgentRole.PLANNER

    def __init__(self, nim_client: NIMClient) -> None:
        self.nim = nim_client

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        raise NotImplementedError

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
            model=model,
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
            model=model,
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


def unwrap_generated_code(raw_output: str) -> str:
    """Extract model-generated code from a Markdown fence when present."""
    output = raw_output.strip()
    fenced = re.search(r"```[^\n]*\n(.*?)\n?```", output, re.DOTALL)
    return fenced.group(1).strip() if fenced else output


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
        "detailed project plan in Markdown with: Overview, Tech Stack, Features list, "
        "API Endpoints, Database Schema outline, and Milestones. Be specific and thorough."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.PLANNING
        ctx.target = detect_target(ctx.user_prompt)
        plan = await self._call_nim(
            user_message=(
                "Plan a full-stack application for the user's product idea below. "
                "Apply the mandatory product baseline without asking the user to repeat it.\n\n"
                f"PRODUCT BASELINE:\n{DEFAULT_PRODUCT_BASELINE}\n\n"
                f"VISUAL QUALITY BASELINE:\n{DEFAULT_VISUAL_QUALITY_BASELINE}\n\n"
                f"DELIVERY TARGET: {ctx.target}\n"
                "Plan for this exact platform and its deployment requirements.\n\n"
                f"USER PRODUCT IDEA:\n{ctx.user_prompt}"
            ),
            temperature=0.3,
            max_tokens=3000,
        )
        
        plan_lower = plan.lower()
        if "cannot fulfill" in plan_lower or "unable to" in plan_lower or "safety" in plan_lower or "violate" in plan_lower:
             raise ValueError("NVIDIA AI Safety Filter Triggered: The upstream model refused to generate a plan for this prompt due to safety guidelines. Please try a different prompt.")
             
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
        
        # Normalize harmless model presentation/schema variants at the
        # inference boundary before downstream agents consume the artifact.
        try:
            design_json = parse_design_tokens(design)
        except json.JSONDecodeError:
            design_lower = design.lower()
            if "cannot fulfill" in design_lower or "unable to" in design_lower or "safety" in design_lower or "violate" in design_lower:
                raise ValueError("NVIDIA AI Safety Filter Triggered: The upstream model refused to generate content for this prompt due to safety guidelines. Please try a different prompt.")
            raise ValueError(f"Designer validation failed: Output must be valid JSON. (Got: {design[:50]}...)")

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


class FrontendAgent(BaseAgent):
    role = AgentRole.FRONTEND
    SYSTEM_PROMPT = (
        "You are an expert React/TypeScript frontend engineer. Given a design spec, "
        "generate complete, production-ready React component code using Tailwind CSS. "
        "You MUST ensure the UI exactly matches the premium design tokens provided. "
        "Apply the supplied Aurora Metal quality baseline, all responsive breakpoints, "
        "accessible interaction states, and polished loading/empty/error states. "
        "Output only valid, runnable code with no placeholders."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.BUILDING_FRONTEND
        design = ctx.artifacts.get("design_tokens.json", "")
        plan = ctx.artifacts.get("PLAN.md", "")
        
        error_context = ""
        if ctx.errors and "Frontend validation" in ctx.errors[-1]:
            error_context = f"\n\nPREVIOUS ERROR TO FIX:\n{ctx.errors[-1]}"

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
            request = "Build the complete React frontend."
        code = await self._call_nim(
            user_message=(
                f"{request}\n\nPLAN:\n{plan}\n\n"
                f"DESIGN TOKENS:\n{design}\n\nVISUAL QUALITY BASELINE:\n"
                f"{DEFAULT_VISUAL_QUALITY_BASELINE}{error_context}"
            ),
            temperature=0.2,
            max_tokens=6000,
        )
        code = unwrap_generated_code(code)
        
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
          violations = lint_frontend_design_tokens(code, design_json)
          if violations:
              raise ValueError("Frontend validation failed: design tokens not structurally applied -- " + "; ".join(violations))
          artifact_name = "frontend/App.tsx"

        ctx.set_artifact(artifact_name, code)
        for name, content in scaffold_for(ctx.target, "Emergent App").items():
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
            user_message=f"Build the complete FastAPI backend for:\n\n{plan}{repair_context}",
            temperature=0.2,
            max_tokens=12000,
        )
        code = unwrap_generated_code(code)
        try:
            ast.parse(code)
        except SyntaxError as exc:
            # Preserve the exact failed attempt for the next repair pass
            # without writing unvalidated code into the project workspace.
            ctx.artifacts["_backend_last_attempt.py"] = code
            raise ValueError(f"Backend validation failed: generated Python is invalid: {exc}") from exc
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
            user_message=f"TARGET: {ctx.target}\nPLAN:\n{ctx.artifacts.get('PLAN.md','')}\nDESIGN:\n{ctx.artifacts.get('design_tokens.json','')}",
            temperature=0.2, max_tokens=6000,
        ))
        if "<!doctype html" not in html.lower() or "<script" not in html.lower() or "<style" not in html.lower():
            raise ValueError("Preview validation failed: expected self-contained interactive HTML")
        if re.search(r"(?:src|href)=[\"']https?://", html, re.I):
            raise ValueError("Preview validation failed: remote preview dependency is not allowed")
        ctx.set_artifact("index.html", html)
        mode = "mobile_simulation" if ctx.target in {"flutter", "react-native"} else "interactive_web"
        ctx.set_artifact("PREVIEW_MODE.json", json.dumps({"mode": mode, "target": ctx.target, "native_runtime": False if mode == "mobile_simulation" else None}, indent=2))
        ctx.add_message(AgentMessage(from_role=self.role, to_role=AgentRole.QA, content="Interactive preview generated.", metadata={"artifact": "index.html", "mode": mode}))
        return ctx


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
        
        # Generate docker-compose.yml
        docker_compose = await self._call_nim(
            user_message=(
                f"Generate a complete docker-compose.yml for this project:\n\n"
                f"PLAN:\n{plan[:2000]}\n\n"
                f"FRONTEND (React/Next.js):\n{frontend[:1000]}\n\n"
                f"BACKEND (FastAPI):\n{backend[:1000]}"
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
                f"PLAN:\n{plan[:2000]}"
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
            # A retry must repair the artifact that failed, not merely ask QA
            # to emit a different test file.  The repaired module is written
            # back into the shared context before tests are regenerated and
            # rerun below.
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

        tests = await self._call_nim(
            user_message=(
                "Write complete pytest tests for this FastAPI backend. Include a small "
                "smoke test for the primary health/readiness path and API tests for the "
                "main user journey.\n\n"
                f"BACKEND:\n{backend[:4000]}{error_context}"
            ),
            temperature=0.2,
            max_tokens=3000,
        )
        tests = unwrap_generated_code(tests)
        try:
            ast.parse(tests)
        except SyntaxError as exc:
            raise ValueError(f"QA validation failed: generated tests are invalid Python: {exc}") from exc
        ctx.set_artifact("tests/test_backend.py", tests)
        
        # Execution Loop (The Moat)
        if ctx.project_dir:
            isolation = os.getenv("SANDBOX_ISOLATION") or (
                "docker" if os.getenv("NIM_STRICT_MODE", "false").lower() in ("true", "1") else "auto"
            )
            executor = SandboxExecutor(ctx.project_dir, isolation=isolation)
            success, output = await executor.run_pytest_async("tests/test_backend.py")
            if not success:
                raise ValueError(f"Pytest execution failed:\n{output}")

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
            isolation = os.getenv("SANDBOX_ISOLATION") or (
                "docker" if os.getenv("NIM_STRICT_MODE", "false").lower() in ("true", "1") else "auto"
            )
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
            user_message=f"Create a complete GitHub Actions CI/CD pipeline for:\n\n{plan}",
            temperature=0.2,
            max_tokens=3000,
        )
        ctx.set_artifact(".github/workflows/ci.yml", ci_cd)
        
        # Generate deployment checklist
        deployment_checklist = await self._call_nim(
            user_message=f"Create a deployment checklist in Markdown for:\n\n{plan}",
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
        ctx.set_artifact("docker-compose.prod.yml", docker_compose_prod)

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

    async def _run_agent_with_retry(self, agent: BaseAgent, ctx: PipelineContext) -> PipelineContext:
        for attempt in range(self.MAX_AGENT_RETRIES):
            try:
                return await agent.run(ctx)
            except ValueError as ve:
                if attempt == self.MAX_AGENT_RETRIES - 1:
                    ctx.fail(f"{agent.role.value} validation completely failed: {ve}")
                    return ctx
                ctx.errors.append(str(ve))
            except Exception as exc:  # noqa: BLE001
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
            ctx = await self._run_agent_with_retry(agent, ctx)
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
                "target": ctx.target,
            },
        }
