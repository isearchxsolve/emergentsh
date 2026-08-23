"""
Tests for the self-debugging loop module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.core.self_debug import (
    SelfDebugConfig,
    SelfDebugLoop,
    ErrorAnalyzer,
    FixGenerator,
    TestResult,
    DebugIteration,
    DebugState,
    run_self_debug,
)


class TestSelfDebugConfig:
    """Test SelfDebugConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SelfDebugConfig()
        assert config.max_iterations == 5
        assert config.test_command == ["python", "-m", "pytest", "tests/", "-v"]
        assert config.test_timeout == 120
        assert config.auto_apply_fixes is False
        assert config.working_directory is None
        assert config.target_files == []

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SelfDebugConfig(
            max_iterations=3,
            test_command=["pytest", "tests/"],
            test_timeout=60,
            auto_apply_fixes=True,
            working_directory=Path("/tmp/test"),
            target_files=["src/main.py"],
        )
        assert config.max_iterations == 3
        assert config.test_command == ["pytest", "tests/"]
        assert config.test_timeout == 60
        assert config.auto_apply_fixes is True
        assert config.working_directory == Path("/tmp/test")
        assert config.target_files == ["src/main.py"]


class TestTestResult:
    """Test TestResult dataclass."""

    def test_test_result_creation(self):
        """Test TestResult creation with defaults."""
        from datetime import datetime
        result = TestResult(
            passed=True,
            exit_code=0,
            stdout="test output",
            stderr="",
            duration_seconds=1.5,
        )
        assert result.passed is True
        assert result.exit_code == 0
        assert result.stdout == "test output"
        assert result.stderr == ""
        assert result.duration_seconds == 1.5
        assert isinstance(result.timestamp, datetime)
        assert result.failed_tests == []
        assert result.error_summary == ""


class TestErrorAnalyzer:
    """Test ErrorAnalyzer class."""

    def test_analyze_passed(self):
        """Test analysis of passed test result."""
        result = TestResult(
            passed=True,
            exit_code=0,
            stdout="all passed",
            stderr="",
            duration_seconds=1.0,
        )
        analysis = ErrorAnalyzer.analyze(result)
        assert "All tests passed" in analysis

    def test_analyze_failed_with_details(self):
        """Test analysis of failed test result with failed test details."""
        result = TestResult(
            passed=False,
            exit_code=1,
            stdout="FAILED test_example.py::test_foo - AssertionError: assert 1 == 2",
            stderr="",
            duration_seconds=1.0,
            failed_tests=[
                {
                    "name": "test_example.py::test_foo",
                    "error": "AssertionError: assert 1 == 2",
                    "traceback": "File test_example.py line 10\nassert 1 == 2",
                }
            ],
        )
        analysis = ErrorAnalyzer.analyze(result)
        assert "FAILED TESTS (1)" in analysis
        assert "test_example.py::test_foo" in analysis
        assert "AssertionError" in analysis


class TestFixGenerator:
    """Test FixGenerator class."""

    def test_generate_assertion_error_fix(self):
        """Test fix generation for assertion errors."""
        generator = FixGenerator()
        analysis = "FAILED TESTS (1):\n  - test_example.py::test_foo\n    Error: AssertionError: assert 'spec' in result"
        fixes = generator.generate(analysis, ["tests/test_example.py"])
        assert len(fixes) > 0
        assert any(f["type"] == "test_expectation_update" for f in fixes)

    def test_generate_import_error_fix(self):
        """Test fix generation for import errors."""
        generator = FixGenerator()
        analysis = "ModuleNotFoundError: No module named 'requests'"
        fixes = generator.generate(analysis, ["src/main.py"])
        assert len(fixes) > 0
        assert any(f["type"] == "install_dependency" for f in fixes)

    def test_generate_key_error_fix(self):
        """Test fix generation for key errors."""
        generator = FixGenerator()
        analysis = "KeyError: 'spec'"
        fixes = generator.generate(analysis, ["src/agent.py"])
        assert len(fixes) > 0
        assert any(f["type"] == "fix_dict_access" for f in fixes)

    def test_generate_unknown_error_fallback(self):
        """Test fallback for unknown error types."""
        generator = FixGenerator()
        analysis = "SomeUnknownError: weird error"
        fixes = generator.generate(analysis, ["src/main.py"])
        assert len(fixes) > 0
        assert fixes[0]["type"] == "manual_review"
        assert fixes[0]["confidence"] == 0.1


