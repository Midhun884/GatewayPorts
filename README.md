# 🚇 SSH Tunnel Manager

> A lightweight desktop application that manages **persistent SSH port forwarding**
> with a clean GUI. Create, edit, and monitor multiple SSH tunnels without
> memorizing long `ssh -L` and `ssh -R` commands.

<p align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![AsyncSSH](https://img.shields.io/badge/AsyncSSH-Backend-2f6fed)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-1f9d55)
![Platform](https://img.shields.io/badge/Linux-Desktop-orange?logo=linux)


</p>

---

## ✨ Overview

SSH Tunnel Manager provides a simple desktop interface for creating and managing
SSH port forwards.

Instead of opening several terminal windows and remembering complicated SSH
commands, the application keeps **one persistent SSH connection** alive and
creates any number of **local** and **remote** tunnels inside it.

When the SSH connection drops, it reconnects automatically and restores every
enabled tunnel.

---
<img width="882" height="674" alt="image" src="https://github.com/user-attachments/assets/61424538-c6d1-4937-81c9-36d2871ae647" />

## 📸 Features

### 🔄 Persistent SSH Connection

- One SSH session shared across every tunnel
- Automatic reconnect after disconnects
- SSH keepalive support
- Restores all enabled tunnels automatically

---

### 🌍 Local & Remote Port Forwarding

Supports both standard SSH forwarding modes.

| Type | Equivalent | Description |
|------|------------|-------------|
| **Local** | `ssh -L` | Access services that are only reachable from the remote server |
| **Remote** | `ssh -R` | Expose a service running on your local machine through the SSH server |

No terminal commands required.

---

### 🔑 SSH Config Integration

Automatically reads your existing SSH configuration.

Supports:

- `~/.ssh/config`
- `/etc/ssh/ssh_config`
- `Include` directives
- Host aliases
- User
- IdentityFile
- Port

Simply choose one of your configured hosts from the dropdown.

---

### 📊 Live Tunnel Status

Every tunnel displays its current state.

- 🟢 Connected
- 🟡 Connecting
- 🔴 Error
- ⚪ Disabled

Errors are shown per tunnel, making it easy to identify failures without affecting
working tunnels.

---

### 💾 Persistent Configuration

Everything is saved automatically.

```
~/.config/
└── ssh-tunnel-manager/
    └── config.json
```

- Tunnel list
- Connection settings
- Enabled/disabled state

Configuration files are written with secure **0600** permissions.

---

### 🛑 Clean Shutdown

Closing the application:

- Stops every tunnel
- Closes listeners
- Disconnects SSH
- Leaves no background processes running

---

# 🧠 How It Works

SSH Tunnel Manager keeps a **single SSH connection** alive.

Every tunnel is attached to that connection.

```
                 SSH Connection
        ┌──────────────────────────────┐
        │                              │
        │      SSH Tunnel Manager      │
        │                              │
        └──────────────────────────────┘
                    │
                    │
                    ▼
              SSH Server
           /      |      \
          /       |       \
     Tunnel    Tunnel   Tunnel
```

One connection.

Multiple forwards.

Automatic recovery.

---

# 🔀 Tunnel Types

## Remote Forward (`-R`)

Expose something running on **your computer** so it can be reached from the SSH server.

```
Your Computer                     SSH Server

localhost:5000  ─────────────►  server:9000
```

Useful for:

- Development servers
- Local dashboards
- APIs
- Web applications

---

## Local Forward (`-L`)

Reach services that only exist on the server's private network.

```
Your Computer                     SSH Server

localhost:8080 ◄───────────── internal-service:8080
```

Useful for:

- Databases
- Internal web interfaces
- Private APIs
- Administrative dashboards

---

# 🚀 Installation

## Requirements

- Python 3.10+
- Tkinter

Ubuntu / Debian:

```bash
sudo apt install python3-tk
```

---

## Setup

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

Run:

```bash
python ssh_tunnel_manager.py
```

---

# 🎮 Using the Application

## 1. Select a Host

Choose any host from your SSH configuration.

```
myserver
production
aws
raspberrypi
office
```

You can also type a hostname manually.

---

## 2. Connect

Press **Connect**.

The application establishes one SSH session.

---

## 3. Add Tunnels

Create as many forwards as you need.

Example:

| Type | Local | Remote |
|------|-------|--------|
| Remote | localhost:5000 | server:9000 |
| Local | localhost:5432 | remote-db:5432 |
| Local | localhost:8080 | internal-api:8080 |

---

## 4. Monitor

Watch tunnel status update in real time.

No terminal windows required.

---

# 📁 Project Structure

```
.
├── ssh_tunnel_manager.py
├── gui.py
├── ssh_manager.py
├── tunnel_config.py
├── requirements.txt
├── tests
│   └── ...
└── README.md
```

### `ssh_tunnel_manager.py`

Application entry point.

---

### `gui.py`

Tkinter interface.

Responsible for:

- Connection controls
- Tunnel editor
- Status display
- Notifications

---

### `ssh_manager.py`

AsyncSSH backend.

Responsible for:

- SSH connection
- Reconnect loop
- Keepalive
- Port forwarding

---

### `tunnel_config.py`

Configuration layer.

Responsible for:

- JSON persistence
- Tunnel model
- SSH config parsing
- Settings migration

---

### `tests/`

Unit tests for configuration and persistence.

---

# ⚠ Troubleshooting

## Tunnel says **Connected** but doesn't work

The SSH connection itself is alive, but the forwarding request failed.

Common causes include:

### Port already in use

Another process is already listening on that port.

---

### Server disabled forwarding

```
AllowTcpForwarding no
```

in `sshd_config`.

---

### Remote wildcard binding

For remote forwards using `0.0.0.0`, the server typically requires:

```
GatewayPorts yes
```

or

```
GatewayPorts clientspecified
```

---

### Privileged ports

Ports below **1024** usually require elevated privileges on the machine where the listener is created.

---

The built-in log panel displays the exact SSH error returned by the server.

---

# ⚙ Configuration

Configuration is stored in:

```
$XDG_CONFIG_HOME/ssh-tunnel-manager/config.json
```

or

```
~/.config/ssh-tunnel-manager/config.json
```

The file contains:

- Saved hosts
- Tunnel definitions
- Window settings
- Connection preferences

Older configuration formats are migrated automatically.

---

# 🧪 Running Tests

```bash
python -m unittest discover -s tests -v
```

---

# ❤️ Why SSH Tunnel Manager?

- 🖥 Native desktop application
- 🚀 Lightweight and fast
- 🔒 Uses standard SSH authentication
- 🔄 Automatic reconnect
- 📡 Multiple tunnels over one connection
- 📂 Uses your existing SSH configuration
- 💾 Persistent settings
- 🎯 No terminal commands to remember

---
