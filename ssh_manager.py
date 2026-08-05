#!/usr/bin/env python3
"""Async SSH backend: owns the connection, keepalive/reconnect loop, and port forwarders."""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Callable

from tunnel_config import Settings, Tunnel

try:
    import asyncssh
except ImportError:  # The GUI can still start and explain what is missing.
    asyncssh = None

ASYNCSSH_AVAILABLE = asyncssh is not None


class SSHManager:
    """Own the asyncio loop, SSH connection, listeners, and reconnect cycle."""

    def __init__(self, notify: Callable[[str, object], None]):
        self.notify = notify
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.desired = False
        self.settings: Settings | None = None
        self.connection = None
        self.listeners: dict[int, object] = {}
        self.task = None

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def connect(self, settings: Settings) -> None:
        self.settings = settings
        self.desired = True
        if not self.task or self.task.done():
            self.task = asyncio.run_coroutine_threadsafe(self._connection_loop(), self.loop)

    def disconnect(self) -> None:
        self.desired = False
        asyncio.run_coroutine_threadsafe(self._close(), self.loop)

    def sync_tunnels(self, tunnels: list[Tunnel]) -> None:
        if self.settings:
            self.settings.tunnels = tunnels
        asyncio.run_coroutine_threadsafe(self._apply_tunnels(), self.loop)

    def reopen_tunnel(self, tunnel_id: int) -> None:
        asyncio.run_coroutine_threadsafe(self._reopen_tunnel(tunnel_id), self.loop)

    async def _reopen_tunnel(self, tunnel_id: int) -> None:
        listener = self.listeners.pop(tunnel_id, None)
        if listener:
            listener.close()
        await self._apply_tunnels()

    async def _connection_loop(self) -> None:
        while self.desired:
            try:
                self.notify("connection", "connecting")
                cfg = self.settings
                kwargs = {"host": cfg.host, "port": cfg.port, "keepalive_interval": 20, "keepalive_count_max": 3}
                if cfg.user:
                    kwargs["username"] = cfg.user
                if cfg.key:
                    kwargs["client_keys"] = [os.path.expanduser(cfg.key)]
                self.connection = await asyncssh.connect(**kwargs)
                self.notify("connection", "connected")
                await self._apply_tunnels()
                await self.connection.wait_closed()
                if self.desired:
                    raise ConnectionError("SSH connection closed")
            except Exception as exc:
                self.connection = None
                self.listeners.clear()
                if self.desired:
                    self.notify("log", f"Connection lost: {exc}. Retrying in 2 seconds")
                    self.notify("connection", "reconnecting")
                    await asyncio.sleep(2)
        self.notify("connection", "disconnected")

    async def _apply_tunnels(self) -> None:
        if not self.connection or self.connection.is_closed() or not self.settings:
            return
        wanted = {t.id: t for t in self.settings.tunnels if t.enabled}
        for tunnel_id in list(self.listeners):
            if tunnel_id not in wanted:
                self.listeners.pop(tunnel_id).close()
                self.notify("tunnel", (tunnel_id, "Disabled"))
        for tunnel_id, tunnel in wanted.items():
            if tunnel_id in self.listeners:
                continue
            self.notify("tunnel", (tunnel_id, "Connecting"))
            try:
                if tunnel.direction == "local":
                    listener = await self.connection.forward_local_port(
                        "127.0.0.1", tunnel.listen_port, tunnel.dest_host, tunnel.dest_port
                    )
                    self.notify("log", f"Tunnel 127.0.0.1:{tunnel.listen_port} opened → server's {tunnel.dest_host}:{tunnel.dest_port}")
                else:
                    listener = await self.connection.forward_remote_port(
                        "", tunnel.listen_port, tunnel.dest_host, tunnel.dest_port
                    )
                    self.notify("log", f"Tunnel {tunnel.listen_port} opened → {tunnel.dest_host}:{tunnel.dest_port}")
                self.listeners[tunnel_id] = listener
                self.notify("tunnel", (tunnel_id, "Connected"))
            except Exception as exc:
                self.notify("tunnel", (tunnel_id, "Error"))
                self.notify("log", f"Tunnel {tunnel.listen_port} failed: {exc}")

    async def _close(self) -> None:
        for listener in self.listeners.values():
            listener.close()
        self.listeners.clear()
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
        self.connection = None
        self.notify("connection", "disconnected")

    def shutdown(self) -> None:
        self.desired = False
        future = asyncio.run_coroutine_threadsafe(self._close(), self.loop)
        try:
            future.result(timeout=3)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
