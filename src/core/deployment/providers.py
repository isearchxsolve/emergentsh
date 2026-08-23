"""
Deployment Providers — implementations for various hosting platforms.
"""

from __future__ import annotations

import os
import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .deployment import (
    DeploymentConfig,
    DeploymentResult,
    DeploymentProvider,
    VercelProvider,
)


# ════════════════════════════════════════════════════════════════════════════
# Netlify Provider
# ════════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════════
# Netlify Provider
# ════════════════════════════════════════════════════════════════════════════

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
            cmd.extend(["--message", f"PR #{pr_number} preview"])
        
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
        # Netlify doesn't have easy CLI status check
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
        config = {
            "build": {
                "command": self.config.build_command,
                "publish": self.config.output_dir,
            },
        }
        if env_vars:
            config["build"]["environment"] = env_vars
        
        path = Path(project_dir) / "netlify.toml"
        with open(path, "w") as f:
            f.write("[build]\n")
            f.write(f'  command = "{self.config.build_command}"\n')
            f.write(f'  publish = "{self.config.output_dir}"\n')
            if env_vars:
                f.write("[build.environment]\n")
                for k, v in env_vars.items():
                    f.write(f'  {k} = "{v}"\n')
    
    def _parse_netlify_url(self, output: str) -> Optional[str]:
        import re
        # Look for deployment URLs
        patterns = [
            r'https?://[^\s]+\.netlify\.app',
            r'Website URL: (https?://[^\s]+)',
            r'Deploy preview: (https?://[^\s]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1) if match.groups() else match.group(0)
        return None


# ════════════════════════════════════════════════════════════════════════════
# Fly.io Provider
# ════════════════════════════════════════════════════════════════════════════

class FlyProvider(DeploymentProvider):
    """Fly.io deployment provider."""
    
    name = "fly"
    supports_preview = False  # Fly doesn't have traditional preview deployments
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("FLY_API_TOKEN")
        self._app_name = config.provider_config.get("app_name")
        self._region = config.provider_config.get("region", "iad")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        # Check for fly.toml
        fly_toml = Path(project_dir) / "fly.toml"
        if not fly_toml.exists():
            self._generate_fly_toml(project_dir, env_vars)
        
        # Ensure flyctl is available
        cmd = ["flyctl", "deploy"]
        if self._token:
            cmd.extend(["--access-token", self._token])
        if self._app_name:
            cmd.extend(["--app", self._app_name])
        
        result = self._run_command(cmd, cwd=project_dir)
        
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
        # Fly doesn't have traditional previews; create a temporary app
        preview_name = f"{self._app_name}-pr-{pr_number}" if self._app_name and pr_number else f"preview-{int(time.time())}"
        
        # Create temporary app
        cmd = ["flyctl", "apps", "create", preview_name, "--org", "personal"]
        if self._token:
            cmd.extend(["--access-token", self._token])
        
        result = self._run_command(cmd)
        if result.returncode != 0:
            return DeploymentResult(deployment_id="", status="failed", error=result.stderr, provider=self.name)
        
        # Deploy to preview app
        self.config.provider_config["app_name"] = preview_name
        return self.deploy(project_dir, env_vars)
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Fly logs not available via simple CLI"
    
    def _generate_fly_toml(self, project_dir: str, env_vars: Dict[str, str]) -> None:
        content = f"""app = "{self._app_name or 'myapp'}"
primary_region = "{self._region}"

[build]
  command = "{self.config.build_command}"

[env]
"""
        for k, v in env_vars.items():
            content += f'  {k} = "{v}"\n'
        
        path = Path(project_dir) / "fly.toml"
        path.write_text(content)


# ════════════════════════════════════════════════════════════════════════════
# Railway Provider
# ════════════════════════════════════════════════════════════════════════════

class RailwayProvider(DeploymentProvider):
    """Railway deployment provider."""
    
    name = "railway"
    supports_preview = True
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._token = config.provider_config.get("token") or os.environ.get("RAILWAY_TOKEN")
        self._project_id = config.provider_config.get("project_id")
        self._environment_id = config.provider_config.get("environment_id")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        self._prepare_project(project_dir)
        
        # Railway uses railway CLI or API
        cmd = ["railway", "up"]
        if self._token:
            cmd.extend(["--token", self._token])
        if self._project_id:
            cmd.extend(["--project", self._project_id])
        
        result = self._run_command(cmd, cwd=project_dir)
        
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
        # Railway supports preview environments
        return self.deploy(project_dir, env_vars)
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Railway logs via CLI"


# ════════════════════════════════════════════════════════════════════════════
# Render Provider
# ════════════════════════════════════════════════════════════════════════════

class RenderProvider(DeploymentProvider):
    """Render deployment provider."""
    
    name = "render"
    supports_preview = True
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._api_key = config.provider_config.get("api_key") or os.environ.get("RENDER_API_KEY")
        self._service_id = config.provider_config.get("service_id")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        self._prepare_project(project_dir)
        
        if not self._service_id:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error="Render service_id required",
                provider=self.name,
            )
        
        # Trigger deploy via API
        import requests
        url = f"https://api.render.com/v1/services/{self._service_id}/deploys"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        
        try:
            response = requests.post(url, headers=headers, json={"clearCache": "do_not_clear"})
            if response.status_code not in (200, 201):
                return DeploymentResult(
                    deployment_id="",
                    status="failed",
                    error=f"API error: {response.text}",
                    provider=self.name,
                )
            
            data = response.json()
            return DeploymentResult(
                deployment_id=data.get("id", f"render-{int(time.time())}"),
                status="building",
                logs="Deploy triggered via Render API",
                provider=self.name,
            )
        except Exception as e:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=str(e),
                provider=self.name,
            )
    
    def create_preview(self, project_dir: str, env_vars: Dict[str, str], pr_number: Optional[int] = None) -> DeploymentResult:
        # Render supports preview via PRs automatically
        return self.deploy(project_dir, env_vars)
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        if not self._api_key:
            return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
        
        import requests
        url = f"https://api.render.com/v1/deploys/{deployment_id}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return DeploymentResult(
                    deployment_id=deployment_id,
                    status=data.get("status", "unknown"),
                    url=data.get("service", {}).get("url"),
                    provider=self.name,
                    metadata=data,
                )
        except Exception:
            pass
        return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        return "Render logs via API"


