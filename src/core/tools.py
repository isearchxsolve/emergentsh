"""
FileTools — file and shell tools for the autonomous agent.

All tools are sandboxed to the project directory.  ``run_command`` uses
``subprocess.Popen`` in a background thread so that stdout/stderr can be
streamed live to the UI's Execution Drawer via a callback.
"""

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional


class FileTools:
    """Sandboxed file/shell tool implementations."""

    def __init__(self, base: str):
        self.base: Path = Path(base).resolve()

    # ------------------------------------------------------------------
    def _safe(self, p: str) -> Path:
        """Resolve *p* relative to base and ensure it doesn't escape."""
        t = (self.base / p).resolve()
        try:
            t.relative_to(self.base)
        except ValueError:
            raise PermissionError(
                f"Path '{p}' escapes project directory ({self.base})"
            )
        return t

    # ------------------------------------------------------------------
    def read(self, path: str) -> str:
        try:
            t = self._safe(path)
            if not t.exists():
                return f"[ERR] File not found: {path}"
            with open(t, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"[ERR] {e}"

    def write(self, path: str, content: str) -> str:
        try:
            t = self._safe(path)
            t.parent.mkdir(parents=True, exist_ok=True)
            with open(t, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[OK] Written {len(content)} chars to {path}"
        except Exception as e:
            return f"[ERR] {e}"

    def search(self, pattern: str, path: str = ".") -> str:
        try:
            t = self._safe(path)
            rx = re.compile(pattern, re.IGNORECASE)
            matches: list[str] = []
            for root, dirs, files in os.walk(t):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in (".git", "__pycache__", ".venv", "node_modules")
                ]
                for fn in files:
                    if fn.endswith(
                        (".pyc", ".exe", ".dll", ".png", ".jpg", ".zip", ".tar")
                    ):
                        continue
                    fp = Path(root) / fn
                    try:
                        with open(
                            fp, "r", encoding="utf-8", errors="replace"
                        ) as f:
                            for i, line in enumerate(f, 1):
                                if rx.search(line):
                                    matches.append(
                                        f"{fp.relative_to(self.base)}:{i} {line.strip()}"
                                    )
                                    if len(matches) >= 50:
                                        break
                    except Exception:
                        pass
                    if len(matches) >= 50:
                        break
            return "\n".join(matches) if matches else f"No matches for '{pattern}'"
        except Exception as e:
            return f"[ERR] {e}"

    # ------------------------------------------------------------------
    def run_cmd(
        self,
        cmd: str,
        on_output: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Execute *cmd* in the project directory.

        If *on_output* is provided, each line of combined stdout/stderr is
        passed to it in real time (from a background thread).  The full
        output is also returned as a string.
        """
        try:
            p = subprocess.Popen(
                cmd,
                cwd=self.base,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                bufsize=1,
            )
            out: list[str] = []
            assert p.stdout is not None
            for line in p.stdout:
                out.append(line)
                if on_output:
                    on_output(line.rstrip("\n"))
            try:
                p.wait(timeout=120)
                return "".join(out) + f"\n[EXIT CODE: {p.returncode}]"
            except subprocess.TimeoutExpired:
                p.kill()
                return "\n[ERR: command exceeded 120s timeout and was killed]"
        except Exception as e:
            return f"[ERR] {e}"


# ──────────────────────────────────────────────────────────────────────
# Tool schema (OpenAI function-calling format)
# ──────────────────────────────────────────────────────────────────────
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create/overwrite file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Regex search in project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run shell command/tests.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def execute_tool(
    tools: FileTools,
    name: str,
    args: dict,
    on_output: Optional[Callable[[str], None]] = None,
) -> str:
    """Dispatch a tool call by name."""
    if name == "read_file":
        return tools.read(args.get("path", ""))
    if name == "write_file":
        return tools.write(args.get("path", ""), args.get("content", ""))
    if name == "search_files":
        return tools.search(args.get("pattern", ""), args.get("path", "."))
    if name == "run_command":
        return tools.run_cmd(args.get("command", ""), on_output=on_output)
    return f"[ERR] Unknown tool: {name}"
