"""
Self-Debugging Loop Module

Provides automated test running, error capture, fix generation, and iteration limits
for the agent framework. Implements the self-healing cycle: run → fail → analyze → fix → retry.
"""

import asyncio
import subprocess
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DebugState(Enum):
    """States in the self-debugging loop."""
    IDLE = "idle"
    RUNNING_TESTS = "running_tests"
    ANALYZING_ERRORS = "analyzing_errors"
    GENERATING_FIX = "generating_fix"
    APPLYING_FIX = "applying_fix"
    RETRYING = "retrying"
    SUCCESS = "success"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    FAILED = "failed"


@dataclass
class TestResult:
    """Result of a test run."""
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)
    failed_tests: List[Dict[str, Any]] = field(default_factory=list)
    error_summary: str = ""


@dataclass
class DebugIteration:
    """Single iteration in the debug loop."""
    iteration: int
    state: DebugState
    test_result: Optional[TestResult] = None
    error_analysis: Optional[str] = None
    fix_generated: Optional[str] = None
    fix_applied: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SelfDebugConfig:
    """Configuration for self-debugging loop."""
    max_iterations: int = 5
    test_command: List[str] = field(default_factory=lambda: ["python", "-m", "pytest", "tests/", "-v"])
    test_timeout: int = 120
    auto_apply_fixes: bool = False
    working_directory: Optional[Path] = None
    target_files: List[str] = field(default_factory=list)


class ErrorAnalyzer:
    """Analyzes test failures to extract actionable error information."""

    @staticmethod
    def analyze(test_result: TestResult) -> str:
        """Analyze test failure and return structured error analysis."""
        if test_result.passed:
            return "All tests passed."

        analysis_parts = []

        # Parse pytest output for failure details
        failed_tests = test_result.failed_tests
        if failed_tests:
            analysis_parts.append(f"FAILED TESTS ({len(failed_tests)}):")
            for ft in failed_tests:
                analysis_parts.append(f"  - {ft.get('name', 'unknown')}")
                analysis_parts.append(f"    Error: {ft.get('error', 'No error details')}")
                if ft.get('traceback'):
                    # Extract last few lines of traceback
                    tb_lines = ft['traceback'].split('\n')
                    relevant = [l for l in tb_lines if 'assert' in l or 'Error' in l or 'File' in l][-3:]
                    for line in relevant:
                        analysis_parts.append(f"    {line.strip()}")

        # Add stdout/stderr summary
        if test_result.stdout:
            analysis_parts.append(f"\nSTDOUT (last 500 chars):\n{test_result.stdout[-500:]}")
        if test_result.stderr:
            analysis_parts.append(f"\nSTDERR (last 500 chars):\n{test_result.stderr[-500:]}")

        return "\n".join(analysis_parts)


