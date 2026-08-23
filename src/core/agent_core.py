"""
NIMAgentCore — the agentic inference loop, fully decoupled from the UI.

This class is *headless*: it knows nothing about Qt widgets.  It accepts
an :class:`~src.core.signals.AgentSignals` instance and emits signals at
every meaningful event.  The UI layer listens to those signals.

Key features ported from the CLI:
  * NVIDIA NIM / OpenRouter provider pool with failover
  * Token-bucket RPM enforcement
  * 10 % context compaction
  * Auto-Correction Interceptor for XML hallucinations
  * Mid-stream overload protection + auto-retry
  * Chatty-Stop Auto-Nudge
  * Silent stream-truncation detection
"""

import json
import re
import time
from typing import Dict, List, Optional, Any, Set

from .providers import ProviderPool, build_provider_pool
from .rate_limiter import TokenMeter
from .signals import AgentSignals
from .tools import TOOLS_SCHEMA, FileTools, execute_tool
from .handoff import HANDOFF_TOOL_SCHEMA

# Overload / rate-limit error signatures (lower-cased, space-stripped)
_OVERLOAD_SIGNATURES = [
    "429",
    "toomanyrequests",
    "ratelimit",
    "resourceexhausted",
    "workerlocaltotalrequestlimit",
    "overloaded",
    "503",
    "502",
    "500",
    "504",
]

_ACTION_PHRASES = [
    "let me",
    "i will",
    "i need to",
    "i'm going to",
    "allow me to",
    "i should",
    "here is the plan",
]

_XML_HALLUCINATION_RE = re.compile(r"<(tool_call|function|parameter)")


