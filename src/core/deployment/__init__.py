"""
Deployment package — provider abstractions, deployment manager, and GitHub integration.
"""

from .deployment import (
    DeploymentConfig,
    DeploymentResult,
    GitHubRepo,
    DeploymentProvider,
    VercelProvider,
    NetlifyProvider,
    FlyProvider,
    RailwayProvider,
    RenderProvider,
    CustomProvider,
    DeploymentManager,
    create_deployment_manager,
    get_provider,
    list_providers,
    PROVIDERS,
)
from .providers import (
    DeploymentProvider,
    VercelProvider,
    NetlifyProvider,
    FlyProvider,
    RailwayProvider,
    RenderProvider,
    CustomProvider,
    PROVIDERS,
    get_provider,
    list_providers,
)
from ..github import (
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
    # Deployment core
    "DeploymentConfig",
    "DeploymentResult",
    "GitHubRepo",
    "DeploymentProvider",
    "VercelProvider",
    "NetlifyProvider",
    "FlyProvider",
    "RailwayProvider",
 "RenderProvider",
    "CustomProvider",
    "DeploymentManager",
    "create_deployment_manager",
    "get_provider",
    "list_providers",
    "PROVIDERS",
    # GitHub
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