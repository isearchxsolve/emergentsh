"""
HMRClient — Hot Module Replacement WebSocket client for live preview.

Connects to dev server HMR endpoint and handles reload notifications.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

import websockets


@dataclass
class HMRMessage:
    """Parsed HMR message."""
    type: str
    payload: Any = None


class HMRClient:
    """
    WebSocket client for Hot Module Replacement.

    Connects to dev server HMR endpoint and handles:
    - Full page reload
    - CSS hot update
    - Module hot update
    - Error/connected/disconnected events
    """

    def __init__(
        self,
        url: str,
        on_reload: Optional[Callable[[], None]] = None,
        on_update: Optional[Callable[[dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
    ):
        self._url = url
        self._on_reload = on_reload
        self._on_update = on_update
        self._on_error = on_error
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_delay = 2.0
        self._max_reconnect_delay = 30.0

    async def connect(self) -> None:
        """Connect to the HMR WebSocket server."""
        if self._running:
            return

        self._running = True
        await self._connect_loop()

    async def disconnect(self) -> None:
        """Disconnect from the HMR server."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _connect_loop(self) -> None:
        """Main connection loop with auto-reconnect."""
        while self._running:
            try:
                await self._connect()
                await self._listen()
            except Exception as e:
                if self._on_error:
                    self._on_error(str(e))

            if self._running:
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 1.5, self._max_reconnect_delay)

    async def _connect(self) -> None:
        """Establish WebSocket connection."""
        self._ws = await websockets.connect(
            self._url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )

        if self._on_connected:
            self._on_connected()

    async def _listen(self) -> None:
        """Listen for messages from the server."""
        if not self._ws:
            return

        async for message in self._ws:
            try:
                await self._handle_message(message)
            except Exception as e:
                if self._on_error:
                    self._on_error(f"Error handling HMR message: {e}")

    async def _handle_message(self, message: str | bytes) -> None:
        """Parse and handle incoming HMR message."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type", "")

        if msg_type == "connected":
            # Server acknowledged connection
            pass

        elif msg_type == "reload":
            if self._on_reload:
                self._on_reload()

        elif msg_type == "update":
            # Module update
            if self._on_update:
                self._on_update(data.get("payload", {}))

        elif msg_type == "css-update":
            # CSS hot reload
            pass

        elif msg_type == "error":
            if self._on_error:
                self._on_error(data.get("message", "Unknown HMR error"))

        elif msg_type == "ping":
            # Heartbeat
            if self._ws:
                await self._ws.send(json.dumps({"type": "pong"}))


def create_hmr_client(
    port: int,
    host: str = "localhost",
    path: str = "/hmr",
    **callbacks,
) -> HMRClient:
    """
    Create an HMR client for a dev server.

    Args:
        port: Dev server port
        host: Dev server host
        path: HMR WebSocket path
        **callbacks: Event callbacks (on_reload, on_update, on_error, etc.)

    Returns:
        Configured HMRClient instance
    """
    protocol = "wss" if port == 443 else "ws"
    url = f"{protocol}://{host}:{port}{path}"
    return HMRClient(url, **callbacks)


# ----------------------------------------------------------------------
# Browser-side HMR injection script
# ----------------------------------------------------------------------

HMR_INJECTION_SCRIPT = """
(function() {
    if (window.__hmr_connected) return;
    window.__hmr_connected = true;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/hmr`);

    ws.onopen = () => console.log('[HMR] Connected');
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'reload') {
                console.log('[HMR] Reloading page...');
                window.location.reload();
            } else if (data.type === 'css-update') {
                // Hot reload CSS without full reload
                const links = document.querySelectorAll('link[rel="stylesheet"]');
                links.forEach(link => {
                    const href = link.href.split('?')[0];
                    link.href = href + '?' + Date.now();
                });
            } else if (data.type === 'update') {
                console.log('[HMR] Module update:', data.payload);
                // Module hot update would go here
            }
        } catch (e) {
            console.error('[HMR] Message parse error:', e);
        }
    });

    ws.onclose = () => {
        console.log('[HMR] Disconnected, reconnecting in 2s...');
        setTimeout(() => window.location.reload(), 2000);
    };

    ws.onerror = (err) => console.error('[HMR] WebSocket error:', err);
})();
"""