"""
DevServerManager — manages development servers for live preview.

Supports: Vite, Next.js, Expo, SvelteKit, Nuxt, Remix, Django, FastAPI, Express.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class DevServer:
    """Represents a running development server."""
    project_id: str
    framework: str
    port: int
    process: subprocess.Popen
    url: str
    started_at: float = field(default_factory=time.time)
    logs: List[str] = field(default_factory=list)


@dataclass
class DevServerConfig:
    """Configuration for a development server instance."""
    project_id: str
    framework: str = "vite"
    port: int = 3000
    host: str = "0.0.0.0"
    env: Dict[str, str] = field(default_factory=dict)
    idle_timeout: int = 3600
    command: Optional[List[str]] = None


class DevServerStatus:
    """Status of a dev server lifecycle."""
    PENDING = "pending"
    STARTING = "starting"
    READY = "ready"
    ERROR = "error"
    STOPPED = "stopped"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.PENDING, cls.STARTING, cls.READY, cls.ERROR, cls.STOPPED]


class PortAllocator:
    """Thread-safe allocator for dev server ports."""

    def __init__(self, base_port: int = 3001, max_port: int = 65535):
        self._base_port = base_port
        self._next_port = base_port
        self._allocated: set[int] = set()
        self._lock = threading.Lock()
        self._max_port = max_port

    def allocate(self) -> int:
        with self._lock:
            while self._next_port in self._allocated and self._next_port < self._max_port:
                self._next_port += 1
            port = self._next_port
            self._allocated.add(port)
            self._next_port += 1
            return port

    def release(self, port: int) -> None:
        with self._lock:
            self._allocated.discard(port)

    def is_allocated(self, port: int) -> bool:
        with self._lock:
            return port in self._allocated

    def reset(self) -> None:
        with self._lock:
            self._allocated.clear()
            self._next_port = self._base_port


_port_allocator_instance: Optional[PortAllocator] = None


def get_port_allocator(base_port: int = 3001) -> PortAllocator:
    """Get or create the global PortAllocator instance."""
    global _port_allocator_instance
    if _port_allocator_instance is None:
        _port_allocator_instance = PortAllocator(base_port=base_port)
    return _port_allocator_instance


def create_dev_server_manager(
    base_port: int = 3001,
    max_servers: int = 50,
    idle_timeout: int = 3600,
    preview_apps_dir: str = "./preview_apps",
) -> DevServerManager:
    """Factory for creating a configured DevServerManager."""
    return DevServerManager(
        base_port=base_port,
        max_servers=max_servers,
        idle_timeout=idle_timeout,
        preview_apps_dir=preview_apps_dir,
    )


class DevServerManager:
    """
    Manages ephemeral development servers for live preview of generated apps.
    
    Each project gets its own isolated dev server on a unique port.
    Servers are automatically cleaned up when the project is deleted or idle.
    """
    
    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        "nextjs": [
            r"package\.json.*next",
            r"next\.config\.(js|ts|mjs)",
            r"app/.*page\.(tsx|jsx)",
            r"pages/.*\.(tsx|jsx)",
        ],
        "vite": [
            r"vite\.config\.(js|ts|mjs)",
            r"package\.json.*vite",
            r"index\.html",
        ],
        "remix": [
            r"remix\.config\.(js|ts)",
            r"package\.json.*@remix-run",
            r"app/.*\.tsx",
        ],
        "sveltekit": [
            r"svelte\.config\.(js|ts)",
            r"package\.json.*@sveltejs/kit",
            r"src/routes/",
        ],
        "nuxt": [
            r"nuxt\.config\.(js|ts)",
            r"package\.json.*nuxt",
            r"pages/.*\.vue",
        ],
        "expo": [
            r"app\.json",
            r"package\.json.*expo",
            r"App\.(tsx|jsx)",
        ],
        "django": [
            r"manage\.py",
            r"requirements\.txt.*django",
            r"settings\.py",
        ],
        "fastapi": [
            r"main\.py.*fastapi",
            r"requirements\.txt.*fastapi",
            r"uvicorn",
        ],
        "express": [
            r"package\.json.*express",
            r"server\.js",
            r"app\.js",
            r"index\.js",
        ],
    }
    
    # Default ports for each framework (will be dynamically assigned)
    FRAMEWORK_PORTS = {
        "nextjs": 3000,
        "vite": 5173,
        "remix": 3000,
        "sveltekit": 5173,
        "nuxt": 3000,
        "expo": 8081,
        "django": 8000,
        "fastapi": 8000,
        "express": 3000,
    }
    
    # Start commands for each framework
    FRAMEWORK_COMMANDS = {
        "nextjs": ["npm", "run", "dev"],
        "vite": ["npm", "run", "dev"],
        "remix": ["npm", "run", "dev"],
        "sveltekit": ["npm", "run", "dev"],
        "nuxt": ["npm", "run", "dev"],
        "expo": ["npx", "expo", "start", "--web"],
        "django": ["python", "manage.py", "runserver", "0.0.0.0:8000"],
        "fastapi": ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        "express": ["npm", "run", "dev"],
    }

    def __init__(
        self,
        base_port: int = 3001,
        max_servers: int = 50,
        idle_timeout: int = 3600,  # 1 hour
        preview_apps_dir: str = "./preview_apps",
    ):
        self.base_port = base_port
        self.max_servers = max_servers
        self.idle_timeout = idle_timeout
        self.preview_apps_dir = Path(preview_apps_dir).resolve()
        self.preview_apps_dir.mkdir(parents=True, exist_ok=True)
        
        self._servers: Dict[str, DevServer] = {}
        self._port_allocator = base_port
        self._lock = threading.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
    def _allocate_port(self) -> int:
        """Allocate a unique port for a new server."""
        with self._lock:
            port = self._port_allocator
            self._port_allocator += 1
            # Check if port is already in use
            while any(s.port == port for s in self._servers.values()):
                port = self._port_allocator
                self._port_allocator += 1
            return port

    def _detect_framework(self, project_path: Path) -> Optional[str]:
        """Detect the framework used in a project directory."""
        if not project_path.exists():
            return None
            
        # Check for package.json first (most common)
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                import json
                with open(package_json) as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                
                # Check dependencies for framework signatures
                if "next" in deps:
                    return "nextjs"
                if "vite" in deps:
                    return "vite"
                if "@remix-run/react" in deps or "@remix-run/node" in deps:
                    return "remix"
                if "@sveltejs/kit" in deps:
                    return "sveltekit"
                if "nuxt" in deps:
                    return "nuxt"
                if "expo" in deps:
                    return "expo"
                if "express" in deps:
                    return "express"
            except Exception:
                pass
        
        # Check for config files
        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if list(project_path.rglob(pattern)):
                    return framework
        
        # Check for Python frameworks
        if (project_path / "requirements.txt").exists():
            try:
                with open(project_path / "requirements.txt") as f:
                    reqs = f.read().lower()
                if "fastapi" in reqs or "uvicorn" in reqs:
                    return "fastapi"
                if "django" in reqs:
                    return "django"
            except Exception:
                pass
        
        return None

    async def start_server(
        self,
        project_id: str,
        project_path: Path,
        framework: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> DevServer:
        """
        Start a development server for a project.
        
        Args:
            project_id: Unique identifier for the project
            project_path: Path to the project directory
            framework: Optional framework override (auto-detected if not provided)
            env: Optional environment variables
            
        Returns:
            DevServer instance with connection details
        """
        # Check if server already exists
        if project_id in self._servers:
            server = self._servers[project_id]
            # Verify it's still running
            if server.process.poll() is None:
                return server
            else:
                # Process died, clean up
                del self._servers[project_id]
        
        # Check max servers limit
        if len(self._servers) >= self.max_servers:
            # Remove oldest idle server
            await self._cleanup_idle()
            if len(self._servers) >= self.max_servers:
                raise RuntimeError("Maximum number of preview servers reached")
        
        # Detect framework
        if framework is None:
            framework = self._detect_framework(project_path)
        
        if framework is None:
            # Default to a simple static server if no framework detected
            framework = "vite"
        
        # Get port and command
        port = self._allocate_port()
        command = self.FRAMEWORK_COMMANDS.get(framework, ["npm", "run", "dev"])
        default_port = self.FRAMEWORK_PORTS.get(framework, 3000)
        
        # Prepare environment
        server_env = os.environ.copy()
        server_env.update({
            "PORT": str(port),
            "HOST": "0.0.0.0",
        })
        if env:
            server_env.update(env)
        
        # Start the process
        try:
            process = subprocess.Popen(
                command,
                cwd=project_path,
                env=server_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start {framework} server: {e}")
        
        # Create server object
        server = DevServer(
            project_id=project_id,
            framework=framework,
            port=port,
            process=process,
            url=f"http://localhost:{port}",
        )
        
        self._servers[project_id] = server
        
        # Start log reader thread
        threading.Thread(target=self._read_logs, args=(server,), daemon=True).start()
        
        # Wait for server to be ready
        await self._wait_for_ready(server)
        
        # Start cleanup task if not running
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        return server

    def _read_logs(self, server: DevServer) -> None:
        """Read server logs in a background thread."""
        try:
            for line in server.process.stdout:
                server.logs.append(line.rstrip())
                # Keep only last 1000 lines
                if len(server.logs) > 1000:
                    server.logs = server.logs[-1000:]
        except Exception:
            pass

    async def _wait_for_ready(self, server: DevServer, timeout: float = 60.0) -> None:
        """Wait for the development server to be ready."""
        start_time = time.time()
        url = server.url
        
        # Framework-specific ready checks
        ready_paths = {
            "nextjs": "/",
            "vite": "/",
            "remix": "/",
            "sveltekit": "/",
            "nuxt": "/",
            "expo": "/",
            "django": "/",
            "fastapi": "/docs",
            "express": "/",
        }
        ready_path = ready_paths.get(server.framework, "/")
        
        async with httpx.AsyncClient() as client:
            while time.time() - start_time < timeout:
                if server.process.poll() is not None:
                    # Process exited
                    raise RuntimeError(f"Server process exited with code {server.process.returncode}")
                
                try:
                    response = await client.get(f"{url}{ready_path}", timeout=5.0)
                    if response.status_code < 500:
                        return  # Server is ready
                except Exception:
                    pass
                
                await asyncio.sleep(1.0)
        
        raise TimeoutError(f"Server {server.framework} on port {server.port} did not become ready within {timeout}s")

    def stop_server(self, project_id: str) -> bool:
        """Stop a development server."""
        if project_id not in self._servers:
            return False
        
        server = self._servers[project_id]
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(server.process.pid), signal.SIGTERM)
            else:
                server.process.terminate()
            server.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(os.getpgid(server.process.pid), signal.SIGKILL)
                else:
                    server.process.kill()
                server.process.wait(timeout=5)
            except Exception:
                pass
        except Exception:
            pass
        
        del self._servers[project_id]
        return True

    def get_server(self, project_id: str) -> Optional[DevServer]:
        """Get a server by project ID."""
        return self._servers.get(project_id)

    def list_servers(self) -> List[DevServer]:
        """List all running servers."""
        return list(self._servers.values())

    async def _cleanup_idle(self) -> None:
        """Remove idle servers."""
        now = time.time()
        to_remove = []
        
        for project_id, server in self._servers.items():
            # Check if process is still alive
            if server.process.poll() is not None:
                to_remove.append(project_id)
                continue
            
            # Check idle timeout
            if now - server.started_at > self.idle_timeout:
                to_remove.append(project_id)
        
        for project_id in to_remove:
            self.stop_server(project_id)

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up idle servers."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def shutdown(self) -> None:
        """Shutdown all servers and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        for project_id in list(self._servers.keys()):
            self.stop_server(project_id)


# Global instance
_dev_server_manager: Optional[DevServerManager] = None


def get_dev_server_manager() -> DevServerManager:
    """Get or create the global DevServerManager instance."""
    global _dev_server_manager
    if _dev_server_manager is None:
        _dev_server_manager = DevServerManager()
    return _dev_server_manager