class FixGenerator:
    """Generates potential fixes based on error analysis."""

    def __init__(self):
        self.fix_patterns = {
            "AssertionError": self._fix_assertion_error,
            "ImportError": self._fix_import_error,
            "ModuleNotFoundError": self._fix_module_not_found,
            "AttributeError": self._fix_attribute_error,
            "TypeError": self._fix_type_error,
            "KeyError": self._fix_key_error,
            "FileNotFoundError": self._fix_file_not_found,
        }

    def generate(self, error_analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate potential fixes based on error analysis."""
        fixes = []

        # Extract error type from analysis
        for error_type, handler in self.fix_patterns.items():
            if error_type in error_analysis:
                fixes.extend(handler(error_analysis, target_files))

        # Generic fallback
        if not fixes:
            fixes.append({
                "type": "manual_review",
                "description": "Unable to auto-generate fix. Manual review required.",
                "confidence": 0.1,
                "files": target_files[:1] if target_files else [],
            })

        return fixes

    def _fix_assertion_error(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for assertion errors (typically test expectation mismatches)."""
        fixes = []
        # Look for assertion patterns
        if "assert" in analysis.lower():
            fixes.append({
                "type": "test_expectation_update",
                "description": "Update test assertion to match actual implementation output",
                "confidence": 0.7,
                "files": target_files,
                "action": "update_assertion",
            })
        return fixes

    def _fix_import_error(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for import errors."""
        return [{
            "type": "add_import",
            "description": "Add missing import statement",
            "confidence": 0.8,
            "files": target_files,
            "action": "add_missing_import",
        }]

    def _fix_module_not_found(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for module not found errors."""
        return [{
            "type": "install_dependency",
            "description": "Install missing Python package via pip",
            "confidence": 0.9,
            "files": [],
            "action": "pip_install",
        }]

    def _fix_attribute_error(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for attribute errors."""
        return [{
            "type": "fix_attribute_access",
            "description": "Fix incorrect attribute access or add missing attribute",
            "confidence": 0.6,
            "files": target_files,
            "action": "fix_attribute",
        }]

    def _fix_type_error(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for type errors."""
        return [{
            "type": "fix_type_mismatch",
            "description": "Fix type mismatch in function call or assignment",
            "confidence": 0.6,
            "files": target_files,
            "action": "fix_types",
        }]

    def _fix_key_error(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for key errors (dict access)."""
        return [{
            "type": "fix_dict_access",
            "description": "Add missing dict key or use .get() with default",
            "confidence": 0.7,
            "files": target_files,
            "action": "fix_dict_key",
        }]

    def _fix_file_not_found(self, analysis: str, target_files: List[str]) -> List[Dict[str, Any]]:
        """Generate fixes for file not found errors."""
        return [{
            "type": "create_missing_file",
            "description": "Create missing file or fix file path",
            "confidence": 0.8,
            "files": target_files,
            "action": "create_file",
        }]


class SelfDebugLoop:
    """Main self-debugging loop orchestrator."""

    def __init__(self, config: SelfDebugConfig):
        self.config = config
        self.error_analyzer = ErrorAnalyzer()
        self.fix_generator = FixGenerator()
        self.iterations: List[DebugIteration] = []
        self.current_state = DebugState.IDLE

    async def run(self) -> bool:
        """Run the self-debugging loop until success or max iterations."""
        logger.info(f"Starting self-debug loop with max {self.config.max_iterations} iterations")

        for iteration in range(1, self.config.max_iterations + 1):
            self.current_state = DebugState.RUNNING_TESTS
            logger.info(f"Iteration {iteration}/{self.config.max_iterations}")

            # Run tests
            test_result = await self._run_tests()

            # Record iteration
            debug_iter = DebugIteration(
                iteration=iteration,
                state=DebugState.RUNNING_TESTS,
                test_result=test_result,
            )
            self.iterations.append(debug_iter)

            # Check if passed
            if test_result.passed:
                debug_iter.state = DebugState.SUCCESS
                self.current_state = DebugState.SUCCESS
                logger.info("All tests passed!")
                return True

            # Analyze errors
            self.current_state = DebugState.ANALYZING_ERRORS
            error_analysis = self.error_analyzer.analyze(test_result)
            debug_iter.error_analysis = error_analysis
            debug_iter.state = DebugState.ANALYZING_ERRORS
            logger.info(f"Error analysis:\n{error_analysis}")

            # Generate fix
            self.current_state = DebugState.GENERATING_FIX
            fixes = self.fix_generator.generate(error_analysis, self.config.target_files)
            if fixes:
                fix_desc = fixes[0].get("description", "No description")
                debug_iter.fix_generated = fix_desc
                debug_iter.state = DebugState.GENERATING_FIX
                logger.info(f"Generated fix: {fix_desc}")

                # Apply fix if auto-apply enabled
                if self.config.auto_apply_fixes:
                    self.current_state = DebugState.APPLYING_FIX
                    applied = await self._apply_fix(fixes[0])
                    debug_iter.fix_applied = applied
                    debug_iter.state = DebugState.APPLYING_FIX
                    if applied:
                        logger.info("Fix applied, retrying...")
                        self.current_state = DebugState.RETRYING
                        continue
            else:
                logger.warning("No fixes generated")

            # If we reach here and it's the last iteration
            if iteration == self.config.max_iterations:
                self.current_state = DebugState.MAX_ITERATIONS_REACHED
                logger.error(f"Max iterations ({self.config.max_iterations}) reached")
                break

        # Only set to FAILED if not already at MAX_ITERATIONS_REACHED
        if self.current_state != DebugState.MAX_ITERATIONS_REACHED:
            self.current_state = DebugState.FAILED
        return False

    async def _run_tests(self) -> TestResult:
        """Run the test command and return structured result."""
        start_time = datetime.now()
        cmd = self.config.test_command
        cwd = self.config.working_directory or Path.cwd()

        logger.info(f"Running tests: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.config.test_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return TestResult(
                    passed=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Test timeout after {self.config.test_timeout}s",
                    duration_seconds=self.config.test_timeout,
                )

            duration = (datetime.now() - start_time).total_seconds()
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')

            # Parse pytest output for failed tests
            failed_tests = self._parse_pytest_failures(stdout_str, stderr_str)

            return TestResult(
                passed=process.returncode == 0,
                exit_code=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=duration,
                failed_tests=failed_tests,
            )

        except Exception as e:
            logger.exception("Error running tests")
            return TestResult(
                passed=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )

    def _parse_pytest_failures(self, stdout: str, stderr: str) -> List[Dict[str, Any]]:
        """Parse pytest output to extract failed test details."""
        failed = []
        combined = stdout + "\n" + stderr

        # Simple parsing for FAILED lines
        lines = combined.split('\n')
        current_test = None
        current_traceback = []

        for line in lines:
            if "FAILED" in line and "::" in line:
                if current_test:
                    current_test['traceback'] = '\n'.join(current_traceback)
                    failed.append(current_test)
                parts = line.split()
                test_name = parts[0] if parts else "unknown"
                current_test = {
                    "name": test_name,
                    "error": line,
                    "traceback": "",
                }
                current_traceback = []
            elif current_test:
                current_traceback.append(line)

        if current_test:
            current_test['traceback'] = '\n'.join(current_traceback)
            failed.append(current_test)

        return failed

    async def _apply_fix(self, fix: Dict[str, Any]) -> bool:
        """Apply a generated fix (placeholder - requires integration with code editor)."""
        # This would integrate with the edit tool or an LLM-based code modifier
        # For now, log the fix that would be applied
        logger.info(f"Would apply fix: {fix}")
        return False  # Not implemented - requires human-in-the-loop or LLM integration

    def get_report(self) -> Dict[str, Any]:
        """Get a summary report of the debug loop execution."""
        return {
            "final_state": self.current_state.value,
            "total_iterations": len(self.iterations),
            "iterations": [
                {
                    "iteration": i.iteration,
                    "state": i.state.value,
                    "test_passed": i.test_result.passed if i.test_result else None,
                    "error_analysis": i.error_analysis,
                    "fix_generated": i.fix_generated,
                    "fix_applied": i.fix_applied,
                }
                for i in self.iterations
            ],
        }


async def run_self_debug(
    max_iterations: int = 5,
    test_command: Optional[List[str]] = None,
    target_files: Optional[List[str]] = None,
    auto_apply: bool = False,
) -> bool:
    """Convenience function to run the self-debug loop."""
    config = SelfDebugConfig(
        max_iterations=max_iterations,
        test_command=test_command or ["python", "-m", "pytest", "tests/", "-v"],
        target_files=target_files or [],
        auto_apply_fixes=auto_apply,
    )
    loop = SelfDebugLoop(config)
    return await loop.run()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # CLI usage
    max_iter = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    result = asyncio.run(run_self_debug(max_iterations=max_iter))
    print(f"Self-debug loop {'succeeded' if result else 'failed'}")
    sys.exit(0 if result else 1)