# ════════════════════════════════════════════════════════════════════════════
# Custom Provider (generic)
# ════════════════════════════════════════════════════════════════════════════

class CustomProvider(DeploymentProvider):
    """Generic custom deployment provider using shell commands."""
    
    name = "custom"
    supports_preview = False
    
    def __init__(self, config: DeploymentConfig):
        super().__init__(config)
        self._deploy_cmd = config.provider_config.get("deploy_command", "")
        self._preview_cmd = config.provider_config.get("preview_command", "")
        self._status_cmd = config.provider_config.get("status_command", "")
        self._logs_cmd = config.provider_config.get("logs_command", "")
    
    def deploy(self, project_dir: str, env_vars: Dict[str, str]) -> DeploymentResult:
        if not self._deploy_cmd:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error="No deploy_command configured for custom provider",
                provider=self.name,
            )
        
        self._prepare_project(project_dir)
        
        env = os.environ.copy()
        env.update(env_vars)
        
        result = self._run_command(
            self._deploy_cmd.split(),
            cwd=project_dir,
            env=env,
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
        if not self._preview_cmd:
            return self.deploy(project_dir, env_vars)
        
        env = os.environ.copy()
        env.update(env_vars)
        env["PR_NUMBER"] = str(pr_number) if pr_number else ""
        
        result = self._run_command(
            self._preview_cmd.split(),
            cwd=project_dir,
            env=env,
        )
        
        if result.returncode != 0:
            return DeploymentResult(
                deployment_id="",
                status="failed",
                error=result.stderr,
                provider=self.name,
            )
        
        return DeploymentResult(
            deployment_id=f"custom-preview-{int(time.time())}",
            status="deployed",
            logs=result.stdout,
            provider=self.name,
        )
    
    def get_deployment_status(self, deployment_id: str) -> DeploymentResult:
        if not self._status_cmd:
            return DeploymentResult(deployment_id=deployment_id, status="unknown", provider=self.name)
        
        result = self._run_command(self._status_cmd.split() + [deployment_id])
        if result.returncode != 0:
            return DeploymentResult(deployment_id=deployment_id, status="failed", provider=self.name)
        
        return DeploymentResult(deployment_id=deployment_id, status="completed", provider=self.name)
    
    def cancel_deployment(self, deployment_id: str) -> bool:
        return False
    
    def get_logs(self, deployment_id: str, lines: int = 100) -> str:
        if not self._logs_cmd:
            return "No logs_command configured"
        
        result = self._run_command(self._logs_cmd.split() + [deployment_id, "--lines", str(lines)])
        return result.stdout


# ════════════════════════════════════════════════════════════════════════════
# Provider Registry
# ════════════════════════════════════════════════════════════════════════════

PROVIDERS: Dict[str, type] = {
    "vercel": VercelProvider,
    "netlify": NetlifyProvider,
    "fly": FlyProvider,
    "railway": RailwayProvider,
    "render": RenderProvider,
    "custom": CustomProvider,
}


def get_provider(name: str, config: DeploymentConfig) -> DeploymentProvider:
    """Get a provider instance by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](config)


def list_providers() -> List[str]:
    return list(PROVIDERS.keys())


# Re-export for convenience
__all__ = [
    "DeploymentProvider",
    "VercelProvider",
    "NetlifyProvider",
    "FlyProvider",
    "RailwayProvider",
    "RenderProvider",
    "CustomProvider",
    "PROVIDERS",
    "get_provider",
    "list_providers",
]