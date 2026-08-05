#!/usr/bin/env python3
"""Settings and Tunnel data model, JSON persistence, and OpenSSH config discovery."""

from __future__ import annotations

import glob
import json
import os
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ssh-tunnel-manager"
CONFIG_PATH = APP_DIR / "config.json"
SSH_CONFIG_PATHS = (Path.home() / ".ssh" / "config", Path("/etc/ssh/ssh_config"))


@dataclass
class Tunnel:
    id: int
    name: str
    enabled: bool
    listen_port: int
    direction: str = "remote"  # "remote": expose a local service on the server (-R). "local": expose a remote service here (-L).
    dest_host: str = "127.0.0.1"
    dest_port: int = 0
    description: str = ""


@dataclass
class Settings:
    host: str = ""
    user: str = ""
    key: str = ""
    port: int = 22
    auto_connect: bool = False
    tunnels: list[Tunnel] = field(default_factory=list)


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    if not path.exists():
        return Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["tunnels"] = [Tunnel(**_migrate_tunnel(item)) for item in raw.get("tunnels", [])]
        return Settings(**{k: v for k, v in raw.items() if k in Settings.__dataclass_fields__})
    except (OSError, ValueError, TypeError):
        return Settings()


def _migrate_tunnel(item: dict) -> dict:
    """Upgrade tunnels saved before the local/remote direction field existed."""
    item = dict(item)
    if "listen_port" not in item and "remote_port" in item:
        item["listen_port"] = item.pop("remote_port")
        item.setdefault("direction", "remote")
    if "dest_host" not in item and "local_host" in item:
        item["dest_host"] = item.pop("local_host")
    if "dest_port" not in item and "local_port" in item:
        item["dest_port"] = item.pop("local_port")
    return item


def save_settings(settings: Settings, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _expand_includes(value: str, base: Path) -> list[Path]:
    paths: list[Path] = []
    for item in shlex.split(value):
        expanded = os.path.expanduser(item)
        if not os.path.isabs(expanded):
            expanded = str(base / expanded)
        paths.extend(Path(p) for p in sorted(glob.glob(expanded)))
    return paths


def read_ssh_hosts(paths: tuple[Path, ...] = SSH_CONFIG_PATHS) -> dict[str, dict[str, str]]:
    """Return concrete Host entries from OpenSSH configs, including Include files.

    Wildcards and negated patterns are defaults/match rules, not selectable devices.
    """
    hosts: dict[str, dict[str, str]] = {}
    visited: set[Path] = set()

    def parse(path: Path) -> None:
        try:
            resolved = path.expanduser().resolve()
            if resolved in visited:
                return
            visited.add(resolved)
            lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        current: list[str] = []
        for raw_line in lines:
            try:
                parts = shlex.split(raw_line, comments=True)
            except ValueError:
                continue
            if not parts:
                continue
            key, values = parts[0].lower(), parts[1:]
            if key == "include" and values:
                for included in _expand_includes(" ".join(values), resolved.parent):
                    parse(included)
            elif key == "host":
                current = [v for v in values if not v.startswith("!") and not any(c in v for c in "*?")]
                for alias in current:
                    hosts.setdefault(alias, {"alias": alias, "hostname": alias, "user": "", "identityfile": "", "port": "22"})
            elif key == "match":
                current = []
            elif key in {"hostname", "user", "identityfile", "port"} and values:
                for alias in current:
                    # OpenSSH uses the first obtained value for these options.
                    entry = hosts[alias]
                    default = alias if key == "hostname" else ("22" if key == "port" else "")
                    if entry[key] == default or not entry[key]:
                        entry[key] = os.path.expanduser(values[0]) if key == "identityfile" else values[0]

    # User config is intentionally parsed first, matching OpenSSH precedence.
    for config_path in paths:
        parse(config_path)
    return hosts