class TestSelfDebugLoop:
    """Test SelfDebugLoop class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SelfDebugConfig(
            max_iterations=2,
            test_command=["echo", "test"],
            test_timeout=5,
            target_files=["src/test.py"],
        )

    @pytest.mark.asyncio
    async def test_run_success_first_try(self, config):
        """Test successful run on first iteration."""
        loop = SelfDebugLoop(config)

        # Mock _run_tests to return passing result
        loop._run_tests = AsyncMock(return_value=TestResult(
            passed=True,
            exit_code=0,
            stdout="passed",
            stderr="",
            duration_seconds=0.1,
        ))

        result = await loop.run()
        assert result is True
        assert loop.current_state == DebugState.SUCCESS
        assert len(loop.iterations) == 1
        assert loop.iterations[0].state == DebugState.SUCCESS

    @pytest.mark.asyncio
    async def test_run_fails_then_succeeds(self, config):
        """Test run that fails first then succeeds."""
        loop = SelfDebugLoop(config)

        call_count = [0]

        async def mock_run_tests():
            call_count[0] += 1
            if call_count[0] == 1:
                return TestResult(
                    passed=False,
                    exit_code=1,
                    stdout="FAILED",
                    stderr="AssertionError",
                    duration_seconds=0.1,
                    failed_tests=[{"name": "test_foo", "error": "AssertionError", "traceback": ""}],
                )
            return TestResult(
                passed=True,
                exit_code=0,
                stdout="passed",
                stderr="",
                duration_seconds=0.1,
            )

        loop._run_tests = mock_run_tests
        loop.config.auto_apply_fixes = True

        # Mock _apply_fix to return True
        loop._apply_fix = AsyncMock(return_value=True)

        result = await loop.run()
        assert result is True
        assert len(loop.iterations) == 2
        assert loop.iterations[0].state == DebugState.APPLYING_FIX
        assert loop.iterations[1].state == DebugState.SUCCESS

    @pytest.mark.asyncio
    async def test_run_max_iterations_reached(self, config):
        """Test run that reaches max iterations without success."""
        loop = SelfDebugLoop(config)

        loop._run_tests = AsyncMock(return_value=TestResult(
            passed=False,
            exit_code=1,
            stdout="FAILED",
            stderr="AssertionError",
            duration_seconds=0.1,
            failed_tests=[{"name": "test_foo", "error": "AssertionError", "traceback": ""}],
        ))

        result = await loop.run()
        assert result is False
        assert loop.current_state == DebugState.MAX_ITERATIONS_REACHED
        assert len(loop.iterations) == config.max_iterations

    def test_get_report(self, config):
        """Test report generation."""
        loop = SelfDebugLoop(config)
        loop.iterations = [
            DebugIteration(
                iteration=1,
                state=DebugState.SUCCESS,
                test_result=TestResult(True, 0, "", "", 0.1),
                fix_generated="Fixed assertion",
                fix_applied=True,
            )
        ]
        loop.current_state = DebugState.SUCCESS

        report = loop.get_report()
        assert report["final_state"] == "success"
        assert report["total_iterations"] == 1
        assert len(report["iterations"]) == 1
        assert report["iterations"][0]["fix_generated"] == "Fixed assertion"


class TestRunSelfDebug:
    """Test run_self_debug convenience function."""

    @pytest.mark.asyncio
    async def test_run_self_debug_success(self):
        """Test run_self_debug returns True on success."""
        with patch('src.core.self_debug.SelfDebugLoop.run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True
            result = await run_self_debug(max_iterations=1)
            assert result is True
            mock_run.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])