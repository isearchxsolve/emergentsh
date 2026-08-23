"""
IntegrationGenerator — generates third-party integration code.

Generates:
- API clients (REST, GraphQL, gRPC)
- Webhook handlers
- OAuth flows
- SDK wrappers
- Event consumers/producers
- Message queue integrations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.templates.engine import (
    build_project_context,
    get_stack_loader,
)
from ..core.workspace import WorkspaceManager, get_workspace, Project, Artifact


@dataclass
class APIClientSpec:
    """Specification for an API client wrapper."""
    name: str
    base_url: str
    auth_type: str  # "bearer", "api_key", "oauth2", "basic", "none"
    endpoints: List[Dict[str, Any]]  # path, method, params, response
    rate_limit: Optional[Dict[str, int]] = None  # requests, window_seconds
    retry_config: Optional[Dict[str, Any]] = None
    webhook_verification: Optional[Dict[str, Any]] = None


@dataclass
class WebhookSpec:
    """Specification for a webhook handler."""
    name: str
    path: str  # e.g., "/webhooks/stripe"
    provider: str  # "stripe", "github", "slack", "custom"
    events: List[str]  # Event types to handle
    secret_header: str  # Header containing signature
    secret_env_var: str  # Environment variable for secret
    idempotency_key: Optional[str] = None


@dataclass
class OAuthSpec:
    """Specification for an OAuth integration."""
    provider: str  # "github", "google", "github", "microsoft", "custom"
    client_id_env: str
    client_secret_env: str
    redirect_uri: str
    scopes: List[str]
    authorize_url: str
    token_url: str
    user_info_url: Optional[str] = None
    pkce: bool = True


@dataclass
class SDKSpec:
    """Specification for an SDK wrapper."""
    name: str
    language: str  # "typescript", "python", "go"
    package_name: str
    version: str
    api_client_spec: APIClientSpec
    additional_methods: List[Dict[str, Any]] = field(default_factory=list)


class IntegrationGenerator:
    """
    Generates integration code for third-party services.

    Used by the IntegrationAgent to produce:
    - Typed API clients with retry/circuit breaker
    - Webhook receivers with signature verification
    - OAuth flows (authorization code, client credentials, device flow)
    - SDK wrappers for internal use
    - Event publishers/consumers (Kafka, RabbitMQ, Redis Streams)
    - Message queue consumers with dead letter handling
    """

    def __init__(
        self,
        project: Project,
        workspace: Optional[WorkspaceManager] = None,
        template_root: Optional[str] = None,
    ):
        self._project = project
        self._workspace = workspace or get_workspace()
        self._template_root = template_root
        self._stack_loader = get_stack_loader(project.tech_stack.get("backend", "fastapi"))

    # ----------------------------------------------------------------------
    # API Client Generation
    # ----------------------------------------------------------------------
    def generate_api_client(self, spec: APIClientSpec) -> Dict[str, str]:
        """Generate a typed API client with retry, rate limiting, and circuit breaker."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "client_name": spec.name,
            "base_url": spec.base_url,
            "auth_type": spec.auth_type,
            "endpoints": spec.endpoints,
            "rate_limit": spec.rate_limit,
            "retry_config": spec.retry_config,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "py"

        if "fastapi" in backend or "python" in backend:
            output_path = f"backend/integrations/{spec.name.lower()}_client.{ext}"
            template_name = "integrations/api-client-python.j2"
        else:
            output_path = f"src/integrations/{spec.name.lower()}-client.{ext}"
            template_name = f"integrations/api-client.{ext}.j2"

        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_api_client(spec, context)

        return {output_path: content}

    def generate_webhook_handler(self, spec: WebhookSpec) -> Dict[str, str]:
        """Generate a webhook handler with signature verification."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "webhook_name": spec.name,
            "webhook_path": spec.path,
            "provider": spec.provider,
            "events": spec.events,
            "secret_header": spec.secret_header,
            "secret_env_var": spec.secret_env_var,
            "idempotency_key": spec.idempotency_key,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "py"

        if "nextjs" in backend:
            output_path = f"src/app/api/webhooks/{spec.name}/route.{ext}"
        elif "fastapi" in backend:
            output_path = f"backend/integrations/webhooks/{spec.name}.{ext}"
        elif "express" in backend:
            output_path = f"backend/src/webhooks/{spec.name}.{ext}"
        else:
            output_path = f"backend/webhooks/{spec.name}.{ext}"

        template_name = f"integrations/webhook-{spec.provider}.{ext}.j2"
        try:
            content = self._stack_loader.render(template_name, context)
        except Exception:
            content = self._render_base_webhook(spec, context)

        return {output_path: content}

    def generate_oauth_flow(self, spec: OAuthSpec) -> Dict[str, str]:
        """Generate OAuth authorization code flow with PKCE support."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "provider": spec.provider,
            "client_id_env": spec.client_id_env,
            "client_secret_env": spec.client_secret_env,
            "redirect_uri": spec.redirect_uri,
            "scopes": spec.scopes,
            "authorize_url": spec.authorize_url,
            "token_url": spec.token_url,
            "user_info_url": spec.user_info_url,
            "pkce": spec.pkce,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "py"

        if "nextjs" in backend:
            output_paths = {
                f"src/app/api/auth/{spec.provider}/authorize/route.{ext}": "authorize",
                f"src/app/api/auth/{spec.provider}/callback/route.{ext}": "callback",
                f"src/lib/auth/{spec.provider}.{ext}": "client",
            }
        elif "fastapi" in backend:
            output_paths = {
                f"backend/integrations/oauth/{spec.provider}_auth.{ext}": "client",
                f"backend/api/routes/oauth_{spec.provider}.{ext}": "routes",
            }
        else:
            output_paths = {
                f"backend/oauth/{spec.provider}.{ext}": "client",
            }

        artifacts = {}
        for path, template_type in output_paths.items():
            template_name = f"integrations/oauth-{spec.provider}-{template_type}.{ext}.j2"
            try:
                content = self._stack_loader.render(template_name, context)
            except Exception:
                content = self._render_base_oauth(spec, context, template_type)
            artifacts[path] = content

        return artifacts

    def generate_sdk_wrapper(self, spec: SDKSpec) -> Dict[str, str]:
        """Generate an SDK wrapper around an API client."""
        # First generate the base API client
        api_artifacts = self.generate_api_client(spec.api_client_spec)

        # Then generate additional SDK methods
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "sdk_name": spec.name,
            "package_name": spec.package_name,
            "version": spec.version,
            "language": spec.language,
            "additional_methods": spec.additional_methods,
        })

        ext = "ts" if spec.language == "typescript" else ("py" if spec.language == "python" else "go")
        output_path = f"sdks/{spec.package_name}/src/index.{ext}"

        try:
            content = self._stack_loader.render(f"sdks/{spec.language}-sdk.{ext}.j2", context)
        except Exception:
            content = self._render_base_sdk(spec, context)

        return {**api_artifacts, output_path: content}

    def generate_event_consumer(
        self,
        name: str,
        topic: str,
        message_schema: Dict[str, Any],
        handler_code: str,
        consumer_group: str = "default",
    ) -> Dict[str, str]:
        """Generate a message queue consumer (Kafka, RabbitMQ, Redis Streams)."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "consumer_name": name,
            "topic": topic,
            "message_schema": message_schema,
            "handler_code": handler_code,
            "consumer_group": consumer_group,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "py"

        if "fastapi" in backend:
            output_path = f"backend/integrations/events/{name}_consumer.py"
        else:
            output_path = f"src/integrations/events/{name}-consumer.{ext}"

        try:
            content = self._stack_loader.render("integrations/event-consumer.j2", context)
        except Exception:
            content = self._render_base_event_consumer(name, context)

        return {output_path: content}

    def generate_event_publisher(
        self,
        name: str,
        topic: str,
        message_schema: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate an event publisher."""
        context = build_project_context(
            project_name=self._project.name,
            tech_stack=self._project.tech_stack,
        )
        context.update({
            "publisher_name": name,
            "topic": topic,
            "message_schema": message_schema,
        })

        backend = self._project.tech_stack.get("backend", "fastapi")
        ext = "ts" if "typescript" in str(self._project.tech_stack).lower() else "py"

        output_path = f"backend/integrations/events/{name}_publisher.{ext}" if "fastapi" in backend else f"src/integrations/events/{name}-publisher.{ext}"

        try:
            content = self._stack_loader.render("integrations/event-publisher.j2", context)
        except Exception:
            content = self._render_base_event_publisher(name, context)

        return {output_path: content}

    def persist_artifacts(self, artifacts: Dict[str, str], task_id: str) -> None:
        """Persist generated artifacts to workspace and project."""
        if not self._workspace:
            return

        for path, content in artifacts.items():
            full_path = Path(self._project.root_dir) / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

            artifact = Artifact(
                id=f"art-{abs(hash(f'{task_id}:{path}')) % 1000000:06d}",
                project_id=self._project.id,
                task_id=task_id,
                agent_role="integration",
                kind="file",
                path=path,
                content=content,
                metadata={},
            )
            self._workspace.save_artifact(artifact)

    # ----------------------------------------------------------------------
    # Base Renderers (Fallbacks)
    # ----------------------------------------------------------------------
    def _render_base_api_client(self, spec: APIClientSpec, context: Dict) -> str:
        return f'''"""
{sinc_name} API Client
Auto-generated integration client for {spec.base_url}
"""

import httpx
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class {spec.name}Config:
    base_url: str = "{spec.base_url}"
    timeout: float = 30.0
    max_retries: int = 3
    rate_limit: int = {spec.rate_limit.get("requests", 100) if spec.rate_limit else 100}

class {spec.name}Client:
    """Typed API client for {spec.name}"""

    def __init__(self, config: Optional[{spec.name}Config] = None):
        self.config = config or {spec.name}Config()
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )
        self._rate_limiter = asyncio.Semaphore(self.config.rate_limit)

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        async with self._rate_limiter:
            for attempt in range(self.config.max_retries):
                try:
                    response = await self._client.request(method, path, **kwargs)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code >= 500 and attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except Exception:
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise

    # Endpoint methods would be generated here
    # Example:
    # async def get_user(self, user_id: str) -> Dict[str, Any]:
    #     return await self._request("GET", f"/users/{user_id}")

    async def close(self):
        await self._client.aclose()
'''

    def _render_base_webhook(self, spec: WebhookSpec, context: Dict) -> str:
        return f'''"""
Webhook handler for {spec.provider}
Auto-generated webhook receiver with signature verification
"""

from fastapi import APIRouter, Request, HTTPException, Header
import hmac
import hashlib
import os

router = APIRouter(prefix="{spec.path}")

# Load secret from environment
WEBHOOK_SECRET = os.getenv("{spec.secret_env_var}")
if not WEBHOOK_SECRET:
    raise ValueError("Missing {spec.secret_env_var} environment variable")

def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify webhook signature"""
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("")
async def handle_{spec.name}_webhook(
    request: Request,
    {spec.secret_header.lower().replace('-', '_')}: str = Header(None),
):
    if not {spec.secret_header.lower().replace('-', '_')}:
        raise HTTPException(status_code=401, detail="Missing signature header")

    body = await request.body()
    if not verify_signature(body, {spec.secret_header.lower().replace('-', '_')}):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and handle event
    event = await request.json()
    event_type = event.get("type")

    if event_type not in {spec.events}:
        return {{"status": "ignored", "event": event_type}}

    # TODO: Implement event handling logic
    return {{"status": "ok", "event": event_type}}
'''

    def _render_base_oauth(self, spec: OAuthSpec, context: Dict, template_type: str) -> str:
        if template_type == "authorize":
            return f'''"""
OAuth authorize endpoint for {spec.provider}
"""
from fastapi import APIRouter, Request
from urllib.parse import urlencode
import secrets

router = APIRouter(prefix="/auth/{spec.provider}")

@router.get("/authorize")
async def {spec.provider}_authorize(request: Request):
    state = secrets.token_urlsafe(32)
    pkce_verifier = secrets.token_urlsafe(32)
    pkce_challenge = secrets.token_urlsafe(32)  # TODO: Proper PKCE

    request.session["oauth_state"] = state
    request.session["pkce_verifier"] = pkce_verifier

    params = {{
        "client_id": "{spec.client_id_env}",
        "redirect_uri": "{spec.redirect_uri}",
        "scope": " ".join({spec.scopes}),
        "response_type": "code",
        "state": state,
        "code_challenge": pkce_challenge,
        "code_challenge_method": "S256",
    }}

    auth_url = f"{{spec.authorize_url}}?{{urlencode(params)}}"
    return {{"auth_url": auth_url}}
'''
        elif template_type == "callback":
            return f'''"""
OAuth callback endpoint for {spec.provider}
"""
from fastapi import APIRouter, Request, HTTPException
import httpx

router = APIRouter(prefix="/auth/{spec.provider}")

@router.get("/callback")
async def {spec.provider}_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {{error}}")

    if state != request.session.get("oauth_state"):
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "{spec.token_url}",
            data={{
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": "{spec.redirect_uri}",
                "client_id": "{spec.client_id_env}",
                "client_secret": "{{{{ secrets.{spec.client_secret_env} }}}}",
                "code_verifier": request.session.get("pkce_verifier"),
            }},
            headers={{"Accept": "application/json"}},
        )

    token_data = response.json()

    # Fetch user info
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "{spec.user_info_url or spec.token_url}",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )

    return {{"access_token": token_data["access_token"], "user": user_response.json()}}
'''
        return f"# {spec.provider} OAuth {template_type} - TODO: implement"

    def _render_base_sdk(self, spec: SDKSpec, context: Dict) -> str:
        return f'''/**
 * {spec.name} SDK v{spec.version}
 * Auto-generated SDK wrapper
 */

export class {spec.name}SDK {{
  constructor(config: {{ apiKey: string; baseUrl?: string }}) {{
    this.config = config;
  }}

  // Additional methods would be generated here
}}
'''

    def _render_base_event_consumer(self, name: str, context: Dict) -> str:
        return f'''"""
Event consumer for {name}
"""
import asyncio
from typing import Callable, Any

class {name}Consumer:
    def __init__(self, topic: str, group_id: str = "default"):
        self.topic = topic
        self.group_id = group_id
        self._running = False

    async def start(self, handler: Callable[[dict], Any]):
        """Start consuming messages"""
        self._running = True
        # TODO: Implement consumer logic (Kafka, RabbitMQ, Redis Streams)
        pass

    async def stop(self):
        self._running = False
'''

    def _render_base_event_publisher(self, name: str, context: Dict) -> str:
        return f'''"""
Event publisher for {name}
"""
import json
from typing: Any, Dict

class {name}Publisher:
    def __init__(self, topic: str):
        self.topic = topic

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """Publish an event to the message queue"""
        message = {{
            "event_type": event_type,
            "payload": payload,
            "timestamp": "2024-01-01T00:00:00Z",  # TODO: Use actual timestamp
        }}
        # TODO: Implement publishing logic (Kafka, RabbitMQ, Redis Streams)
        return True
'''


def create_integration_generator(
    project: Project,
    workspace: Optional[WorkspaceManager] = None,
    template_root: Optional[str] = None,
) -> IntegrationGenerator:
    return IntegrationGenerator(project, workspace, template_root)