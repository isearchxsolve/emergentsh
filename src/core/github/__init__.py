"""
GitHub Integration — API client and high-level manager for GitHub operations.
"""

from .github import (
    GitHubClient,
    GitHubManager,
    GitHubUser,
    GitHubRepo,
    GitHubBranch,
    GitHubCommit,
    GitHubPR,
    GitHubIssue,
    GitHubWorkflowRun,
    create_github_client,
    create_github_manager,
)

__all__ = [
    "GitHubClient",
    "GitHubManager",
    "GitHubUser",
    "GitHubRepo",
    "GitHubBranch",
    "GitHubCommit",
    "GitHubPR",
    "GitHubIssue",
    "GitHubWorkflowRun",
    "create_github_client",
    "create_github_manager",
]