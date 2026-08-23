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
        plan = await self._call_nim(
            user_message=f"Plan a full-stack application for: {ctx.user_prompt}",
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
        "UI REQUIREMENT: You MUST implement a stunning, premium, modern user interface. "
        "Use 2026 state-of-the-art aesthetics (glassmorphism, dynamic micro-animations). "
        "Output ONLY a valid JSON object representing these design tokens."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.DESIGNING
        plan = ctx.artifacts.get("PLAN.md", "")
        
        error_context = ""
        if ctx.errors and "Designer validation" in ctx.errors[-1]:
            error_context = f"\n\nPREVIOUS ERROR TO FIX:\n{ctx.errors[-1]}"

        design = await self._call_nim(
            user_message=f"Design the UI tokens for this project:\n\n{plan}{error_context}",
            temperature=0.5,
            max_tokens=3000,
        )
        
        # Structural Validation
        try:
            design_json = json.loads(design.strip("` \n").removeprefix("json"))
            if "colors" not in design_json or "typography" not in design_json:
                raise ValueError("Designer validation failed: Missing required token categories.")
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
        "Apply glassmorphism effects, hover micro-animations, and pixel-perfect layouts. "
        "Output only valid, runnable code with no placeholders."
    )

    async def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.status = PipelineStatus.BUILDING_FRONTEND
        design = ctx.artifacts.get("design_tokens.json", "")
        plan = ctx.artifacts.get("PLAN.md", "")
        
        error_context = ""
        if ctx.errors and "Frontend validation" in ctx.errors[-1]:
            error_context = f"\n\nPREVIOUS ERROR TO FIX:\n{ctx.errors[-1]}"

        code = await self._call_nim(
            user_message=(
                f"Build the complete React frontend for:\n\nPLAN:\n{plan}\n\nDESIGN TOKENS:\n{design}{error_context}"
            ),
            temperature=0.2,
            max_tokens=6000,
        )
        
        # EM-4: structural design-token lint (replaces the old single-keyword
        # string-search gate).
        design_json: Optional[Dict[str, Any]] = None
        try:
            design_json = json.loads(design) if design else None
        except (json.JSONDecodeError, TypeError):
            design_json = None
        violations = lint_frontend_design_tokens(code, design_json)
        if violations:
            raise ValueError(
                "Frontend validation failed: design tokens not structurally applied -- "
                + "; ".join(violations)
            )

        ctx.set_artifact("frontend/App.tsx", code)
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.BACKEND,
            content=code,
            metadata={"artifact": "frontend/App.tsx"},
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
        code = await self._call_nim(
            user_message=f"Build the complete FastAPI backend for:\n\n{plan}",
            temperature=0.2,
            max_tokens=6000,
        )
        ctx.set_artifact("backend/main.py", code)
        ctx.add_message(AgentMessage(
            from_role=self.role,
            to_role=AgentRole.INTEGRATION,
            content=code,
            metadata={"artifact": "backend/main.py"},
        ))
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
        
        error_context = ""
        if ctx.errors and "Pytest execution failed" in ctx.errors[-1]:
            error_context = f"\n\nTEST EXECUTION FAILED. FIX THE TESTS OR BACKEND CODE:\n{ctx.errors[-1]}"

        tests = await self._call_nim(
            user_message=f"Write complete pytest tests for this FastAPI backend:\n\n{backend[:2000]}{error_context}",
            temperature=0.2,
            max_tokens=3000,
        )
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
        # 7-agent chain: Planning -> Design -> Frontend -> Backend ->
        # Integration -> QA -> DevOps. (SeleniumQAAgent remains defined for
        # opt-in use but is not part of the default contract.)
        self._agents: List[BaseAgent] = [
            PlannerAgent(nim_client),
            DesignerAgent(nim_client),
            FrontendAgent(nim_client),
            BackendAgent(nim_client),
            IntegrationAgent(nim_client),
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
                },
            }

        yield {
            "event": "pipeline_complete",
            "role": "orchestrator",
            "data": {
                "status": ctx.status.value,
                "artifacts": list(ctx.artifacts.keys()),
                "errors": ctx.errors,
            },
        }