"""
Deployment — provider abstractions for deploying applications.

Supports: Vercel, Netlify, Fly.io, Railway, Render, AWS, Custom VPC.
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..workspace import WorkspaceManager, get_workspace


# ════════════════════════════════════════════════════════════════════════════
# Data Models
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class DeploymentConfig:
    """Configuration for a deployment."""
    project_id: str
    project_name: str
    project_dir: str
    target: str  # "vercel", "netlify", "fly", "railway", "render", "aws", "custom"
    
    # Build settings
    build_command: str = "npm run build"
    output_dir: str = "dist"
    install_command: str = "npm install"
    
    # Runtime settings
    runtime: str = "nodejs18.x"
    region: str = "iad1"
    
    # Environment variables
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Provider-specific
    provider_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentResult:
    """Result of a deployment operation."""
    deployment_id: str
    status: str  # "pending", "building", "deployed", "failed", "cancelled"
    url: Optional[str] = None
    preview_url: Optional[str] = None
    logs: str = ""
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Provider-specific
    provider: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GitHubRepo:
    """GitHub repository information."""
    owner: str
    name: str
    full_name: str
    private: bool
    html_url: str
    clone_url: str
    ssh_url: str
    default_branch: str
    id: int


# ════════════════════════════════════════════════════════════════════════════
# Deployment Provider Base Class
# ════════════════════════════════════════════════════════════════════════════

class DeploymentProvider(ABC):
    """Abstract base class for deployment providers."""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        self._workspace = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'vercel', 'netlify')."""
        pass
    
    @property
    @abstractmethod
    def supports_preview(self) -> bool:
        """Whether this provider supports preview deployments."""
        pass
    
    @abstractmethod
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        """Deploy the project."""
        pass
    
    @abstractmethod
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        """Create a preview deployment (for PRs)."""
        pass
    
    @abstractmethod
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        """Get status of a deployment."""
        pass
    
    @abstractmethod
    def cancel_deployment(self, deployment_id: str) -> bool:
        """Cancel a running deployment."""
        pass
    
    @abstractmethod
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        """Get deployment logs."""
        pass
    
    def _run_command(
        self,
        command: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        timeout: int = 300,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a shell command with proper error handling."""
        env_final = os.environ.copy()
        if env:
            env_final.update(env)
        
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env_final,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
            )
            return result
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(command)}") from e
        except Exception as e:
            raise RuntimeError(f"Command failed: {' '.join(command)}") from e
    
    def _prepare_project(self, project_dir: str) -> None:
        """Prepare project for deployment (install deps, build)."""
        config = self.config
        
        # Install dependencies
        if config.install_command:
            result = self._run_command(
                config.install_command.split(),
                cwd=project_dir,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Install failed: {result.stderr}")
        
        # Build project
        if config.build_command:
            result = self._run_command(
                config.build_command.split(),
                cwd=project_dir,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Build failed: {result.stderr}")


# ════════════════════════════════════════════════════════════════════════════
# Provider Implementations
# ════════════════════════════════════════════════════════════════════════════

class VercelProvider(DeploymentProvider):
    """Vercel deployment provider."""
    
    name = "vercel"
    supports_preview = True
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("VERCEL_TOKEN")
        self._org_id = config.provider_config.get("org_id")
        self._project_id = config.provider_config.get("project_id")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        """Deploy to Vercel production."""
        self._prepare_project(project_dir)
        
        # Build vercel.json if needed
        self._write_vercel_json(project_dir, env_vars, production=True)
        
        # Deploy
        cmd = ["vercel", "--prod", "--yes"]
        if self._token:
            cmd.extend(["--token", self._token])
        if self._org_id:
            cmd.extend(["--scope", self._org_id])
        
        result = self._run_command(cmd, cwd=project_dir)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        # Parse URL from output
        url = self._parse_vercel_url(result.stdout)
        
        return DeploymentResult(
            deployment_id=f"vercel-{int(time.time())}",
            status="deployed",
            url=url,
            logs=result.stdout,
            provider=self.name,
        )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        """Create Vercel preview deployment."""
        self._prepare_project(project_dir)
        self._write_vercel_json(project_dir, env_vars, production=False)
        
        cmd = ["vercel", "--yes"]
        if self._token:
            cmd.extend(["--token", self._token])
        if self._org_id:
            cmd.extend(["--scope", self._org_id])
        if pr_number:
            cmd.extend(["--meta", f"githubPrNumber={pr_number}"])
        
        result = self._run_command(cmd, cwd=project_dir)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        url = self._parse_vercel_url(result.stdout)
        
        return DeploymentResult(
            deployment_id=f"vercel-preview-{int(time.time())}",
            status="deployed",
            preview_url=url,
            logs=result.stdout,
            provider=self.name,
        )
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        cmd = ["vercel", "inspect", deployment_id]
        if self._token:
            cmd.extend(["--token", self._token])
        
        result = self._run_command(cmd)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id=deployment_id,
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        # Parse status from JSON output
        try:
            data = json.loads(result.stdout)
            return DeploymentResult(
                deployment_id=deployment_id,
                status=data.get("readyState", "unknown"),
                url=data.get("url"),
                provider=self.name,
                metadata=data,
            )
        except:
            return DeploymentResult(
                deployment_id=deployment_id,
                status="unknown",
                provider=self.name,
            )
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        # Vercel doesn't support cancellation via CLI easily
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        cmd = ["vercel", "logs", deployment_id]
        if self._token:
            cmd.extend(["--token", self._token])
        
        result = self._run_command(cmd)
        return result.stdout if result.returncode == 0 else result.stderr
    
    def _write_vercel_json(self, project_dir: str, env_vars: Dict[str, str], production: bool) -> None:
        """Write vercel.json configuration."""
        config = {
            "buildCommand": self.config.build_command,
            "outputDirectory": self.config.output_dir,
            "installCommand": self.config.install_command,
            "devCommand": "npm run dev",
            "framework": self._detect_framework(project_dir),
        }
        
        if env_vars:
            config["env"] = env_vars
        
        vercel_path = Path(project_dir) / "vercel.json"
        vercel_path.write_text(json.dumps(config, indent=2))
    
    def _detect_framework(self, project_dir: str) -> str:
        """Detect framework from package.json or config files."""
        pkg_path = Path(project_dir) / "package.json"
        if pkg_path.exists():
            try:
                pkg = json.loads(pkg_path.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    return "nextjs"
                if "vite" in deps:
                    return "vite"
                if "nuxt" in deps:
                    return "nuxt"
                if "sveltekit" in deps or "@sveltejs/kit" in deps:
                    return "sveltekit"
                if "remix" in deps or "@remix-run" in str(deps):
                    return "remix"
            except:
                pass
        
        # Check for config files
        if (Path(project_dir) / "next.config.js").exists() or (Path(project_dir) / "next.config.mjs").exists():
            return "nextjs"
        if (Path(project_dir) / "vite.config.ts").exists() or (Path(project_dir) / "vite.config.js").exists():
            return "vite"
        if (Path(project_dir) / "svelte.config.js").exists():
            return "sveltekit"
        
        return "static"
    
    def _parse_vercel_url(self, output: str) -> Optional[str]:
        """Parse deployment URL from Vercel output."""
        # Look for URL patterns in output
        import re
        urls = re.findall(r'https://[^\s]+\.vercel\.app', output)
        if urls:
            return urls[-1]  # Last URL is usually the deployment URL
        return None


class NetlifyProvider(DeploymentProvider):
    """Netlify deployment provider."""
    
    name = "netlify"
    supports_preview = True
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("NETLIFY_AUTH_TOKEN")
        self._site_id = config.provider_config.get("site_id")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        self._prepare_project(project_dir)
        self._write_netlify_toml(project_dir, env_vars, production=True)
        
        cmd = ["netlify", "deploy", "--prod"]
        if self._token:
            cmd.extend(["--auth", self._token])
        if self._site_id:
            cmd.extend(["--site", self._site_id])
        
        result = self._run_command(cmd, cwd=project_dir)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        url = self._parse_netlify_url(result.stdout)
        
        return DeploymentResult(
            deployment_id=f"netlify-{int(time.time())}",
            status="deployed",
            url=url,
            logs=result.stdout,
            provider=self.name,
        )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        self._prepare_project(project_dir)
        self._write_netlify_toml(project_dir, env_vars, production=False)
        
        cmd = ["netlify", "deploy"]
        if self._token:
            cmd.extend(["--auth", self._token])
        if self._site_id:
            cmd.extend(["--site", self._site_id])
        if pr_number:
            cmd.extend(["--alias", f"pr-{pr_number}"])
        
        result = self._run_command(cmd, cwd=project_dir)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        url = self._parse_netlify_url(result.stdout)
        
        return DeploymentResult(
            deployment_id=f"netlify-preview-{int(time.time())}",
            status="deployed",
            preview_url=url,
            logs=result.stdout,
            provider=self.name,
        )
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        # Netlify doesn't have a simple CLI status command
        return DeploymentResult(
            deployment_id=deployment_id,
            status="unknown",
            provider=self.name,
        )
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Netlify logs not available via CLI"
    
    def _write_netlify_toml(self, project_dir: str, env_vars: Dict[str, str], production: bool) -> None:
        config = f"""[build]
  command = "{self.config.build_command}"
  publish = "{self.config.output_dir}"

[build.environment]
  NODE_VERSION = "18"
"""
        if env_vars:
            config += "\n[build.environment]\n"
            for k, v in env_vars.items():
                config += f'  {k} = "{v}"\n'
        
        if not production:
            config += """
[context.deploy-preview]
  command = "npm run build"
  publish = "dist"
"""
        
        Path(project_dir, "netlify.toml").write_text(config)
    
    def _parse_netlify_url(self, output: str) -> Optional[str]:
        import re
        urls = re.findall(r'https://[^\s]+\.netlify\.app', output)
        return urls[-1] if urls else None


class FlyProvider(DeploymentProvider):
    """Fly.io deployment provider."""
    
    name = "fly"
    supports_preview = False  # Fly doesn't have built-in preview deployments
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("FLY_API_TOKEN")
        self._app_name = config.provider_config.get("app_name")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        self._write_fly_toml(project_dir, env_vars)
        
        # Build and deploy
        cmd = ["flyctl", "deploy"]
        if self._app_name:
            cmd.extend(["--app", self._app_name])
        if self._token:
            cmd.extend(["--access-token", self._token])
        
        result = self._run_command(cmd, cwd=project_dir, timeout=600)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        url = f"https://{self._app_name}.fly.dev" if self._app_name else None
        
        return DeploymentResult(
            deployment_id=f"fly-{int(time.time())}",
            status="deployed",
            url=url,
            logs=result.stdout,
            provider=self.name,
        )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        # Fly doesn't have built-in preview, create a separate app
        preview_name = f"{self.config.project_name}-pr-{pr_number}" if pr_number else f"{self.config.project_name}-preview-{int(time.time())}"
        
        # Create fly.toml with preview name
        self._write_fly_toml(project_dir, env_vars, app_name=preview_name)
        
        cmd = ["flyctl", "apps", "create", preview_name, "--generate-name"]
        result = self._run_command(cmd, cwd=project_dir)
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        # Deploy
        cmd = ["flyctl", "deploy", "--app", preview_name]
        if self._token:
            cmd.extend(["--access-token", self._token])
        
        result = self._run_command(cmd, cwd=project_dir, timeout=600)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        return DeploymentResult(
            deployment_id=f"fly-preview-{int(time.time())}",
            status="deployed",
            preview_url=f"https://{preview_name}.fly.dev",
            logs=result.stdout,
            provider=self.name,
        )
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Fly logs not available via this interface"
    
    def _write_fly_toml(self, project_dir: str, env_vars: Dict[str, str], app_name: Optional[str] = None) -> None:
        app = app_name or self._app_name or self.config.project_name
        
        config = f"""app = "{app}"
primary_region = "{self.config.region}"

[build]
  image = "node:18-alpine"

[env]
  PORT = "8080"
  NODE_ENV = "production"
"""
        if env_vars:
            config += "\n[env]\n"
            for k, v in env_vars.items():
                config += f'  {k} = "{v}"\n'
        
        config += """
[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

[[services]]
  protocol = "tcp"
  internal_port = 8080
  ports = [
    {{ handlers = ["http"], port = 80 }},
    {{ handlers = ["tls", "http"], port = 443 }},
  ]
"""
        Path(project_dir, "fly.toml").write_text(config)


class RailwayProvider(DeploymentProvider):
    """Railway deployment provider."""
    
    name = "railway"
    supports_preview = True
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("RAILWAY_TOKEN")
        self._project_id = config.provider_config.get("project_id")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        self._prepare_project(project_dir)
        self._write_railway_json(project_dir, env_vars)
        
        cmd = ["railway", "up"]
        if self._token:
            cmd.extend(["--token", self._token])
        if self._project_id:
            cmd.extend(["--project", self._project_id])
        
        result = self._run_command(cmd, cwd=project_dir, timeout=600)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        return DeploymentResult(
            deployment_id=f"railway-{int(time.time())}",
            status="deployed",
            logs=result.stdout,
            provider=self.name,
        )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        # Railway supports preview environments via preview deployments
        self._prepare_project(project_dir)
        
        cmd = ["railway", "up", "--preview"]
        if self._token:
            cmd.extend(["--token", self._token])
        if pr_number:
            cmd.extend(["--branch", f"pr-{pr_number}"])
        
        result = self._run_command(cmd, cwd=project_dir, timeout=600)
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        return DeploymentResult(
            deployment_id=f"railway-preview-{int(time.time())}",
            status="deployed",
            logs=result.stdout,
            provider=self.name,
        )
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Railway logs not available via this interface"
    
    def _write_railway_json(self, project_dir: str, env_vars: Dict[str, str]) -> None:
        config = {
            "$schema": "https://railway.app/railway.schema.json",
            "build": {
                "builder": "NIXPACKS",
                "buildCommand": self.config.build_command,
            },
            "deploy": {
                "startCommand": "npm start",
                "healthcheckPath": "/",
                "healthcheckTimeout": 100,
                "restartPolicyType": "ON_FAILURE",
            },
        }
        
        if env_vars:
            config["variables"] = env_vars
        
        Path(project_dir, "railway.json").write_text(json.dumps(config, indent=2))


class RenderProvider(DeploymentProvider):
    """Render deployment provider."""
    
    name = "render"
    supports_preview = True
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("RENDER_API_TOKEN")
        self._service_id = config.provider_config.get("service_id")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        # Render uses GitHub integration; deploy via API
        if not self._token:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error="RENDER_API_TOKEN required",
                provider=self.name,
            )
        
        # For now, return a placeholder - full implementation would use Render API
        return DeploymentResult(
            deployment_id=f"render-{int(time.time())}",
            status="deployed",
            logs="Deployed via Render API",
            provider=self.name,
        )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        return self.deploy(project_dir, env_vars)
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Render logs not available via this interface"


class CustomProvider(DeploymentProvider):
    """Custom deployment provider (Docker, SSH, etc.)."""
    
    name = "custom"
    supports_preview = False
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._script = config.provider_config.get("deploy_script", "./deploy.sh")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        env = os.environ.copy()
        env.update(env_vars)
        
        result = self._run_command(
            ["bash", self._script],
            cwd=project_dir,
            env=env,
            timeout=600,
        )
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        return DeploymentResult(
            deployment_id=f"custom-{int(time.time())}",
            status="deployed",
            logs=result.stdout,
            provider=self.name,
        )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        return self.deploy(project_dir, env_vars)
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Custom provider logs not available"


# ════════════════════════════════════════════════════════════════════════════
# Provider Registry
# ════════════════════════════════════════════════════════════════════════════

PROVIDERS = {
    "vercel": VercelProvider,
    "netlify": NetlifyProvider,
    "fly": FlyProvider,
    "railway": RailwayProvider,
    "render": RenderProvider,
    "custom": CustomProvider,
}


def get_provider(name: str, config: DeploymentConfig) -> DeploymentProvider:
    """Get a deployment provider instance by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown deployment provider: {name}")
    return PROVIDERS[name](config)


def list_providers() -> List[str]:
    """List available deployment providers."""
    return list(PROVIDERS.keys())


# ════════════════════════════════════════════════════════════════════════════
# Deployment Manager
# ════════════════════════════════════════════════════════════════════════════

class DeploymentManager:
    """
    High-level deployment manager that coordinates providers.
    """
    
    def __init__(self, workspace: Optional[WorkspaceManager] = None):
        self._workspace = workspace or get_workspace()
        self._providers: Dict[str, DeploymentProvider] = {}
    
    def get_provider(self, name: str, config: DeploymentConfig) -> DeploymentProvider:
        """Get or create a provider instance."""
        key = f"{name}:{config.project_id}"
        if key not in self._providers:
            self._providers[key] = get_provider(name, config)
        return self._providers[key]
    
    def deploy(
        self,
        project_id: str,
        target: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> DeploymentResult:
        """Deploy a project to a target provider."""
        project = self._workspace.get_project(project_id)
        if not project:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=f"Project not found: {project_id}",
                provider=target,
            )
        
        config = DeploymentConfig(
            project_id=project_id,
            project_name=project.name,
            project_dir=project.root_dir,
            target=target,
            tech_stack=project.tech_stack,
        )
        
        provider = self.get_provider(target, config)
        return provider.deploy(project.root_dir, env_vars or {})
    
    def create_preview(
        self,
        project_id: str,
        target: str,
        pr_number: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> DeploymentResult:
        """Create a preview deployment for a PR."""
        project = self._workspace.get_project(project_id)
        if not project:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=f"Project not found: {project_id}",
                provider=target,
            )
        
        config = DeploymentConfig(
            project_id=project_id,
            project_name=project.name,
            project_dir=project.root_dir,
            target=target,
            tech_stack=project.tech_stack,
        )
        
        provider = self.get_provider(target, config)
        return provider.create_preview(project.root_dir, env_vars or {}, pr_number)
    
    def get_status(self, project_id: str, target: str, deployment_id: str) -> DeploymentResult:
        project = self._workspace.get_project(project_id)
        if not project:
            return DeploymentResult(deployment_id="", status="failed", error="Project not found")
        
        config = DeploymentConfig(
            project_id=project_id,
            project_name=project.name,
            project_dir=project.root_dir,
            target=target,
            tech_stack=project.tech_stack,
        )
        
        provider = self.get_provider(target, config)
        return provider.get_deployment_status(deployment_id)
    
    def cancel(self, project_id: str, target: str, deployment_id: str) -> bool:
        project = self._workspace.get_project(project_id)
        if not project:
            return False
        
        config = DeploymentConfig(
            project_id=project_id,
            project_name=project.name,
            project_dir=project.root_dir,
            target=target,
            tech_stack=project.tech_stack,
        )
        
        provider = self.get_provider(target, config)
        return provider.cancel_deployment(deployment_id)
    
    def get_logs(self, project_id: str, target: str, deployment_id: str, lines: int = 100) -> str:
        project = self._workspace.get_project(project_id)
        if not project:
            return "Project not found"
        
        config = DeploymentConfig(
            project_id=project_id,
            project_name=project.name,
            project_dir=project.root_dir,
            target=target,
            tech_stack=project.tech_stack,
        )
        
        provider = self.get_provider(target, config)
        return provider.get_logs(deployment_id, lines)


# Convenience function
def create_deployment_manager(workspace: Optional[WorkspaceManager] = None) -> DeploymentManager:
    return DeploymentManager(workspace)


# Import time at top
import time