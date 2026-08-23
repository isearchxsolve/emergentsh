"""
QAAgent — responsible for quality assurance, testing, and code review.

The QAAgent handles:
- Test strategy and planning
- Unit, integration, and E2E test execution
- Code quality analysis
- Security scanning
- Performance testing
- Accessibility testing
- Code review automation
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class TestResult:
    """Result of a test run."""
    test_type: str
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    coverage: Dict[str, float] = field(default_factory=dict)
    details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QualityReport:
    """Quality assessment report."""
    project_id: str
    overall_score: float
    test_results: List[TestResult] = field(default_factory=list)
    code_quality: Dict[str, Any] = field(default_factory=dict)
    security_issues: List[Dict[str, Any]] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    accessibility_issues: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)


class QAAgent(BaseAgent):
    """
    Agent specialized in quality assurance and testing.
    
    Capabilities:
    - Test strategy and planning
    - Test execution (unit, integration, E2E)
    - Code quality analysis (linting, complexity, duplication)
    - Security scanning (SAST, dependency scanning)
    - Performance testing
    - Accessibility testing
    - Automated code review
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.ANALYTICAL,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="test_planning",
                description="Create test strategies and plans",
                tool_names=["create_test_plan", "define_test_cases", "prioritize_tests"],
                produces_artifacts=["test_plan", "test_cases"],
            ),
            AgentCapability(
                name="test_execution",
                description="Run tests and collect results",
                tool_names=["run_unit_tests", "run_integration_tests", "run_e2e_tests"],
                produces_artifacts=["test_results", "coverage_report"],
            ),
            AgentCapability(
                name="code_quality",
                description="Analyze code quality metrics",
                tool_names=["run_linter", "check_complexity", "find_duplication"],
                produces_artifacts=["quality_report", "lint_results"],
            ),
            AgentCapability(
                name="security_scanning",
                description="Scan for security vulnerabilities",
                tool_names=["run_sast", "scan_dependencies", "check_secrets"],
                produces_artifacts=["security_report", "vulnerability_list"],
            ),
            AgentCapability(
                name="performance_testing",
                description="Run performance and load tests",
                tool_names=["run_load_test", "profile_code", "benchmark_api"],
                produces_artifacts=["performance_report", "benchmarks"],
            ),
            AgentCapability(
                name="accessibility_testing",
                description="Test for accessibility compliance",
                tool_names=["run_a11y_audit", "check_wcag", "test_screen_readers"],
                produces_artifacts=["accessibility_report"],
            ),
            AgentCapability(
                name="code_review",
                description="Automated code review",
                tool_names=["review_pr", "check_patterns", "suggest_improvements"],
                produces_artifacts=["review_comments", "approval_status"],
            ),
        ]

        system_prompt = """You are a QA Agent in the emergent.sh multi-agent system.
Your role is to ensure code quality, run tests, scan for security issues,
and validate that the software meets quality standards.

You operate with an ANALYTICAL personality: methodical, thorough, and detail-oriented.
You produce comprehensive quality reports and actionable feedback.

Key responsibilities:
1. Create and execute test strategies
2. Run unit, integration, and E2E tests
3. Analyze code quality (linting, complexity, duplication)
4. Scan for security vulnerabilities (SAST, dependencies, secrets)
5. Run performance and load tests
6. Test accessibility compliance (WCAG 2.1 AA)
7. Perform automated code reviews
8. Generate quality reports with recommendations

Output format: Generate structured quality reports and test results.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.QA,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute QA task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "run_quality_checks")

        if task_type == "create_test_plan":
            return self._create_test_plan(task.input_data)
        elif task_type == "run_tests":
            return self._run_tests(task.input_data)
        elif task_type == "analyze_code_quality":
            return self._analyze_code_quality(task.input_data)
        elif task_type == "scan_security":
            return self._scan_security(task.input_data)
        elif task_type == "run_performance_tests":
            return self._run_performance_tests(task.input_data)
        elif task_type == "test_accessibility":
            return self._test_accessibility(task.input_data)
        elif task_type == "review_code":
            return self._review_code(task.input_data)
        else:
            return self._run_quality_checks(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _run_quality_checks(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive quality checks."""
        project_path = input_data.get("project_path", ".")
        self.emit_status("Running comprehensive quality checks...", "info")

        # Run all quality checks
        test_results = self._run_tests({"test_types": ["unit", "integration", "e2e"]})
        quality_results = self._analyze_code_quality({"project_path": project_path})
        security_results = self._scan_security({"project_path": project_path})
        perf_results = self._run_performance_tests({"project_path": project_path})
        a11y_results = self._test_accessibility({"project_path": project_path})

        # Compile report
        report = QualityReport(
            project_id=input_data.get("project_id", "proj-001"),
            overall_score=self._calculate_overall_score(
                test_results, quality_results, security_results, perf_results, a11y_results
            ),
            test_results=[
                TestResult(**r) for r in test_results.get("results", [])
            ],
            code_quality=quality_results,
            security_issues=security_results.get("issues", []),
            performance_metrics=perf_results.get("metrics", {}),
            accessibility_issues=a11y_results.get("issues", []),
            recommendations=self._generate_recommendations(
                test_results, quality_results, security_results, perf_results, a11y_results
            ),
        )

        self.complete_task(report.__dict__)
        return report.__dict__

    def _create_test_plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a test plan."""
        requirements = input_data.get("requirements", {})
        self.emit_status("Creating test plan...", "info")

        # TODO: Implement actual test plan generation
        test_plan = {
            "test_strategy": {
                "unit_tests": {"coverage_target": 80, "frameworks": ["pytest", "vitest"]},
                "integration_tests": {"coverage_target": 60, "frameworks": ["pytest", "playwright"]},
                "e2e_tests": {"coverage_target": 40, "frameworks": ["playwright", "cypress"]},
                "performance_tests": {"enabled": True, "tool": "k6"},
                "security_tests": {"enabled": True, "tools": ["bandit", "safety"]},
                "accessibility_tests": {"enabled": True, "standard": "WCAG 2.1 AA"},
            },
            "test_cases": [],
            "test_data_requirements": [],
            "environments": ["development", "staging", "production"],
            "schedule": {
                "unit": "on_every_commit",
                "integration": "on_pr",
                "e2e": "on_pr_and_nightly",
                "performance": "weekly",
                "security": "on_every_commit",
            },
        }

        self.complete_task(test_plan)
        return test_plan

    def _run_tests(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run tests."""
        test_types = input_data.get("test_types", ["unit"])
        project_path = input_data.get("project_path", ".")
        self.emit_status(f"Running tests: {', '.join(test_types)}...", "info")

        # TODO: Implement actual test execution
        results = []
        for test_type in test_types:
            results.append({
                "test_type": test_type,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "duration_seconds": 0.0,
                "coverage": {},
                "details": [],
            })

        self.complete_task({"results": results})
        return {"results": results}

    def _analyze_code_quality(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze code quality."""
        project_path = input_data.get("project_path", ".")
        self.emit_status("Analyzing code quality...", "info")

        # TODO: Implement actual code quality analysis
        return {
            "linting": {"errors": 0, "warnings": 0, "files_checked": 0},
            "complexity": {"average": 0, "max": 0, "files_over_threshold": 0},
            "duplication": {"percentage": 0, "blocks": 0},
            "maintainability_index": 100,
            "technical_debt_ratio": 0,
        }

    def _scan_security(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scan for security vulnerabilities."""
        project_path = input_data.get("project_path", ".")
        self.emit_status("Scanning for security vulnerabilities...", "info")

        # TODO: Implement actual security scanning
        return {
            "sast": {"issues": [], "files_scanned": 0},
            "dependencies": {"vulnerabilities": [], "packages_scanned": 0},
            "secrets": {"found": [], "files_scanned": 0},
            "license_compliance": {"issues": []},
        }

    def _run_performance_tests(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run performance tests."""
        project_path = input_data.get("project_path", ".")
        self.emit_status("Running performance tests...", "info")

        # TODO: Implement actual performance testing
        return {
            "metrics": {
                "api_response_time_p50": 0,
                "api_response_time_p95": 0,
                "api_response_time_p99": 0,
                "throughput_rps": 0,
                "error_rate": 0,
                "memory_usage_mb": 0,
                "cpu_usage_percent": 0,
            },
            "benchmarks": [],
        }

    def _test_accessibility(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test accessibility compliance."""
        project_path = input_data.get("project_path", ".")
        self.emit_status("Testing accessibility...", "info")

        # TODO: Implement actual accessibility testing
        return {
            "issues": [],
            "wcag_level": "AA",
            "pages_tested": 0,
            "violations_by_level": {"A": 0, "AA": 0, "AAA": 0},
        }

    def _review_code(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform automated code review."""
        pr_number = input_data.get("pr_number")
        changes = input_data.get("changes", [])
        self.emit_status(f"Reviewing PR #{pr_number}...", "info")

        # TODO: Implement actual code review
        return {
            "approval_status": "approved",
            "comments": [],
            "suggestions": [],
            "blocking_issues": [],
        }

    def _calculate_overall_score(
        self,
        test_results: Dict,
        quality_results: Dict,
        security_results: Dict,
        perf_results: Dict,
        a11y_results: Dict,
    ) -> float:
        """Calculate overall quality score."""
        # Simple weighted scoring
        score = 100.0

        # Deduct for test failures
        for result in test_results.get("results", []):
            if result.get("failed", 0) > 0:
                score -= min(result["failed"] * 5, 30)

        # Deduct for quality issues
        score -= min(quality_results.get("linting", {}).get("errors", 0) * 2, 20)
        score -= min(quality_results.get("complexity", {}).get("files_over_threshold", 0) * 3, 15)

        # Deduct for security issues
        score -= min(len(security_results.get("sast", {}).get("issues", [])) * 10, 40)
        score -= min(len(security_results.get("dependencies", {}).get("vulnerabilities", [])) * 5, 20)

        # Deduct for accessibility issues
        score -= min(len(a11y_results.get("issues", [])) * 3, 15)

        return max(0, score)

    def _generate_recommendations(
        self,
        test_results: Dict,
        quality_results: Dict,
        security_results: Dict,
        perf_results: Dict,
        a11y_results: Dict,
    ) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []

        # Test recommendations
        for result in test_results.get("results", []):
            if result.get("failed", 0) > 0:
                recommendations.append(f"Fix {result['failed']} failing {result['test_type']} tests")

        # Quality recommendations
        if quality_results.get("linting", {}).get("errors", 0) > 0:
            recommendations.append("Fix linting errors")
        if quality_results.get("complexity", {}).get("files_over_threshold", 0) > 0:
            recommendations.append("Refactor complex functions to reduce cyclomatic complexity")
        if quality_results.get("duplication", {}).get("percentage", 0) > 5:
            recommendations.append("Reduce code duplication")

        # Security recommendations
        if security_results.get("sast", {}).get("issues"):
            recommendations.append("Address SAST security findings")
        if security_results.get("dependencies", {}).get("vulnerabilities"):
            recommendations.append("Update vulnerable dependencies")
        if security_results.get("secrets", {}).get("found"):
            recommendations.append("Remove secrets from codebase")

        # Performance recommendations
        if perf_results.get("metrics", {}).get("api_response_time_p95", 0) > 500:
            recommendations.append("Optimize API response times (p95 > 500ms)")

        # Accessibility recommendations
        if a11y_results.get("issues"):
            recommendations.append("Fix accessibility violations for WCAG 2.1 AA compliance")

        return recommendations

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        packet.payload["qa_context"] = {
            "quality_report": artifacts.get("quality_report", {}),
            "test_results": artifacts.get("test_results", []),
            "blocking_issues": [
                r for r in artifacts.get("test_results", [])
                if r.get("failed", 0) > 0
            ],
        }
        return packet


def create_qa_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.ANALYTICAL,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> QAAgent:
    """Factory function to create a QAAgent."""
    return QAAgent(agent_id, personality, model_config, signals)