class NIMAgentCore:
    """
    Headless agentic loop.

    Parameters
    ----------
    profile : dict
        Profile dict from ConfigManager (contains ``key``, ``models``,
        ``default_model``, ``rpm``, ``name``).
    project_dir : str
        Working directory for file/shell tools.
    signals : AgentSignals
        Qt signal object to emit events through.
    """

    MAX_ROUNDS = 100
    MAX_OVERLOAD_RETRIES = 20
    MAX_NUDGES = 3
    COMPACT_THRESHOLD = 0.10
    MAX_TOKENS = 32768
    TEMPERATURE = 0.2

    def __init__(
        self,
        profile: Dict,
        project_dir: str,
        signals: AgentSignals,
    ):
        self.profile: Dict = profile
        self.pdir: str = project_dir
        self.signals: AgentSignals = signals
        self.tools: FileTools = FileTools(project_dir)
        self.pool: ProviderPool = build_provider_pool(profile)
        self.messages: List[Dict] = []
        self.goal: Optional[str] = None
        self.meter: TokenMeter = TokenMeter()
        self.compaction_summary: Optional[str] = None
        self._stop_requested: bool = False

        # Role-specific configuration (set by AgentFactory)
        self._role: Optional[str] = None
        self._role_profile = None
        self._filtered_tools_schema: List[Dict] = TOOLS_SCHEMA
        self._role_temperature: float = self.TEMPERATURE
        self._role_max_tokens: int = self.MAX_TOKENS
        self._role_model_key: str = "glm"
        self._extra_system_prompt: str = ""

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def load_session(self) -> None:
        """Attempt to restore a saved session for this profile+dir."""
        from .config import ConfigManager

        s = ConfigManager.load_session(self.profile["name"], self.pdir)
        if s:
            self.messages = s.get("messages", [])
            self.goal = s.get("goal")
            self.compaction_summary = s.get("compaction_summary")
            self.signals.status_info.emit("Session restored.")

    def save(self) -> None:
        from .config import ConfigManager

        ConfigManager.save_session(
            self.profile["name"],
            self.pdir,
            self.messages,
            self.goal,
            self.compaction_summary,
        )

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------
    def _rebuild_system(self) -> None:
        parts = [
            "You are an expert autonomous developer. "
            "Use tools proactively to achieve the goal.",
            "CRITICAL: You MUST use the native JSON function calling API "
            "to execute tools.",
            "CRITICAL: If you intend to use a tool, you MUST use it "
            "immediately in the exact same response. "
            "DO NOT announce your intentions and stop. "
            "DO NOT wait for user permission.",
            "NEVER output raw XML or markdown blocks (like <tool_call>) "
            "under any circumstances.",
        ]
        if self.goal:
            parts.append(f"CURRENT GOAL: {self.goal}")
        parts.append(f"Working Directory: {self.pdir}")

        # Add role-specific system prompt suffix
        if hasattr(self, "_role_profile") and self._role_profile:
            suffix = getattr(self._role_profile, "system_prompt_suffix", "")
            if suffix:
                parts.append(suffix)

        # Add extra system prompt (injected by factory)
        if self._extra_system_prompt:
            parts.append(self._extra_system_prompt)

        self.messages = [m for m in self.messages if m.get("role") != "system"]
        self.messages.insert(
            0, {"role": "system", "content": "\n".join(parts)}
        )
        if self.compaction_summary:
            if not any(
                self.compaction_summary in (m.get("content") or "")
                for m in self.messages
            ):
                self.messages.insert(
                    1,
                    {
                        "role": "user",
                        "content": (
                            f"[PRIOR CONTEXT SUMMARY]\n"
                            f"{self.compaction_summary}\n\n"
                            "You are mid-task. Do not ask for permission. "
                            "Execute the next required tool immediately."
                        ),
                    },
                )
                self.messages.insert(
                    2,
                    {
                        "role": "assistant",
                        "content": (
                            "Context acknowledged. I will execute the "
                            "next tool directly."
                        ),
                    },
                )

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------
    def est_tokens(self) -> int:
        return sum(
            max(1, len(str(m.get("content", ""))) // 4)
            for m in self.messages
        )

    def maybe_compact(self) -> None:
        ctx_size = self.est_tokens()
        if ctx_size < 128000 * self.COMPACT_THRESHOLD:
            return
        sys_msgs = [m for m in self.messages if m.get("role") == "system"]
        rest = [m for m in self.messages if m.get("role") != "system"]
        if len(rest) <= 8:
            return

        old, recent = rest[:-8], rest[-8:]
        lines: list[str] = []
        for m in old:
            c = str(m.get("content", ""))[:150].replace("\n", " ")
            lines.append(f"- {m.get('role')}: {c}")

        self.compaction_summary = (
            f"Folded {len(old)} messages.\n" + "\n".join(lines[-40:])
        )
        self.messages = sys_msgs + recent
        self._rebuild_system()
        new_ctx = self.est_tokens()
        self.signals.context_compacted.emit(ctx_size, new_ctx)

    # ------------------------------------------------------------------
    # Stop control
    # ------------------------------------------------------------------
    def request_stop(self) -> None:
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Main agentic loop
    # ------------------------------------------------------------------
    def run(self, prompt: str) -> None:
        """
        Run the agentic loop for a single user prompt.

        Emits signals throughout.  Returns when the loop completes,
        the agent produces a final non-tool response, or an error occurs.
        """
        self._stop_requested = False

        if prompt:
            self.messages.append({"role": "user", "content": prompt})

        rnd = 0
        retries = 0
        nudges = 0

        while rnd < self.MAX_ROUNDS:
            if self._stop_requested:
                self.signals.status_info.emit("Agent stopped by user.")
                break

            self.maybe_compact()
            ctx = self.est_tokens()
            self.signals.round_started.emit(rnd + 1, ctx)

            payload = {
                "messages": [
                    {k: v for k, v in m.items() if not k.startswith("_")}
                    for m in self.messages
                ],
                "max_tokens": self._role_max_tokens,
                "temperature": self._role_temperature,
                "stream": True,
                "tools": self._filtered_tools_schema + [HANDOFF_TOOL_SCHEMA],
                "tool_choice": "auto",
            }

            full_content = ""
            full_reason = ""
            tcalls: list[dict] = []
            provider = None
            overloaded = False

            # ── Provider selection + streaming ──────────────────────
            try:
                for _ in range(5):
                    provider = self.pool.next_available()
                    if not provider:
                        wt = self.pool.wait_time()
                        self.signals.status_warning.emit(
                            f"Waiting {wt:.1f}s for rate limits..."
                        )
                        time.sleep(wt)
                        continue

                    with provider.bucket.lock:
                        wt = provider.bucket._wait_time()
                    if wt > 0.5:
                        self.signals.status_info.emit(
                            f"Pacing rate limit (~{wt:.1f}s)..."
                        )
                    if not provider.bucket.reserve(60):
                        self.pool.rotate()
                        continue

                    self.signals.provider_info.emit(
                        provider.name, provider.model_id
                    )
                    self.signals.status_info.emit(
                        f"Awaiting {provider.name} (TTFT)..."
                    )

                    # Use role-specific model if available
                    model_key = getattr(self, "_role_model_key", "glm")
                    model_entry = self.profile["models"].get(model_key)
                    if model_entry:
                        payload["model"] = model_entry["id"]
                    else:
                        payload["model"] = provider.model_id

                    # Enable thinking for GLM models
                    current_model = payload["model"]
                    if "glm" in current_model:
                        payload["extra_body"] = {
                            "chat_template_kwargs": {
                                "enable_thinking": True,
                                "thinking_effort": "medium",
                            }
                        }
                    else:
                        payload.pop("extra_body", None)

                    resp = provider.client.chat.completions.create(**payload)
                    in_think = False
                    finish_reason: Optional[str] = None

                    for chunk in resp:
                        if self._stop_requested:
                            break

                        if chunk.choices and len(chunk.choices) > 0:
                            choice = chunk.choices[0]
                            if choice.finish_reason is not None:
                                finish_reason = choice.finish_reason
                            delta = choice.delta
                        else:
                            continue

                        # Reasoning content (thinking)
                        if (
                            hasattr(delta, "reasoning_content")
                            and delta.reasoning_content
                        ):
                            if not in_think:
                                in_think = True
                            self.signals.token_reasoning.emit(
                                delta.reasoning_content
                            )
                            full_reason += delta.reasoning_content

                        # Regular content
                        if delta.content:
                            if in_think:
                                in_think = False
                            self.signals.token_content.emit(delta.content)
                            full_content += delta.content

                        # Tool calls
                        if delta.tool_calls:
                            if in_think:
                                in_think = False
                            for tc in delta.tool_calls:
                                idx = tc.index
                                while len(tcalls) <= idx:
                                    tcalls.append(
                                        {"id": "", "name": "", "args": ""}
                                    )
                                if tc.id:
                                    tcalls[idx]["id"] += tc.id
                                if tc.function:
                                    if tc.function.name:
                                        tcalls[idx]["name"] += tc.function.name
                                        self.signals.tool_start.emit(
                                            tcalls[idx]["name"]
                                        )
                                    if tc.function.arguments:
                                        tcalls[idx]["args"] += (
                                            tc.function.arguments
                                        )

                    if self._stop_requested:
                        break

                    if finish_reason is None:
                        raise Exception(
                            "502 Server Overload: Connection silently "
                            "dropped by provider before completion."
                        )
                    break

                if provider:
                    provider.record_success()

            except Exception as e:
                err_str = str(e).lower().replace(" ", "")
                if any(
                    sig in err_str for sig in _OVERLOAD_SIGNATURES
                ):
                    self.signals.status_warning.emit(
                        "Server overload — connection dropped mid-stream."
                    )
                    self.signals.status_info.emit("Retrying round...")
                    if provider:
                        provider.record_rejection()
                    self.pool.rotate()
                    time.sleep(3.0)
                    overloaded = True
                else:
                    self.signals.error.emit(f"API error: {e}")
                    return

            if self._stop_requested:
                break

            if overloaded:
                retries += 1
                if retries > self.MAX_OVERLOAD_RETRIES:
                    self.signals.error.emit(
                        "Too many overload retries — aborting."
                    )
                    return
                continue
            retries = 0

            self.meter.record(ctx, len(full_content) // 4)

            # ── Auto-Correction Interceptor ────────────────────────
            if not tcalls and _XML_HALLUCINATION_RE.search(full_content):
                self.signals.auto_corrected.emit(
                    "Detected raw XML hallucination. Auto-correcting..."
                )
                self.messages.append(
                    {"role": "assistant", "content": full_content}
                )
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "SYSTEM ERROR: You just output raw XML tags "
                            "for a tool call. This is strictly forbidden. "
                            "You MUST use the native JSON function calling "
                            "API to execute tools. Please re-issue your "
                            "command correctly."
                        ),
                    }
                )
                self.save()
                time.sleep(2.0)
                continue

            # ── Tool execution ─────────────────────────────────────
            if tcalls:
                nudges = 0
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": full_content or None,
                        "tool_calls": [
                            {
                                "id": t["id"],
                                "type": "function",
                                "function": {
                                    "name": t["name"],
                                    "arguments": t["args"],
                                },
                            }
                            for t in tcalls
                        ],
                    }
                )

                for t in tcalls:
                    name = t["name"]
                    try:
                        args = json.loads(t["args"])
                    except Exception:
                        args = {}

                    args_str = json.dumps(args, ensure_ascii=False)
                    self.signals.tool_executing.emit(name, args_str)

                    # Live output callback for run_command
                    def _on_output(line: str, _name=name) -> None:
                        self.signals.tool_output.emit(line)

                    res = execute_tool(
                        self.tools, name, args, on_output=_on_output
                    )
                    self.signals.tool_result.emit(name, res)

                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": t["id"],
                            "name": name,
                            "content": res[
                                : max(2000, 128000 - ctx) * 4
                            ],
                        }
                    )

                self.save()
                time.sleep(3.0)
                rnd += 1
            else:
                # No tool calls — final response
                self.messages.append(
                    {"role": "assistant", "content": full_content}
                )
                self.signals.response_finished.emit(full_content)

                # Chatty-Stop Auto-Nudge
                is_chatty_promise = (
                    len(full_content) < 800
                    and any(
                        p in full_content.lower() for p in _ACTION_PHRASES
                    )
                )
                if is_chatty_promise and nudges < self.MAX_NUDGES:
                    self.signals.auto_nudged.emit(
                        "Agent paused without calling a tool. Auto-nudging..."
                    )
                    self.messages.append(
                        {
                            "role": "user",
                            "content": "Please proceed and execute the tool "
                            "you just mentioned.",
                        }
                    )
                    nudges += 1
                    time.sleep(2.0)
                    continue

                self.save()
                break

        self.signals.agent_finished.emit()
