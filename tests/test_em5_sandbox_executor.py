"""EM-5 regression tests: hardened Docker sandbox for sandbox_executor.

Guards the audit gap: QA-agent tests used to run as a bare host subprocess
with no isolation. The executor now shares neon_unified's NU-3 hardened
container design (--network none, --read-only, tmpfs, CPU/memory caps) and
fails CLOSED when isolation=docker is requested but the daemon is down.

Acceptance from the remediation prompt: escape-attempt tests are blocked.
"""
import pytest

from backend.sandbox_executor import SandboxExecutor


@pytest.fixture
def project(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    return tmp_path


class TestEscapeAttemptsBlocked:
    def test_path_traversal_rejected(self, project):
        ex = SandboxExecutor(str(project), isolation="host")
        ok, out = ex.run_pytest("../../etc/passwd")
        assert ok is False
        assert "traversal" in out.lower()

    def test_nested_traversal_rejected(self, project):
        ex = SandboxExecutor(str(project), isolation="host")
        ok, out = ex.run_pytest("tests/../../secrets")
        assert ok is False
        assert "traversal" in out.lower()

    def test_absolute_path_rejected(self, project):
        ex = SandboxExecutor(str(project), isolation="host")
        ok, out = ex.run_pytest("C:/Windows/System32")
        assert ok is False
        assert "absolute" in out.lower()

    def test_shell_metachar_path_is_never_interpreted(self, project, monkeypatch):
        """Commands are constant string lists, never shell strings."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

            class R:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return R()

        monkeypatch.setattr("backend.sandbox_executor.subprocess.run", fake_run)
        ex = SandboxExecutor(str(project), isolation="host")
        # The path does not exist, so it must be rejected before any exec;
        # but even for a valid path the exec must be a list, not a shell.
        ok, _ = ex.run_pytest("tests; rm -rf /")
        assert ok is False  # nonexistent path -> blocked, nothing executed
        assert "cmd" not in captured, "no subprocess may run for a bogus path"

        ok, _ = ex.run_pytest("tests/")
        assert ok is True
        assert isinstance(captured["cmd"], list)
        assert captured["kwargs"].get("shell") in (None, False)

    def test_missing_target_blocked_not_passed(self, project):
        ex = SandboxExecutor(str(project), isolation="host")
        ok, out = ex.run_pytest("tests/nonexistent_dir")
        assert ok is False
        assert "does not exist" in out


class TestHardenedDockerCommand:
    def test_container_flags_are_hardened(self, project):
        ex = SandboxExecutor(str(project), isolation="docker")
        cmd = ex._docker_command("/usr/bin/docker", "tests/")
        joined = " ".join(cmd)
        assert "--network none" in joined
        assert "--read-only" in joined
        assert "--tmpfs /tmp" in joined
        assert "--cpus 1.0" in joined
        assert "--memory 512m" in joined
        assert f"-v {project}:/project" in joined
        assert "--workdir /project" in joined
        assert cmd[-3:] == ["pytest", "tests/", "-v"]

    def test_invalid_isolation_mode_rejected(self, project):
        with pytest.raises(ValueError):
            SandboxExecutor(str(project), isolation="yolo")


class TestFailClosedSemantics:
    def test_docker_mode_fails_closed_when_daemon_down(self, project, monkeypatch):
        monkeypatch.setattr(SandboxExecutor, "_docker", staticmethod(lambda: (None, False)))
        ex = SandboxExecutor(str(project), isolation="docker")
        ok, out = ex.run_pytest("tests/")
        assert ok is False
        assert "BLOCKED" in out
        assert "host" in out.lower(), "must name the refused fallback explicitly"

    def test_auto_mode_falls_back_to_host_when_daemon_down(self, project, monkeypatch):
        monkeypatch.setattr(SandboxExecutor, "_docker", staticmethod(lambda: (None, False)))
        called = {}

        def fake_host(self, target):
            called["target"] = target
            return True, "host ran"

        monkeypatch.setattr(SandboxExecutor, "_run_host", fake_host)
        ex = SandboxExecutor(str(project), isolation="auto")
        ok, out = ex.run_pytest("tests/")
        assert ok is True and out == "host ran"
        assert called["target"] == "tests"

    def test_docker_mode_uses_container_when_daemon_up(self, project, monkeypatch):
        monkeypatch.setattr(
            SandboxExecutor, "_docker", staticmethod(lambda: ("/usr/bin/docker", True))
        )
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd

            class R:
                returncode = 0
                stdout = "1 passed"
                stderr = ""

            return R()

        monkeypatch.setattr("backend.sandbox_executor.subprocess.run", fake_run)
        ex = SandboxExecutor(str(project), isolation="auto")
        ok, out = ex.run_pytest("tests/")
        assert ok is True
        assert captured["cmd"][0] == "/usr/bin/docker"
        assert "run" in captured["cmd"]

    def test_docker_failure_is_not_a_silent_pass(self, project, monkeypatch):
        monkeypatch.setattr(
            SandboxExecutor, "_docker", staticmethod(lambda: ("/usr/bin/docker", True))
        )

        def fake_run(cmd, **kwargs):
            class R:
                returncode = 1
                stdout = ""
                stderr = "pytest: command not found"

            return R()

        monkeypatch.setattr("backend.sandbox_executor.subprocess.run", fake_run)
        ex = SandboxExecutor(str(project), isolation="docker")
        ok, out = ex.run_pytest("tests/")
        assert ok is False
        assert "command not found" in out
