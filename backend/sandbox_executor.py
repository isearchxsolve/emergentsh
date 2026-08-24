"""Sandbox executor for QA agents (EM-5: hardened Docker isolation).

Runs generated-project tests (pytest / Playwright) against generated code.
Shares the hardened-container design proven in neon_unified (GAP-NU-3):
when Docker is available, tests execute in a disposable container with no
network, a read-only rootfs, capped CPU/memory, and the project mounted at
/project. When Docker is unavailable, behaviour depends on `isolation`:

  - "auto"   (default): fall back to a host subprocess (legacy behaviour).
  - "docker": fail closed — never silently drop to the host.
  - "host":   explicit host execution.

The public contract is unchanged: run_pytest() returns (success, output).
"""
import os
import asyncio
import shutil
import subprocess
from typing import List, Optional, Tuple

DEFAULT_IMAGE = os.getenv("SANDBOX_IMAGE", "python:3.11-slim")
DEFAULT_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "600"))
DOCKER_IMAGE = os.getenv("SANDBOX_DOCKER_IMAGE", DEFAULT_IMAGE)


class SandboxExecutor:
    """Execution environment for QA agents to run tests against generated code."""

    def __init__(
        self,
        project_dir: str,
        isolation: str = "auto",
        image: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        if isolation not in ("auto", "docker", "host"):
            raise ValueError(f"Unknown isolation mode: {isolation!r}")
        self.project_dir = project_dir
        self.isolation = isolation
        self.image = image or DOCKER_IMAGE
        self.timeout = timeout or DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Path safety: the test target must stay inside the project directory.
    # ------------------------------------------------------------------
    def _resolve_target(self, test_file_relative_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Return (resolved_relative_path, error). Rejects escapes."""
        if not test_file_relative_path:
            return None, "Error: empty test path"
        if os.path.isabs(test_file_relative_path):
            return None, f"Error: absolute test path rejected: {test_file_relative_path}"
        normalized = os.path.normpath(test_file_relative_path)
        if normalized.startswith("..") or ".." + os.sep in normalized:
            return None, f"Error: path traversal rejected: {test_file_relative_path}"
        target_path = os.path.join(self.project_dir, normalized)
        if not os.path.exists(target_path):
            return None, f"Error: Test path does not exist: {target_path}"
        return normalized, None

    # ------------------------------------------------------------------
    # Docker availability (shared detection pattern with neon_unified NU-3)
    # ------------------------------------------------------------------
    @staticmethod
    def _docker() -> Tuple[Optional[str], bool]:
        """Return (docker_cli_path, daemon_up)."""
        docker = shutil.which("docker")
        if not docker:
            return None, False
        try:
            chk = subprocess.run(
                [docker, "info"], capture_output=True, text=True, timeout=15
            )
            return docker, chk.returncode == 0
        except Exception:
            return docker, False

    def _docker_command(self, docker: str, target: str) -> List[str]:
        """Hardened container invocation: no network, read-only rootfs,
        tmpfs scratch space, capped CPU/memory, project mounted read-write
        at /project, constant command strings only."""
        return [
            docker, "run", "--rm",
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp",
            "--cpus", "1.0",
            "--memory", "512m",
            "--workdir", "/project",
            "-v", f"{self.project_dir}:/project",
            self.image,
            "pytest", target, "-v",
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_pytest(self, test_file_relative_path: str = "tests/") -> Tuple[bool, str]:
        """Execute pytest on the given project-relative path.

        Returns (success, output). Success means the runner executed AND
        pytest exited 0. A runner that cannot execute (blocked isolation,
        timeout, missing path) is a failure — never a silent pass.
        """
        target, err = self._resolve_target(test_file_relative_path)
        if err:
            return False, err

        if self.isolation in ("auto", "docker"):
            docker, daemon_up = self._docker()
            if docker and daemon_up:
                return self._run_docker(docker, target)
            if self.isolation == "docker":
                return False, (
                    "BLOCKED: isolation=docker but the Docker daemon is not "
                    "reachable. Start Docker or set isolation=host explicitly. "
                    "Refusing to silently fall back to host execution."
                )
            # auto: fall through to host

        return self._run_host(target)

    async def run_pytest_async(self, test_file_relative_path: str = "tests/") -> Tuple[bool, str]:
        """Run the blocking runner in a worker thread."""
        return await asyncio.to_thread(self.run_pytest, test_file_relative_path)

    def _run_docker(self, docker: str, target: str) -> Tuple[bool, str]:
        cmd = self._docker_command(docker, target)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
            output = result.stdout or ""
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Error: sandboxed pytest timed out after {self.timeout}s."
        except Exception as e:
            return False, f"Error executing sandboxed pytest: {e}"

    def _run_host(self, target: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                ["pytest", os.path.join(self.project_dir, target), "-v"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Error: Pytest execution timed out after {self.timeout} seconds."
        except Exception as e:
            return False, f"Error executing pytest: {e}"
