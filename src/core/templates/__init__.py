"""
Templates Package — Jinja2-based code generation templates.

Structure:
  templates/
    base/                    # Shared base templates
      config/
      docker/
      git/
      vscode/
    nextjs-tailwind/         # Next.js + Tailwind
    nextjs-shadcn/           # Next.js + shadcn/ui
    vite-react-tailwind/     # Vite + React + Tailwind
    expo-react-native/       # Expo + React Native
    fastapi-react/           # FastAPI + React
    django-react/            # Django + React
    sveltekit-tailwind/      # SvelteKit + Tailwind
    nuxt-tailwind/           # Nuxt 3 + Tailwind
    remix-tailwind/          # Remix + Tailwind
"""

from .engine import (
    TemplateEngine,
    StackTemplateLoader,
    get_template_engine,
    get_stack_loader,
    build_project_context,
    build_component_context,
    build_api_route_context,
)

__all__ = [
    "TemplateEngine",
    "StackTemplateLoader",
    "get_template_engine",
    "get_stack_loader",
    "build_project_context",
    "build_component_context",
    "build_api_route_context",
]