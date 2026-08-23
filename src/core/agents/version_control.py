"""
VersionControlAgent — responsible for version control operations, Git workflows, and repository management.

The VersionControlAgent handles:
- Git repository initialization and configuration
- Branch management and workflows (GitFlow, GitHub Flow, trunk-based)
- Commit message conventions and enforcement
- Pull request creation and management
- Merge conflict resolution
- Release tagging and versioning
- Repository hooks and automation
- Submodule management
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseAgent, AgentRole, AgentPersonality, AgentCapability, AgentContext, AgentTask, HandoffPacket


@dataclass
class GitConfig:
    """Git repository configuration."""
    repo_path: str
    remote_url: Optional[str] = None
    default_branch: str = "main"
    branches: List[str] = field(default_factory=list)
    hooks: Dict[str, str] = field(default_factory=dict)
    config: Dict[str, str] = field(default_factory=dict)


@dataclass
class BranchStrategy:
    """Branch management strategy configuration."""
    strategy: str  # gitflow, github-flow, trunk-based, custom
    main_branch: str = "main"
    develop_branch: str = "develop"
    feature_prefix: str = "feature/"
    release_prefix: str = "release/"
    hotfix_prefix: str = "hotfix/"
    version_tag_prefix: str = "v"


@dataclass
class CommitConvention:
    """Commit message convention configuration."""
    convention: str = "conventional"  # conventional, angular, custom
    types: List[str] = field(default_factory=lambda: [
        "feat", "fix", "docs", "style", "refactor", "perf", "test", "chore", "build", "ci"
    ])
    scopes: List[str] = field(default_factory=list)
    require_scope: bool = False
    require_body: bool = False
    require_footer: bool = False
    max_subject_length: int = 72


@dataclass
class PullRequestConfig:
    """Pull request configuration."""
    title_template: str = "{type}: {subject}"
    body_template: str = ""
    required_reviewers: int = 1
    required_checks: List[str] = field(default_factory=list)
    auto_merge: bool = False
    delete_branch_on_merge: bool = True
    labels: List[str] = field(default_factory=list)


@dataclass
class ReleaseConfig:
    """Release configuration."""
    versioning: str = "semver"  # semver, calver, custom
    tag_prefix: str = "v"
    changelog: bool = True
    changelog_path: str = "CHANGELOG.md"
    draft_release: bool = False
    prerelease: bool = False


class VersionControlAgent(BaseAgent):
    """
    Agent specialized in version control, Git workflows, and repository management.
    
    Capabilities:
    - Repository initialization and configuration
    - Branch management and workflows
    - Commit message conventions
    - Pull request management
    - Merge conflict resolution
    - Release management and versioning
    - Git hooks and automation
    - Submodule management
    """

    def __init__(
        self,
        agent_id: str,
        personality: AgentPersonality = AgentPersonality.PRAGMATIC,
        model_config: Dict[str, Any] = None,
        signals: Any = None,
    ):
        capabilities = [
            AgentCapability(
                name="repository_management",
                description="Initialize and configure Git repositories",
                tool_names=["init_repo", "configure_repo", "setup_remote", "configure_hooks"],
                produces_artifacts=["git_config", "hooks"],
            ),
            AgentCapability(
                name="branch_management",
                description="Manage branches and workflows",
                tool_names=["create_branch", "switch_branch", "merge_branch", "delete_branch", "list_branches"],
                produces_artifacts=["branch_list", "merge_result"],
            ),
            AgentCapability(
                name="commit_management",
                description="Manage commits and commit messages",
                tool_names=["stage_changes", "create_commit", "amend_commit", "rebase_commits", "squash_commits"],
                produces_artifacts=["commit_hash", "commit_message"],
            ),
            AgentCapability(
                name="pull_request_management",
                description="Create and manage pull requests",
                tool_names=["create_pr", "update_pr", "review_pr", "merge_pr", "close_pr"],
                produces_artifacts=["pr_url", "pr_number", "review_comments"],
            ),
            AgentCapability(
                name="conflict_resolution",
                description="Resolve merge conflicts",
                tool_names=["detect_conflicts", "resolve_conflict", "abort_merge", "show_conflicts"],
                produces_artifacts=["resolution", "conflict_report"],
            ),
            AgentCapability(
                name="release_management",
                description="Manage releases and versioning",
                tool_names=["create_tag", "create_release", "generate_changelog", "bump_version"],
                produces_artifacts=["tag", "release_notes", "changelog", "version"],
            ),
            AgentCapability(
                name="submodule_management",
                description="Manage Git submodules",
                tool_names=["add_submodule", "update_submodule", "remove_submodule", "sync_submodules"],
                produces_artifacts=["submodule_config"],
            ),
        ]

        system_prompt = """You are a Version Control Agent in the emergent.sh multi-agent system.
