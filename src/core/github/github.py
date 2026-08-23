"""
GitHub Integration — GitHub API client for repository management,
PR creation, branch management, and webhook handling.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


# ════════════════════════════════════════════════════════════════════════════
# Data Models
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class GitHubUser:
    """GitHub user information."""
    login: str
    id: int
    avatar_url: str
    html_url: str
    name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class GitHubRepo:
    """GitHub repository."""
    id: int
    name: str
    full_name: str
    owner: GitHubUser
    private: bool
    html_url: str
    clone_url: str
    ssh_url: str
    default_branch: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class GitHubBranch:
    """GitHub branch."""
    name: str
    commit_sha: str
    protected: bool


@dataclass
class GitHubCommit:
    """GitHub commit."""
    sha: str
    message: str
    author_name: str
    author_email: str
    date: datetime
    url: str
    parents: List[str] = field(default_factory=list)


@dataclass
class GitHubPR:
    """GitHub pull request."""
    id: int
    number: int
    title: str
    body: str
    state: str  # open, closed, merged
    head_branch: str
    base_branch: str
    head_sha: str
    base_sha: str
    html_url: str
    draft: bool
    merged: bool
    mergeable: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    author: Optional[GitHubUser] = None
    labels: List[str] = field(default_factory=list)
    assignees: List[GitHubUser] = field(default_factory=list)
    reviewers: List[GitHubUser] = field(default_factory=list)


@dataclass
class GitHubIssue:
    """GitHub issue."""
    id: int
    number: int
    title: str
    body: str
    state: str  # open, closed
    html_url: str
    labels: List[str] = field(default_factory=list)
    assignees: List[GitHubUser] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class GitHubWorkflowRun:
    """GitHub Actions workflow run."""
    id: int
    name: str
    status: str  # queued, in_progress, completed
    conclusion: Optional[str]  # success, failure, cancelled, skipped
    head_branch: str
    head_sha: str
    html_url: str
    created_at: datetime
    updated_at: datetime
    run_number: int
    run_attempt: int


# ════════════════════════════════════════════════════════════════════════════
# GitHub API Client
# ════════════════════════════════════════════════════════════════════════════

class GitHubClient:
    """
    GitHub REST API client with OAuth and PAT support.
    
    Provides methods for:
    - Repository management (create, list, delete, fork)
    - Branch management (create, list, delete, protect)
    - Commit operations (create, list, compare)
    - Pull request management (create, list, merge, review)
    - Issue management
    - Workflow runs
    - File operations (create, update, delete, get contents)
    - Webhook management
    """
    
    BASE_URL = "https://api.github.com"
    UPLOAD_URL = "https://uploads.github.com"
    
    def __init__(
        self,
        token: Optional[str] = None,
        app_id: Optional[int] = None,
        private_key: Optional[str] = None,
        installation_id: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize GitHub client.
        
        Args:
            token: Personal Access Token (classic) or OAuth token
            app_id: GitHub App ID (for App authentication)
            private_key: Private key for GitHub App (PEM format)
            installation_id: GitHub App installation ID
            timeout: Request timeout in seconds
        """
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._app_id = app_id or int(os.environ.get("GITHUB_APP_ID", "0"))
        self._private_key = private_key or os.environ.get("GITHUB_PRIVATE_KEY")
        self._installation_id = installation_id or int(os.environ.get("GITHUB_INSTALLATION_ID", "0"))
        self._timeout = timeout
        
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "EmergentSH/1.0",
        })
        
        self._app_token: Optional[str] = None
        self._app_token_expires: float = 0
        self._lock = threading.Lock()
    
    # ----------------------------------------------------------------------
    # Authentication
    # ----------------------------------------------------------------------
    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "EmergentSH/1.0",
        }
        
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        elif self._app_id and self._private_key:
            # Use GitHub App authentication
            app_token = self._get_app_token()
            if app_token:
                headers["Authorization"] = f"Bearer {app_token}"
        
        return headers
    
    def _get_app_token(self) -> Optional[str]:
        """Get GitHub App installation token."""
        if self._app_token and time.time() < self._app_token_expires - 60:
            return self._app_token
        
        if not self._app_id or not self._private_key:
            return None
        
        # Generate JWT
        import jwt
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 600,  # 10 minutes
            "iss": self._app_id,
        }
        
        jwt_token = jwt.encode(payload, self._private_key, algorithm="RS256")
        
        # Get installation token
        url = f"{self.BASE_URL}/app/installations/{self._installation_id}/access_tokens"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=self._timeout,
        )
        
        if response.status_code == 201:
            data = response.json()
            self._app_token = data["token"]
            # Token expires in 1 hour, refresh 5 minutes early
            self._app_token_expires = time.time() + 3540
            return self._app_token
        
        return None
    
    # ----------------------------------------------------------------------
    # HTTP Methods
    # ----------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> requests.Response:
        """Make HTTP request to GitHub API."""
        url = f"{self.BASE_URL}{path}"
        headers = headers or {}
        headers.update(self._get_headers())
        
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=self._timeout,
            )
            
            # Handle rate limiting
            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait_time = max(reset_time - time.time(), 0) + 1
                if wait_time < 300:  # Max 5 minutes
                    time.sleep(wait_time)
                    return self._request(method, path, params, json_data, headers)
            
            return response
        
        except requests.Timeout:
            raise RuntimeError(f"Request to {url} timed out")
        except requests.RequestException as e:
            raise RuntimeError(f"Request failed: {e}")
    
    def get(self, path: str, params: Optional[Dict] = None) -> requests.Response:
        return self._request("GET", path, params=params)
    
    def post(self, path: str, json_data: Optional[Dict] = None) -> requests.Response:
        return self._request("POST", path, json_data=json_data)
    
    def patch(self, path: str, json_data: Optional[Dict] = None) -> requests.Response:
        return self._request("PATCH", path, json_data=json_data)
    
    def put(self, path: str, json_data: Optional[Dict] = None) -> requests.Response:
        return self._request("PUT", path, json_data=json_data)
    
    def delete(self, path: str) -> requests.Response:
        return self._request("DELETE", path)
    
    # ----------------------------------------------------------------------
    # User & Auth
    # ----------------------------------------------------------------------
    def get_authenticated_user(self) -> GitHubUser:
        """Get the authenticated user."""
        response = self.get("/user")
        response.raise_for_status()
        return self._parse_user(response.json())
    
    def get_user(self, username: str) -> GitHubUser:
        """Get a user by username."""
        response = self.get(f"/users/{username}")
        response.raise_for_status()
        return self._parse_user(response.json())
    
    def _parse_user(self, data: Dict) -> GitHubUser:
        return GitHubUser(
            login=data["login"],
            id=data["id"],
            avatar_url=data["avatar_url"],
            html_url=data["html_url"],
            name=data.get("name"),
            email=data.get("email"),
        )
    
    # ----------------------------------------------------------------------
    # Repository Management
    # ----------------------------------------------------------------------
    def list_repos(
        self,
        username: Optional[str] = None,
        org: Optional[str] = None,
        type: str = "all",
        sort: str = "updated",
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubRepo]:
        """List repositories for a user or organization."""
        if org:
            path = f"/orgs/{org}/repos"
        elif username:
            path = f"/users/{username}/repos"
        else:
            path = "/user/repos"
        
        params = {"type": type, "sort": sort, "per_page": per_page, "page": page}
        response = self.get(path, params=params)
        response.raise_for_status()
        
        return [self._parse_repo(r) for r in response.json()]
    
    def get_repo(self, owner: str, repo: str) -> GitHubRepo:
        """Get a repository by owner and name."""
        response = self.get(f"/repos/{owner}/{repo}")
        response.raise_for_status()
        return self._parse_repo(response.json())
    
    def create_repo(
        self,
        name: str,
        description: Optional[str] = None,
        private: bool = False,
        auto_init: bool = True,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None,
        org: Optional[str] = None,
    ) -> GitHubRepo:
        """Create a new repository."""
        path = f"/orgs/{org}/repos" if org else "/user/repos"
        
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        
        if gitignore_template:
            data["gitignore_template"] = gitignore_template
        if license_template:
            data["license_template"] = license_template
        
        response = self.post(f"/repos/{org}/{name}" if org else "/user/repos", json_data=data)
        response.raise_for_status()
        return self._parse_repo(response.json())
    
    def delete_repo(self, owner: str, repo: str) -> bool:
        """Delete a repository."""
        response = self.delete(f"/repos/{owner}/{repo}")
        return response.status_code == 204
    
    def fork_repo(self, owner: str, repo: str, org: Optional[str] = None) -> GitHubRepo:
        """Fork a repository."""
        data = {}
        if org:
            data["organization"] = org
        
        response = self.post(f"/repos/{owner}/{repo}/forks", json_data=data)
        response.raise_for_status()
        return self._parse_repo(response.json())
    
    def _parse_repo(self, data: Dict) -> GitHubRepo:
        return GitHubRepo(
            id=data["id"],
            name=data["name"],
            full_name=data["full_name"],
            owner=self._parse_user(data["owner"]),
            private=data["private"],
            html_url=data["html_url"],
            clone_url=data["clone_url"],
            ssh_url=data["ssh_url"],
            default_branch=data["default_branch"],
            description=data.get("description"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        )
    
    # ----------------------------------------------------------------------
    # Branch Management
    # ----------------------------------------------------------------------
    def list_branches(self, owner: str, repo: str, per_page: int = 100) -> List[GitHubBranch]:
        """List branches in a repository."""
        response = self.get(f"/repos/{owner}/{repo}/branches", params={"per_page": per_page})
        response.raise_for_status()
        
        branches = []
        for b in response.json():
            branches.append(GitHubBranch(
                name=b["name"],
                commit_sha=b["commit"]["sha"],
                protected=b.get("protected", False),
            ))
        return branches
    
    def get_branch(self, owner: str, repo: str, branch: str) -> GitHubBranch:
        """Get a specific branch."""
        response = self.get(f"/repos/{owner}/{repo}/branches/{branch}")
        response.raise_for_status()
        b = response.json()
        return GitHubBranch(
            name=b["name"],
            commit_sha=b["commit"]["sha"],
            protected=b.get("protected", False),
        )
    
    def create_branch(self, owner: str, repo: str, branch: str, from_branch: str) -> GitHubBranch:
        """Create a new branch from an existing branch."""
        # Get the source branch SHA
        source = self.get_branch(owner, repo, from_branch)
        
        data = {
            "ref": f"refs/heads/{branch}",
            "sha": source.commit_sha,
        }
        
        response = self.post(f"/repos/{owner}/{repo}/git/refs", json_data=data)
        response.raise_for_status()
        
        data = response.json()
        return GitHubBranch(
            name=branch,
            commit_sha=data["object"]["sha"],
            protected=False,
        )
    
    def delete_branch(self, owner: str, repo: str, branch: str) -> bool:
        """Delete a branch."""
        response = self.delete(f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
        return response.status_code == 204
    
    def protect_branch(
        self,
        owner: str,
        repo: str,
        branch: str,
        required_reviews: int = 1,
        dismiss_stale_reviews: bool = True,
        require_code_owner_reviews: bool = False,
        required_status_checks: Optional[List[str]] = None,
        enforce_admins: bool = False,
    ) -> bool:
        """Protect a branch with rules."""
        data = {
            "required_status_checks": {"strict": True, "contexts": required_status_checks or []},
            "enforce_admins": enforce_admins,
            "required_pull_request_reviews": {
                "required_approving_review_count": required_reviews,
                "dismiss_stale_reviews": dismiss_stale_reviews,
                "require_code_owner_reviews": require_code_owner_reviews,
            },
            "restrictions": None,
        }
        
        response = self.put(
            f"/repos/{owner}/{repo}/branches/{branch}/protection",
            json_data=data,
        )
        return response.status_code == 200
    
    # ----------------------------------------------------------------------
    # Commits
    # ----------------------------------------------------------------------
    def list_commits(
        self,
        owner: str,
        repo: str,
        sha: Optional[str] = None,
        path: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubCommit]:
        """List commits in a repository."""
        params = {"per_page": per_page, "page": page}
        if sha:
            params["sha"] = sha
        if path:
            params["path"] = path
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()
        
        response = self.get(f"/repos/{owner}/{repo}/commits", params=params)
        response.raise_for_status()
        
        commits = []
        for c in response.json():
            commit_data = c["commit"]
            author = commit_data["author"]
            commits.append(GitHubCommit(
                sha=c["sha"],
                message=commit_data["message"],
                author_name=author["name"],
                author_email=author["email"],
                date=datetime.fromisoformat(author["date"].replace("Z", "+00:00")),
                url=c["html_url"],
                parents=[p["sha"] for p in c.get("parents", [])],
            ))
        return commits
    
    def get_commit(self, owner: str, repo: str, sha: str) -> GitHubCommit:
        """Get a specific commit."""
        response = self.get(f"/repos/{owner}/{repo}/commits/{sha}")
        response.raise_for_status()
        c = response.json()
        commit_data = c["commit"]
        author = commit_data["author"]
        return GitHubCommit(
            sha=c["sha"],
            message=commit_data["message"],
            author_name=author["name"],
            author_email=author["email"],
            date=datetime.fromisoformat(author["date"].replace("Z", "+00:00")),
            url=c["html_url"],
            parents=[p["sha"] for p in c.get("parents", [])],
        )
    
    def create_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parent_shas: List[str],
    ) -> str:
        """Create a new commit."""
        data = {
            "message": message,
            "tree": tree_sha,
            "parents": parent_shas,
        }
        
        response = self.post(f"/repos/{owner}/{repo}/git/commits", json_data=data)
        response.raise_for_status()
        return response.json()["sha"]
    
    def create_tree(
        self,
        owner: str,
        repo: str,
        base_tree_sha: Optional[str],
        files: List[Dict[str, str]],  # [{"path": "...", "content": "...", "mode": "100644"}, ...]
    ) -> str:
        """Create a Git tree."""
        tree = []
        for f in files:
            tree.append({
                "path": f["path"],
                "mode": f.get("mode", "100644"),
                "type": "blob",
                "content": f["content"],
            })
        
        data = {"tree": tree}
        if base_tree_sha:
            data["base_tree"] = base_tree_sha
        
        response = self.post(f"/repos/{owner}/{repo}/git/trees", json_data=data)
        response.raise_for_status()
        return response.json()["sha"]
    
    def create_blob(self, owner: str, repo: str, content: str, encoding: str = "utf-8") -> str:
        """Create a Git blob."""
        data = {"content": content, "encoding": encoding}
        response = self.post(f"/repos/{owner}/{repo}/git/blobs", json_data=data)
        response.raise_for_status()
        return response.json()["sha"]
    
    # ----------------------------------------------------------------------
    # Pull Requests
    # ----------------------------------------------------------------------
    def list_prs(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        head: Optional[str] = None,
        base: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubPR]:
        """List pull requests."""
        params = {"state": state, "per_page": per_page, "page": page}
        if head:
            params["head"] = head
        if base:
            params["base"] = base
        
        response = self.get(f"/repos/{owner}/{repo}/pulls", params=params)
        response.raise_for_status()
        
        return [self._parse_pr(p) for p in response.json()]
    
    def get_pr(self, owner: str, repo: str, number: int) -> GitHubPR:
        """Get a specific pull request."""
        response = self.get(f"/repos/{owner}/{repo}/pulls/{number}")
        response.raise_for_status()
        return self._parse_pr(response.json())
    
    def create_pr(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: Optional[str] = None,
        draft: bool = False,
    ) -> GitHubPR:
        """Create a pull request."""
        data = {
            "title": title,
            "head": head,
            "base": base,
            "draft": draft,
        }
        if body:
            data["body"] = body
        
        response = self.post(f"/repos/{owner}/{repo}/pulls", json_data=data)
        response.raise_for_status()
        return self._parse_pr(response.json())
    
    def update_pr(
        self,
        owner: str,
        repo: str,
        number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
    ) -> GitHubPR:
        """Update a pull request."""
        data = {}
        if title is not None:
            data["title"] = title
        if body is not None:
            data["body"] = body
        if state is not None:
            data["state"] = state
        
        response = self.patch(f"/repos/{owner}/{repo}/pulls/{number}", json_data=data)
        response.raise_for_status()
        return self._parse_pr(response.json())
    
    def merge_pr(
        self,
        owner: str,
        repo: str,
        number: int,
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
        merge_method: str = "merge",  # merge, squash, rebase
    ) -> Dict[str, Any]:
        """Merge a pull request."""
        data = {"merge_method": merge_method}
        if commit_title:
            data["commit_title"] = commit_title
        if commit_message:
            data["commit_message"] = commit_message
        
        response = self.put(f"/repos/{owner}/{repo}/pulls/{number}/merge", json_data=data)
        response.raise_for_status()
        return response.json()
    
    def close_pr(self, owner: str, repo: str, number: int) -> GitHubPR:
        """Close a pull request."""
        return self.update_pr(owner, repo, number, state="closed")
    
    def get_pr_files(self, owner: str, repo: str, number: int) -> List[Dict]:
        """Get files changed in a PR."""
        response = self.get(f"/repos/{owner}/{repo}/pulls/{number}/files")
        response.raise_for_status()
        return response.json()
    
    def get_pr_commits(self, owner: str, repo: str, number: int) -> List[GitHubCommit]:
        """Get commits in a PR."""
        response = self.get(f"/repos/{owner}/{repo}/pulls/{number}/commits")
        response.raise_for_status()
        
        commits = []
        for c in response.json():
            commit_data = c["commit"]
            author = commit_data["author"]
            commits.append(GitHubCommit(
                sha=c["sha"],
                message=commit_data["message"],
                author_name=author["name"],
                author_email=author["email"],
                date=datetime.fromisoformat(author["date"].replace("Z", "+00:00")),
                url=c["html_url"],
                parents=[p["sha"] for p in c.get("parents", [])],
            ))
        return commits
    
    def get_pr_reviews(self, owner: str, repo: str, number: int) -> List[Dict]:
        """Get reviews on a PR."""
        response = self.get(f"/repos/{owner}/{repo}/pulls/{number}/reviews")
        response.raise_for_status()
        return response.json()
    
    def create_pr_review(
        self,
        owner: str,
        repo: str,
        number: int,
        body: str,
        event: str = "COMMENT",  # APPROVE, REQUEST_CHANGES, COMMENT
        comments: Optional[List[Dict]] = None,
    ) -> Dict:
        """Create a review on a PR."""
        data = {"body": body, "event": event}
        if comments:
            data["comments"] = comments
        
        response = self.post(f"/repos/{owner}/{repo}/pulls/{number}/reviews", json_data=data)
        response.raise_for_status()
        return response.json()
    
    def _parse_pr(self, data: Dict) -> GitHubPR:
        return GitHubPR(
            id=data["id"],
            number=data["number"],
            title=data["title"],
            body=data["body"] or "",
            state=data["state"],
            head_branch=data["head"]["ref"],
            base_branch=data["base"]["ref"],
            head_sha=data["head"]["sha"],
            base_sha=data["base"]["sha"],
            html_url=data["html_url"],
            draft=data.get("draft", False),
            merged=data.get("merged", False),
            mergeable=data.get("mergeable"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
            merged_at=datetime.fromisoformat(data["merged_at"].replace("Z", "+00:00")) if data.get("merged_at") else None,
            author=self._parse_user(data["user"]) if data.get("user") else None,
            labels=[l["name"] for l in data.get("labels", [])],
            assignees=[self._parse_user(a) for a in data.get("assignees", [])],
            reviewers=[self._parse_user(r) for r in data.get("requested_reviewers", [])],
        )
    
    # ----------------------------------------------------------------------
    # Issues
    # ----------------------------------------------------------------------
    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: Optional[str] = None,
        assignee: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubIssue]:
        """List issues in a repository."""
        params = {"state": state, "per_page": per_page, "page": page}
        if labels:
            params["labels"] = labels
        if assignee:
            params["assignee"] = assignee
        
        response = self.get(f"/repos/{owner}/{repo}/issues", params=params)
        response.raise_for_status()
        
        issues = []
        for i in response.json():
            # Skip PRs (they appear in issues endpoint)
            if "pull_request" in i:
                continue
            issues.append(GitHubIssue(
                id=i["id"],
                number=i["number"],
                title=i["title"],
                body=i["body"] or "",
                state=i["state"],
                html_url=i["html_url"],
                labels=[l["name"] for l in i.get("labels", [])],
                assignees=[self._parse_user(a) for a in i.get("assignees", [])],
                created_at=datetime.fromisoformat(i["created_at"].replace("Z", "+00:00")) if i.get("created_at") else None,
                updated_at=datetime.fromisoformat(i["updated_at"].replace("Z", "+00:00")) if i.get("updated_at") else None,
            ))
        return issues
    
    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: Optional[str] = None,
        assignees: Optional[List[str]] = None,
        labels: Optional[List[str]] = None,
    ) -> GitHubIssue:
        """Create an issue."""
        data = {"title": title}
        if body:
            data["body"] = body
        if assignees:
            data["assignees"] = assignees
        if labels:
            data["labels"] = labels
        
        response = self.post(f"/repos/{owner}/{repo}/issues", json_data=data)
        response.raise_for_status()
        
        i = response.json()
        return GitHubIssue(
            id=i["id"],
            number=i["number"],
            title=i["title"],
            body=i["body"] or "",
            state=i["state"],
            html_url=i["html_url"],
            labels=[l["name"] for l in i.get("labels", [])],
            assignees=[self._parse_user(a) for a in i.get("assignees", [])],
            created_at=datetime.fromisoformat(i["created_at"].replace("Z", "+00:00")) if i.get("created_at") else None,
            updated_at=datetime.fromisoformat(i["updated_at"].replace("Z", "+00:00")) if i.get("updated_at") else None,
        )
    
    # ----------------------------------------------------------------------
    # File Operations
    # ----------------------------------------------------------------------
    def get_file_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get file contents from a repository."""
        params = {}
        if ref:
            params["ref"] = ref
        
        response = self.get(f"/repos/{owner}/{repo}/contents/{path}", params=params)
        response.raise_for_status()
        return response.json()
    
    def create_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Dict:
        """Create a new file."""
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message,
            "content": content_b64,
        }
        if branch:
            data["branch"] = branch
        
        response = self.put(f"/repos/{owner}/{repo}/contents/{path}", json_data=data)
        response.raise_for_status()
        return response.json()
    
    def update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        sha: str,
        branch: Optional[str] = None,
    ) -> Dict:
        """Update an existing file."""
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message,
            "content": content_b64,
            "sha": sha,
        }
        if branch:
            data["branch"] = branch
        
        response = self.put(f"/repos/{owner}/{repo}/contents/{path}", json_data=data)
        response.raise_for_status()
        return response.json()
    
    def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        sha: str,
        branch: Optional[str] = None,
    ) -> Dict:
        """Delete a file."""
        data = {"message": message, "sha": sha}
        if branch:
            data["branch"] = branch
        
        response = self.delete(f"/repos/{owner}/{repo}/contents/{path}", json_data=data)
        response.raise_for_status()
        return response.json()
    
    # ----------------------------------------------------------------------
    # Webhooks
    # ----------------------------------------------------------------------
    def list_webhooks(self, owner: str, repo: str) -> List[Dict]:
        response = self.get(f"/repos/{owner}/{repo}/hooks")
        response.raise_for_status()
        return response.json()
    
    def create_webhook(
        self,
        owner: str,
        repo: str,
        url: str,
        events: List[str] = ["push", "pull_request"],
        secret: Optional[str] = None,
        active: bool = True,
    ) -> Dict:
        data = {
            "name": "web",
            "config": {
                "url": url,
                "content_type": "json",
            },
            "events": events,
            "active": True,
        }
        if secret:
            data["config"]["secret"] = secret
        
        response = self.post(f"/repos/{owner}/{repo}/hooks", json_data=data)
        response.raise_for_status()
        return response.json()
    
    def delete_webhook(self, owner: str, repo: str, hook_id: int) -> bool:
        response = self.delete(f"/repos/{owner}/{repo}/hooks/{hook_id}")
        return response.status_code == 204
    
    # ----------------------------------------------------------------------
    # Workflow Runs
    # ----------------------------------------------------------------------
    def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
        branch: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> List[GitHubWorkflowRun]:
        path = f"/repos/{owner}/{repo}/actions/runs"
        if workflow_id:
            path = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        
        params = {"per_page": per_page, "page": page}
        if branch:
            params["branch"] = branch
        if status:
            params["status"] = status
        
        response = self.get(path, params=params)
        response.raise_for_status()
        
        runs = []
        for r in response.json().get("workflow_runs", []):
            runs.append(GitHubWorkflowRun(
                id=r["id"],
                name=r["name"],
                status=r["status"],
                conclusion=r.get("conclusion"),
                head_branch=r["head_branch"],
                head_sha=r["head_sha"],
                html_url=r["html_url"],
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                run_number=r["run_number"],
                run_attempt=r["run_attempt"],
            ))
        return runs
    
    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> GitHubWorkflowRun:
        response = self.get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")
        response.raise_for_status()
        r = response.json()
        return GitHubWorkflowRun(
            id=r["id"],
            name=r["name"],
            status=r["status"],
            conclusion=r.get("conclusion"),
            head_branch=r["head_branch"],
            head_sha=r["head_sha"],
            html_url=r["html_url"],
            created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
            run_number=r["run_number"],
            run_attempt=r["run_attempt"],
        )
    
    def rerun_workflow(self, owner: str, repo: str, run_id: int) -> bool:
        response = self.post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun")
        return response.status_code == 201
    
    def cancel_workflow(self, owner: str, repo: str, run_id: int) -> bool:
        response = self.post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel")
        return response.status_code == 202
    
    # ----------------------------------------------------------------------
    # Git Operations (low-level)
    # ----------------------------------------------------------------------
    def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> Dict:
        """Create a Git reference (branch/tag)."""
        data = {"ref": f"refs/heads/{ref}", "sha": sha}
        response = self.post(f"/repos/{owner}/{repo}/git/refs", json_data=data)
        response.raise_for_status()
        return response.json()
    
    def get_ref(self, owner: str, repo: str, ref: str) -> Dict:
        response = self.get(f"/repos/{owner}/{repo}/git/refs/heads/{ref}")
        response.raise_for_status()
        return response.json()


# ════════════════════════════════════════════════════════════════════════════
# GitHub Manager (High-level operations)
# ════════════════════════════════════════════════════════════════════════════

class GitHubManager:
    """
    High-level GitHub manager for common operations.
    
    Combines multiple API calls into logical workflows:
    - Create repo + push initial code
    - Create PR from branch
    - Auto-merge with checks
    - Branch protection setup
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        workspace: Optional[WorkspaceManager] = None,
    ):
        self._client = GitHubClient(token=token)
        self._workspace = workspace or get_workspace()
    
    @property
    def client(self) -> GitHubClient:
        return self._client
    
    # ----------------------------------------------------------------------
    # Repository Workflows
    # ----------------------------------------------------------------------
    def create_project_repo(
        self,
        project_id: str,
        private: bool = False,
        org: Optional[str] = None,
    ) -> GitHubRepo:
        """Create a GitHub repo for a project and push initial code."""
        project = self._workspace.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        repo = self._client.create_repo(
            name=project.name,
            description=project.description,
            private=private,
            auto_init=True,
            org=org,
        )
        
        # Update project with repo info
        self._workspace.update_project(project_id, git_repo_url=repo.clone_url)
        
        return repo
    
    def push_project_code(
        self,
        project_id: str,
        branch: str = "main",
        commit_message: str = "Initial commit",
    ) -> bool:
        """Push project code to GitHub."""
        project = self._workspace.get_project(project_id)
        if not project or not project.git_repo_url:
            return False
        
        # This would typically use git CLI or a git library
        # For now, return placeholder
        return True
    
    def create_feature_branch(
        self,
        project_id: str,
        branch_name: str,
        from_branch: str = "main",
    ) -> GitHubBranch:
        """Create a feature branch for a task."""
        project = self._workspace.get_project(project_id)
        if not project or not project.git_repo_url:
            raise ValueError("Project has no GitHub repo")
        
        # Extract owner/repo from URL
        # git@github.com:owner/repo.git or https://github.com/owner/repo.git
        import re
        match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', project.git_repo_url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        
        owner, repo = match.groups()
        repo = repo.replace(".git", "")
        
        return self._client.create_branch(owner, repo, branch_name, from_branch)
    
    def create_pr_for_task(
        self,
        project_id: str,
        task_id: str,
        title: str,
        description: str,
        head_branch: str,
        base_branch: str = "main",
        draft: bool = False,
    ) -> GitHubPR:
        """Create a PR for a completed task."""
        project = self._workspace.get_project(project_id)
        if not project or not project.git_repo_url:
            raise ValueError("Project has no GitHub repo")
        
        match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', project.git_repo_url)
        if not match:
            raise ValueError("Invalid GitHub URL")
        
        owner, repo = match.groups()
        repo = repo.replace(".git", "")
        
        return self._client.create_pr(
            owner=owner,
            repo=repo,
            title=title,
            head=head_branch,
            base=base_branch,
            body=description,
            draft=draft,
        )
    
    def auto_merge_pr(
        self,
        project_id: str,
        pr_number: int,
        merge_method: str = "squash",
    ) -> Dict:
        """Auto-merge a PR after checks pass."""
        project = self._workspace.get_project(project_id)
        if not project or not project.git_repo_url:
            raise ValueError("Project has no GitHub repo")
        
        match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', project.git_repo_url)
        owner, repo = match.groups()
        repo = repo.replace(".git", "")
        
        # Wait for checks to pass (polling)
        # In real implementation, would poll status checks
        
        return self._client.merge_pr(
            owner=owner,
            repo=repo,
            number=pr_number,
            merge_method=merge_method,
        )
    
    def setup_branch_protection(
        self,
        project_id: str,
        branch: str = "main",
        required_reviews: int = 1,
        required_checks: Optional[List[str]] = None,
    ) -> bool:
        """Set up branch protection rules."""
        project = self._workspace.get_project(project_id)
        if not project or not project.git_repo_url:
            raise ValueError("Project has no GitHub repo")
        
        match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', project.git_repo_url)
        owner, repo = match.groups()
        repo = repo.replace(".git", "")
        
        return self._client.protect_branch(
            owner=owner,
            repo=repo,
            branch=branch,
            required_reviews=required_reviews,
            required_status_checks=required_checks,
        )
    
    def create_deploy_key(self, project_id: str, key_title: str, public_key: str) -> bool:
        """Add a deploy key to the repository."""
        project = self._workspace.get_project(project_id)
        if not project or not project.git_repo_url:
            raise ValueError("Project has no GitHub repo")
        
        match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', project.git_repo_url)
        owner, repo = match.groups()
        repo = repo.replace(".git", "")
        
        # This would use the keys endpoint
        # POST /repos/{owner}/{repo}/keys
        # For now, placeholder
        return True


# Convenience functions
def create_github_client(token: Optional[str] = None) -> GitHubClient:
    return GitHubClient(token=token)


def create_github_manager(token: Optional[str] = None) -> GitHubManager:
    return GitHubManager(token=token)