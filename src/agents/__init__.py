"""
Agents package — code generators for specialist agent roles.

Each generator produces code artifacts for a specific domain:
- FrontendGenerator: React/Next.js/Vue/Svelte components, pages, hooks
- BackendGenerator: API routes, database models, services, auth
- IntegrationGenerator: Third-party API clients, webhooks, SDKs
"""

from .frontend_generator import FrontendGenerator
from .backend_generator import BackendGenerator
from .integration_generator import IntegrationGenerator

__all__ = ["FrontendGenerator", "BackendGenerator", "IntegrationGenerator"]