Your role is to manage Git repositories, workflows, and version control operations.

You operate with a PRAGMATIC personality: practical, reliable, and automation-focused.
You ensure clean Git history, proper workflows, and automated version control processes.

Key responsibilities:
1. Initialize and configure Git repositories with proper settings
2. Manage branch strategies (GitFlow, GitHub Flow, trunk-based development)
3. Enforce commit message conventions (Conventional Commits, etc.)
4. Create and manage pull requests with proper templates
5. Resolve merge conflicts automatically when possible
6. Manage releases, versioning, and changelogs
7. Configure Git hooks for automation (pre-commit, commit-msg, etc.)
8. Manage submodules and dependencies

Output format: Generate Git commands, configurations, and automation scripts.
"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.VERSION_CONTROL,
            personality=personality,
            capabilities=capabilities,
            system_prompt=system_prompt,
            model_config=model_config or {},
            signals=signals,
        )

    def execute(self, task: AgentTask, context: AgentContext) -> Dict[str, Any]:
        """Execute version control task based on task type."""
        self.set_task(task)
        self.set_context(context)

        task_type = task.input_data.get("type", "init_repo")

        if task_type == "init_repo":
            return self._init_repo(task.input_data)
        elif task_type == "configure_branches":
            return self._configure_branches(task.input_data)
        elif task_type == "setup_commit_convention":
            return self._setup_commit_convention(task.input_data)
        elif task_type == "create_pr":
            return self._create_pr(task.input_data)
        elif task_type == "resolve_conflicts":
            return self._resolve_conflicts(task.input_data)
        elif task_type == "create_release":
            return self._create_release(task.input_data)
        elif task_type == "manage_submodules":
            return self._manage_submodules(task.input_data)
        elif task_type == "setup_hooks":
            return self._setup_hooks(task.input_data)
        else:
            return self._init_repo(task.input_data)

    def build_system_prompt(self, context: AgentContext) -> str:
        """Build the complete system prompt for this agent's context."""
        base = self.system_prompt
        if context and context.input_artifacts:
            base += f"\n\nInput Artifacts:\n"
            for key, value in context.input_artifacts.items():
                base += f"- {key}: {value}\n"
        return base

    def _init_repo(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize a Git repository."""
        repo_path = input_data.get("repo_path", ".")
        remote_url = input_data.get("remote_url")
        default_branch = input_data.get("default_branch", "main")
        self.emit_status(f"Initializing Git repository at {repo_path}...", "info")

        config = GitConfig(
            repo_path=repo_path,
            remote_url=remote_url,
            default_branch=default_branch,
        )

        # Generate initialization artifacts
        artifacts = {
            "git_init_commands": self._generate_init_commands(config),
            "git_config": self._generate_git_config(config),
            "gitignore": self._generate_gitignore(input_data.get("project_type", "general")),
            "hooks": self._generate_default_hooks(),
        }

        self.complete_task({
            "config": config.__dict__,
            "artifacts": artifacts,
        })
        return {"config": config.__dict__, "artifacts": artifacts}

    def _configure_branches(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Configure branch strategy."""
        strategy = input_data.get("strategy", "github-flow")
        self.emit_status(f"Configuring branch strategy: {strategy}...", "info")

        branch_strategy = BranchStrategy(
            strategy=strategy,
            main_branch=input_data.get("main_branch", "main"),
            develop_branch=input_data.get("develop_branch", "develop"),
            feature_prefix=input_data.get("feature_prefix", "feature/"),
            release_prefix=input_data.get("release_prefix", "release/"),
            hotfix_prefix=input_data.get("hotfix_prefix", "hotfix/"),
            version_tag_prefix=input_data.get("version_tag_prefix", "v"),
        )

        artifacts = {
            "branch_strategy": branch_strategy.__dict__,
            "branch_commands": self._generate_branch_commands(branch_strategy),
            "branch_protection_rules": self._generate_branch_protection(branch_strategy),
        }

        self.complete_task({
            "branch_strategy": branch_strategy.__dict__,
            "artifacts": artifacts,
        })
        return {"branch_strategy": branch_strategy.__dict__, "artifacts": artifacts}

    def _setup_commit_convention(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set up commit message convention."""
        convention = input_data.get("convention", "conventional")
        self.emit_status(f"Setting up commit convention: {convention}...", "info")

        commit_convention = CommitConvention(
            convention=convention,
            types=input_data.get("types", [
                "feat", "fix", "docs", "style", "refactor", "perf", "test", "chore", "build", "ci"
            ]),
            scopes=input_data.get("scopes", []),
            require_scope=input_data.get("require_scope", False),
            require_body=input_data.get("require_body", False),
            require_footer=input_data.get("require_footer", False),
            max_subject_length=input_data.get("max_subject_length", 72),
        )

        artifacts = {
            "commit_convention": commit_convention.__dict__,
            "commit_msg_hook": self._generate_commit_msg_hook(commit_convention),
            "commit_template": self._generate_commit_template(commit_convention),
            "lint_config": self._generate_commitlint_config(commit_convention),
        }

        self.complete_task({
            "commit_convention": commit_convention.__dict__,
            "artifacts": artifacts,
        })
        return {"commit_convention": commit_convention.__dict__, "artifacts": artifacts}

    def _create_pr(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a pull request."""
        title = input_data.get("title", "")
        body = input_data.get("body", "")
        base_branch = input_data.get("base_branch", "main")
        head_branch = input_data.get("head_branch", "")
        self.emit_status(f"Creating PR: {title}...", "info")

        pr_config = PullRequestConfig(
            title_template=input_data.get("title_template", "{type}: {subject}"),
            body_template=input_data.get("body_template", ""),
            required_reviewers=input_data.get("required_reviewers", 1),
            required_checks=input_data.get("required_checks", []),
            auto_merge=input_data.get("auto_merge", False),
            delete_branch_on_merge=input_data.get("delete_branch_on_merge", True),
            labels=input_data.get("labels", []),
        )

        artifacts = {
            "pr_config": pr_config.__dict__,
            "pr_template": self._generate_pr_template(pr_config),
            "github_actions_workflow": self._generate_pr_workflow(pr_config),
        }

        self.complete_task({
            "pr_config": pr_config.__dict__,
            "artifacts": artifacts,
        })
        return {"pr_config": pr_config.__dict__, "artifacts": artifacts}

    def _resolve_conflicts(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve merge conflicts."""
        conflict_files = input_data.get("conflict_files", [])
        strategy = input_data.get("strategy", "manual")  # manual, ours, theirs, union
        self.emit_status(f"Resolving conflicts in {len(conflict_files)} files...", "info")

        # TODO: Implement actual conflict resolution
        artifacts = {
            "conflict_files": conflict_files,
            "resolution_strategy": strategy,
            "resolution_commands": self._generate_conflict_resolution_commands(conflict_files, strategy),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _create_release(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a release."""
        version = input_data.get("version", "1.0.0")
        tag_prefix = input_data.get("tag_prefix", "v")
        self.emit_status(f"Creating release {tag_prefix}{version}...", "info")

        release_config = ReleaseConfig(
            versioning=input_data.get("versioning", "semver"),
            tag_prefix=tag_prefix,
            changelog=input_data.get("changelog", True),
            changelog_path=input_data.get("changelog_path", "CHANGELOG.md"),
            draft_release=input_data.get("draft_release", False),
            prerelease=input_data.get("prerelease", False),
        )

        artifacts = {
            "release_config": release_config.__dict__,
            "tag_command": f"git tag -a {tag_prefix}{version} -m 'Release {tag_prefix}{version}'",
            "changelog_template": self._generate_changelog_template(release_config),
            "release_notes_template": self._generate_release_notes_template(release_config),
            "github_release_workflow": self._generate_release_workflow(release_config),
        }

        self.complete_task({
            "release_config": release_config.__dict__,
            "artifacts": artifacts,
        })
        return {"release_config": release_config.__dict__, "artifacts": artifacts}

    def _manage_submodules(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Manage Git submodules."""
        action = input_data.get("action", "add")
        self.emit_status(f"Managing submodules: {action}...", "info")

        artifacts = {
            "action": action,
            "submodules": input_data.get("submodules", []),
            "commands": self._generate_submodule_commands(input_data),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    def _setup_hooks(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set up Git hooks."""
        hooks = input_data.get("hooks", ["pre-commit", "commit-msg", "pre-push"])
        self.emit_status(f"Setting up Git hooks: {', '.join(hooks)}...", "info")

        artifacts = {
            "hooks": hooks,
            "hook_scripts": self._generate_hook_scripts(hooks, input_data.get("config", {})),
            "pre_commit_config": self._generate_pre_commit_config(input_data.get("config", {})),
        }

        self.complete_task({"artifacts": artifacts})
        return {"artifacts": artifacts}

    # Helper methods for generating artifacts

    def _generate_init_commands(self, config: GitConfig) -> List[str]:
        """Generate Git initialization commands."""
        commands = [
            f"git init {config.repo_path}",
            f"cd {config.repo_path}",
            f"git branch -M {config.default_branch}",
        ]
        if config.remote_url:
            commands.append(f"git remote add origin {config.remote_url}")
        return commands

    def _generate_git_config(self, config: GitConfig) -> Dict[str, str]:
        """Generate Git configuration."""
        base_config = {
            "init.defaultBranch": config.default_branch,
            "pull.rebase": "false",
            "push.default": "simple",
            "core.autocrlf": "input",
            "core.editor": "code --wait",
        }
        base_config.update(config.config)
        return base_config

    def _generate_gitignore(self, project_type: str) -> str:
        """Generate .gitignore based on project type."""
        common = """# Dependencies
node_modules/
vendor/
__pycache__/
*.pyc
.pytest_cache/
.coverage/

# Build outputs
dist/
build/
*.egg-info/
target/
bin/
obj/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
.env.*.local

# Logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Testing
coverage/
.nyc_output/

# Misc
*.tgz
.cache/
"""
        type_specific = {
            "node": "\n# Node\npackage-lock.json\nyarn.lock\npnpm-lock.yaml\n",
            "python": "\n# Python\nPipfile.lock\npoetry.lock\n*.egg\n",
            "rust": "\n# Rust\nCargo.lock\ntarget/\n",
            "go": "\n# Go\ngo.sum\nvendor/\n",
            "java": "\n# Java\n*.class\n*.jar\n*.war\n.gradle/\n.mvn/\n",
            "general": "",
        }
        return common + type_specific.get(project_type, type_specific["general"])

    def _generate_default_hooks(self) -> Dict[str, str]:
        """Generate default Git hooks."""
        return {
            "pre-commit": "#!/bin/sh\n# Pre-commit hook\nnpx lint-staged\n",
            "commit-msg": "#!/bin/sh\n# Commit message validation\nnpx --no-install commitlint --edit $1\n",
            "pre-push": "#!/bin/sh\n# Pre-push hook\nnpm test\n",
        }

    def _generate_branch_commands(self, strategy: BranchStrategy) -> List[str]:
        """Generate branch management commands."""
        commands = [
            f"git checkout -b {strategy.main_branch}",
        ]
        if strategy.strategy == "gitflow":
            commands.append(f"git checkout -b {strategy.develop_branch}")
        return commands

    def _generate_branch_protection(self, strategy: BranchStrategy) -> Dict[str, Any]:
        """Generate branch protection rules."""
        return {
            strategy.main_branch: {
                "required_reviews": 1,
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": True,
                "required_status_checks": ["ci/build", "ci/test"],
                "enforce_admins": True,
            },
            strategy.develop_branch: {
                "required_reviews": 1,
                "required_status_checks": ["ci/build", "ci/test"],
            } if strategy.strategy == "gitflow" else {},
        }

    def _generate_commit_msg_hook(self, convention: CommitConvention) -> str:
        """Generate commit-msg hook for commitlint."""
        return f"""#!/bin/sh
# Commit message validation hook
# Convention: {convention.convention}

npx --no-install commitlint --edit "$1"
"""

    def _generate_commit_template(self, convention: CommitConvention) -> str:
        """Generate commit message template."""
        types = "|".join(convention.types)
        template = f"""# <type>[optional scope]: <description>
# 
# Types: {types}
"""
        if convention.scopes:
            template += f"# Scopes: {'|'.join(convention.scopes)}\n"
        template += """#
# Example: feat(auth): add login functionality
# Example: fix: resolve memory leak in parser
"""
        return template

    def _generate_commitlint_config(self, convention: CommitConvention) -> Dict[str, Any]:
        """Generate commitlint configuration."""
        return {
            "extends": ["@commitlint/config-conventional"],
            "rules": {
                "type-enum": [2, "always", convention.types],
                "subject-max-length": [2, "always", convention.max_subject_length],
                "scope-case": [2, "always", "lower-case"],
                "subject-case": [2, "always", "sentence-case"],
            },
        }

    def _generate_pr_template(self, config: PullRequestConfig) -> str:
        """Generate PR template."""
        return f"""---
name: Pull Request
about: Submit a pull request
title: "{config.title_template}"
labels: {', '.join(config.labels) if config.labels else ''}
---

## Description
{config.body_template or 'Please describe the changes in this PR.'}

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring
- [ ] Performance improvement
- [ ] Test update

## Checklist
- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)

## Related Issues
Closes #
"""

    def _generate_pr_workflow(self, config: PullRequestConfig) -> str:
        """Generate GitHub Actions workflow for PR checks."""
        checks = "\n".join([f"      - {check}" for check in config.required_checks])
        return f"""name: Pull Request Checks

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run checks
        run: |
{checks if checks else "        echo 'No checks configured'"}
"""

    def _generate_conflict_resolution_commands(self, files: List[str], strategy: str) -> List[str]:
        """Generate conflict resolution commands."""
        commands = []
        for file in files:
            if strategy == "ours":
                commands.append(f"git checkout --ours {file}")
            elif strategy == "theirs":
                commands.append(f"git checkout --theirs {file}")
            elif strategy == "union":
                commands.append(f"git checkout --union {file}")
            else:
                commands.append(f"# Manual resolution needed for {file}")
                commands.append(f"git mergetool {file}")
        commands.append("git add .")
        commands.append("git commit -m 'Resolve merge conflicts'")
        return commands

    def _generate_changelog_template(self, config: ReleaseConfig) -> str:
        """Generate changelog template."""
        return f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 

### Changed
- 

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
- 
"""

    def _generate_release_notes_template(self, config: ReleaseConfig) -> str:
        """Generate release notes template."""
        return f"""## {config.tag_prefix}{{version}} - {{date}}

### What's Changed

{{changelog}}

### New Contributors
{{contributors}}

**Full Changelog**: {{compare_url}}
"""

    def _generate_release_workflow(self, config: ReleaseConfig) -> str:
        """Generate GitHub Actions workflow for releases."""
        return f"""name: Release

on:
  push:
    tags:
      - '{config.tag_prefix}*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          draft: {str(config.draft_release).lower()}
          prerelease: {str(config.prerelease).lower()}
          generate_release_notes: true
"""

    def _generate_submodule_commands(self, input_data: Dict[str, Any]) -> List[str]:
        """Generate submodule management commands."""
        action = input_data.get("action", "add")
        submodules = input_data.get("submodules", [])
        commands = []

        for submodule in submodules:
            path = submodule.get("path", "")
            url = submodule.get("url", "")
            branch = submodule.get("branch", "main")

            if action == "add":
                commands.append(f"git submodule add -b {branch} {url} {path}")
            elif action == "update":
                commands.append(f"git submodule update --remote {path}")
            elif action == "remove":
                commands.append(f"git submodule deinit -f {path}")
                commands.append(f"git rm -f {path}")

        if action == "sync":
            commands.append("git submodule sync")
            commands.append("git submodule update --init --recursive")

        return commands

    def _generate_hook_scripts(self, hooks: List[str], config: Dict[str, Any]) -> Dict[str, str]:
        """Generate hook scripts."""
        scripts = {}
        for hook in hooks:
            if hook == "pre-commit":
                scripts[hook] = self._generate_pre_commit_hook(config)
            elif hook == "commit-msg":
                scripts[hook] = self._generate_commit_msg_hook(config)
            elif hook == "pre-push":
                scripts[hook] = self._generate_pre_push_hook(config)
        return scripts

    def _generate_pre_commit_hook(self, config: Dict[str, Any]) -> str:
        """Generate pre-commit hook script."""
        return """#!/bin/sh
# Pre-commit hook
echo "Running pre-commit checks..."

# Run lint-staged
npx lint-staged

# Run tests if configured
if [ -f "package.json" ] && grep -q '"test"' package.json; then
    npm test -- --passWithNoTests
fi

echo "Pre-commit checks passed!"
"""

    def _generate_commit_msg_hook(self, config: Dict[str, Any]) -> str:
        """Generate commit-msg hook script."""
        return """#!/bin/sh
# Commit message validation hook
npx --no-install commitlint --edit "$1"
"""

    def _generate_pre_push_hook(self, config: Dict[str, Any]) -> str:
        """Generate pre-push hook script."""
        return """#!/bin/sh
# Pre-push hook
echo "Running pre-push checks..."

# Run full test suite
if [ -f "package.json" ] && grep -q '"test"' package.json; then
    npm test
fi

echo "Pre-push checks passed!"
"""

    def _generate_pre_commit_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate .pre-commit-config.yaml."""
        return {
            "repos": [
                {
                    "repo": "https://github.com/pre-commit/pre-commit-hooks",
                    "rev": "v4.5.0",
                    "hooks": [
                        {"id": "trailing-whitespace"},
                        {"id": "end-of-file-fixer"},
                        {"id": "check-yaml"},
                        {"id": "check-added-large-files"},
                        {"id": "check-merge-conflict"},
                    ],
                },
                {
                    "repo": "https://github.com/psf/black",
                    "rev": "23.12.1",
                    "hooks": [{"id": "black"}],
                },
                {
                    "repo": "https://github.com/pycqa/isort",
                    "rev": "5.13.2",
                    "hooks": [{"id": "isort"}],
                },
                {
                    "repo": "https://github.com/pycqa/flake8",
                    "rev": "7.0.0",
                    "hooks": [{"id": "flake8"}],
                },
            ],
        }

    def prepare_handoff(
        self,
        to_role: AgentRole,
        payload: Dict[str, Any],
        artifacts: Dict[str, Any],
        requires_approval: bool = False,
    ) -> HandoffPacket:
        """Prepare a handoff packet to another agent."""
        packet = super().prepare_handoff(to_role, payload, artifacts, requires_approval)
        packet.payload["vcs_context"] = {
            "git_configs": artifacts.get("git_configs", []),
            "branch_strategies": artifacts.get("branch_strategies", []),
            "commit_conventions": artifacts.get("commit_conventions", []),
            "pr_configs": artifacts.get("pr_configs", []),
            "release_configs": artifacts.get("release_configs", []),
        }
        return packet


def create_version_control_agent(
    agent_id: str,
    personality: AgentPersonality = AgentPersonality.PRAGMATIC,
    model_config: Dict[str, Any] = None,
    signals: Any = None,
) -> VersionControlAgent:
    """Factory function to create a VersionControlAgent."""
    return VersionControlAgent(agent_id, personality, model_config, signals)