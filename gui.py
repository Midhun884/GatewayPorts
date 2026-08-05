#!/usr/bin/env python3
"""Tkinter desktop UI: connection panel, tunnel table, edit dialog, and log."""

from __future__ import annotations

import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from ssh_manager import ASYNCSSH_AVAILABLE, SSHManager
from tunnel_config import Tunnel, load_settings, read_ssh_hosts, save_settings

PALETTE = {
    "bg": "#f4f5f7", "surface": "#ffffff", "border": "#d7dbe0", "text": "#1f2430", "muted": "#6b7280",
    "accent": "#2f6fed", "accent_active": "#255ed1", "success": "#1f9d55", "warning": "#c98a02", "error": "#d64545",
}
CONNECTION_STYLES = {
    "connected": ("🟢 Connected", "Connected.TLabel"), "connecting": ("🟡 Connecting", "Connecting.TLabel"),
    "reconnecting": ("🟡 Reconnecting", "Connecting.TLabel"), "disconnected": ("⚪ Disconnected", "Disconnected.TLabel"),
}
TUNNEL_STATUS_TAGS = {
    "Connected": "success", "Connecting": "warning", "Error": "error", "Disabled": "muted", "Pending": "muted",
}
DIRECTIONS = {
    "remote": "Expose a local service on the server (-R)",
    "local": "Access a remote service from here (-L)",
}


class TunnelDialog(tk.Toplevel):
    def __init__(self, parent, tunnel: Tunnel | None = None):
        super().__init__(parent)
        self.title("Edit Tunnel" if tunnel else "Add Tunnel")
        self.resizable(False, False)
        self.result = None
        values = tunnel or Tunnel(0, "", True, 9000, "remote", "127.0.0.1", 5000)
        self.vars = {
            "name": tk.StringVar(value=values.name), "listen": tk.StringVar(value=str(values.listen_port)),
            "host": tk.StringVar(value=values.dest_host), "port": tk.StringVar(value=str(values.dest_port)),
            "description": tk.StringVar(value=values.description), "enabled": tk.BooleanVar(value=values.enabled),
            "direction": tk.StringVar(value=DIRECTIONS[values.direction]),
        }
        form = ttk.Frame(self, padding=16); form.grid()
        ttk.Label(form, text="Name").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["name"], width=34).grid(row=0, column=1, pady=4)
        ttk.Label(form, text="Direction").grid(row=1, column=0, sticky="w", pady=4)
        direction_box = ttk.Combobox(form, textvariable=self.vars["direction"], values=list(DIRECTIONS.values()), state="readonly", width=32)
        direction_box.grid(row=1, column=1, pady=4); direction_box.bind("<<ComboboxSelected>>", lambda _e: self._update_labels())
        self.listen_label = ttk.Label(form); self.listen_label.grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["listen"], width=34).grid(row=2, column=1, pady=4)
        self.host_label = ttk.Label(form); self.host_label.grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["host"], width=34).grid(row=3, column=1, pady=4)
        self.port_label = ttk.Label(form); self.port_label.grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["port"], width=34).grid(row=4, column=1, pady=4)
        ttk.Label(form, text="Description").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.vars["description"], width=34).grid(row=5, column=1, pady=4)
        ttk.Checkbutton(form, text="Enabled", variable=self.vars["enabled"]).grid(row=6, column=1, sticky="w")
        buttons = ttk.Frame(form); buttons.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save", command=self._save).pack(side="left")
        self._update_labels()
        self.transient(parent); self.wait_visibility(); self.grab_set(); self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _direction_key(self) -> str:
        label = self.vars["direction"].get()
        return next(key for key, value in DIRECTIONS.items() if value == label)

    def _update_labels(self) -> None:
        if self._direction_key() == "local":
            self.listen_label.configure(text="Listen port (this machine)")
            self.host_label.configure(text="Remote host (as seen from server)")
            self.port_label.configure(text="Remote port")
        else:
            self.listen_label.configure(text="Listen port (on server)")
            self.host_label.configure(text="Forward to host (this machine)")
            self.port_label.configure(text="Forward to port")

    def _save(self) -> None:
        try:
            listen, dest = int(self.vars["listen"].get()), int(self.vars["port"].get())
            if not (1 <= listen <= 65535 and 1 <= dest <= 65535): raise ValueError
            if not self.vars["name"].get().strip() or not self.vars["host"].get().strip(): raise ValueError
        except ValueError:
            messagebox.showerror("Invalid tunnel", "Enter a name, host, and ports between 1 and 65535.", parent=self); return
        self.result = dict(name=self.vars["name"].get().strip(), enabled=self.vars["enabled"].get(), direction=self._direction_key(),
                           listen_port=listen, dest_host=self.vars["host"].get().strip(), dest_port=dest,
                           description=self.vars["description"].get().strip())
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SSH Tunnel Manager"); self.geometry("880x640"); self.minsize(740, 520)
        self._setup_style()
        self.settings = load_settings(); self.ssh_hosts = read_ssh_hosts(); self.events = queue.Queue()
        self.manager = SSHManager(lambda kind, data: self.events.put((kind, data)))
        self.connected_at = None; self.tunnel_states = {}
        self._build(); self._load_connection_fields(); self._refresh_table()
        self.after(100, self._poll_events); self.after(1000, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._quit)
        if self.settings.auto_connect and self.settings.host: self.after(300, self._connect)

    def _setup_style(self) -> None:
        self.configure(background=PALETTE["bg"])
        for name, size, weight in (("TkDefaultFont", 10, "normal"), ("TkTextFont", 10, "normal"), ("TkFixedFont", 10, "normal"), ("TkHeadingFont", 10, "bold")):
            tkfont.nametofont(name).configure(size=size, weight=weight)
        family = tkfont.nametofont("TkDefaultFont").actual("family")

        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure(".", background=PALETTE["bg"], foreground=PALETTE["text"])
        style.configure("TLabelframe", background=PALETTE["bg"], bordercolor=PALETTE["border"])
        style.configure("TLabelframe.Label", background=PALETTE["bg"], foreground=PALETTE["text"], font=(family, 10, "bold"))
        style.configure("TFrame", background=PALETTE["bg"])
        style.configure("TLabel", background=PALETTE["bg"])
        style.configure("TCheckbutton", background=PALETTE["bg"])
        style.configure("TEntry", fieldbackground=PALETTE["surface"], bordercolor=PALETTE["border"])
        style.configure("TCombobox", fieldbackground=PALETTE["surface"])
        style.configure("TButton", padding=6)
        style.configure("Accent.TButton", padding=6, background=PALETTE["accent"], foreground="white")
        style.map("Accent.TButton", background=[("active", PALETTE["accent_active"]), ("disabled", PALETTE["border"])])
        style.configure("Treeview", background=PALETTE["surface"], fieldbackground=PALETTE["surface"], rowheight=26, bordercolor=PALETTE["border"], borderwidth=1)
        style.configure("Treeview.Heading", background=PALETTE["bg"], foreground=PALETTE["muted"], font=(family, 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", PALETTE["accent"])], foreground=[("selected", "white")])
        for status, color in ("Connected", PALETTE["success"]), ("Connecting", PALETTE["warning"]), ("Disconnected", PALETTE["muted"]):
            style.configure(f"{status}.TLabel", foreground=color, font=(family, 10, "bold"))

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=14); outer.pack(fill="both", expand=True)

        connection = ttk.LabelFrame(outer, text="SSH server", padding=12); connection.pack(fill="x")
        self.host_var, self.user_var, self.key_var, self.port_var = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar(value="22")
        self.host_box = ttk.Combobox(connection, textvariable=self.host_var, values=sorted(self.ssh_hosts), width=25)
        self.host_box.grid(row=0, column=1, sticky="ew", padx=(6, 16), pady=3); self.host_box.bind("<<ComboboxSelected>>", self._host_selected)
        ttk.Label(connection, text="Host").grid(row=0, column=0, sticky="e"); ttk.Label(connection, text="User").grid(row=0, column=2, sticky="e")
        ttk.Entry(connection, textvariable=self.user_var, width=15).grid(row=0, column=3, sticky="ew", padx=(6, 16), pady=3)
        ttk.Label(connection, text="Port").grid(row=0, column=4, sticky="e"); ttk.Entry(connection, textvariable=self.port_var, width=6).grid(row=0, column=5, padx=(6, 0), pady=3)
        ttk.Label(connection, text="Key").grid(row=1, column=0, sticky="e")
        ttk.Entry(connection, textvariable=self.key_var).grid(row=1, column=1, columnspan=4, sticky="ew", padx=(6, 16), pady=3)
        ttk.Button(connection, text="Browse…", command=self._browse_key).grid(row=1, column=5, sticky="ew")
        connection.columnconfigure(1, weight=2); connection.columnconfigure(3, weight=1)

        statusbar = ttk.Frame(outer); statusbar.pack(fill="x", pady=14)
        self.status_var, self.elapsed_var = tk.StringVar(value="⚪ Disconnected"), tk.StringVar(value="00:00:00")
        self.status_label = ttk.Label(statusbar, textvariable=self.status_var, style="Disconnected.TLabel")
        self.status_label.pack(side="left")
        ttk.Label(statusbar, textvariable=self.elapsed_var, foreground=PALETTE["muted"]).pack(side="left", padx=20)
        self.connect_btn = ttk.Button(statusbar, text="Connect", command=self._connect, style="Accent.TButton"); self.connect_btn.pack(side="right")

        tunnels = ttk.LabelFrame(outer, text="Tunnels", padding=10); tunnels.pack(fill="both", expand=True)
        tree_row = ttk.Frame(tunnels); tree_row.pack(fill="both", expand=True)
        columns = ("enabled", "name", "direction", "listen", "dest", "status")
        self.tree = ttk.Treeview(tree_row, columns=columns, show="headings", height=10, selectmode="browse")
        for col, label, width in zip(columns, ("On", "Name", "Dir", "Listen port", "Forwards to", "Status"), (35, 160, 45, 100, 200, 110)):
            self.tree.heading(col, text=label); self.tree.column(col, width=width, anchor="center" if col != "name" else "w")
        tree_scroll = ttk.Scrollbar(tree_row, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True); tree_scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit())
        for status, color in TUNNEL_STATUS_TAGS.items(): self.tree.tag_configure(status, foreground=PALETTE[color])
        self.tree.tag_configure("oddrow", background="#eef1f5")

        actions = ttk.Frame(tunnels); actions.pack(fill="x", pady=(10, 0))
        for text, command in (("Add", self._add), ("Edit", self._edit), ("Enable/Disable", self._toggle), ("Delete", self._delete)):
            ttk.Button(actions, text=text, command=command).pack(side="left", padx=(0, 6))
        self.auto_var = tk.BooleanVar(value=self.settings.auto_connect)
        ttk.Checkbutton(actions, text="Connect automatically", variable=self.auto_var, command=self._persist).pack(side="right")

        logs = ttk.LabelFrame(outer, text="Logs", padding=8); logs.pack(fill="both", pady=(14, 0))
        log_row = ttk.Frame(logs); log_row.pack(fill="both")
        self.log = tk.Text(log_row, height=7, state="disabled", wrap="word", relief="flat", borderwidth=0,
                            background=PALETTE["surface"], foreground=PALETTE["text"], font=("TkFixedFont",))
        log_scroll = ttk.Scrollbar(log_row, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side="left", fill="both", expand=True); log_scroll.pack(side="right", fill="y")

    def _load_connection_fields(self):
        self.host_var.set(self.settings.host); self.user_var.set(self.settings.user); self.key_var.set(self.settings.key); self.port_var.set(str(self.settings.port))

    def _host_selected(self, _event=None):
        entry = self.ssh_hosts.get(self.host_var.get())
        if entry:
            self.user_var.set(entry["user"]); self.key_var.set(entry["identityfile"]); self.port_var.set(entry["port"])

    def _browse_key(self):
        path = filedialog.askopenfilename(title="Choose SSH private key", initialdir=str(Path.home() / ".ssh"))
        if path: self.key_var.set(path)

    def _capture_settings(self) -> bool:
        try:
            port = int(self.port_var.get()); assert 1 <= port <= 65535
        except (ValueError, AssertionError):
            messagebox.showerror("Invalid settings", "SSH port must be between 1 and 65535."); return False
        if not self.host_var.get().strip(): messagebox.showerror("Invalid settings", "Choose or enter an SSH host."); return False
        self.settings.host = self.host_var.get().strip(); self.settings.user = self.user_var.get().strip()
        self.settings.key = self.key_var.get().strip(); self.settings.port = port; self.settings.auto_connect = self.auto_var.get(); save_settings(self.settings); return True

    def _persist(self):
        self.settings.auto_connect = self.auto_var.get(); save_settings(self.settings)

    def _connect(self):
        if self.manager.desired:
            self.manager.disconnect(); self.connect_btn.configure(text="Connect"); return
        if not ASYNCSSH_AVAILABLE:
            messagebox.showerror("Dependency missing", "Install AsyncSSH first:\n\npython3 -m pip install -r requirements.txt"); return
        if self._capture_settings():
            self.connect_btn.configure(text="Disconnect"); self.manager.connect(self.settings); self._write_log(f"Connecting to {self.settings.host}")

    def _selected_id(self):
        selection = self.tree.selection(); return int(selection[0]) if selection else None

    def _add(self):
        dialog = TunnelDialog(self); self.wait_window(dialog)
        if dialog.result:
            next_id = max((t.id for t in self.settings.tunnels), default=0) + 1
            self.settings.tunnels.append(Tunnel(id=next_id, **dialog.result)); self._changed()

    def _edit(self):
        tunnel_id = self._selected_id()
        tunnel = next((t for t in self.settings.tunnels if t.id == tunnel_id), None)
        if not tunnel: return
        dialog = TunnelDialog(self, tunnel); self.wait_window(dialog)
        if dialog.result:
            for key, value in dialog.result.items(): setattr(tunnel, key, value)
            save_settings(self.settings); self.manager.reopen_tunnel(tunnel.id); self._refresh_table()

    def _toggle(self):
        tunnel_id = self._selected_id()
        for tunnel in self.settings.tunnels:
            if tunnel.id == tunnel_id: tunnel.enabled = not tunnel.enabled; break
        self._changed()

    def _delete(self):
        tunnel_id = self._selected_id()
        if tunnel_id is not None and messagebox.askyesno("Delete tunnel", "Delete the selected tunnel?"):
            self.settings.tunnels = [t for t in self.settings.tunnels if t.id != tunnel_id]; self._changed()

    def _changed(self):
        save_settings(self.settings); self.manager.sync_tunnels(self.settings.tunnels); self._refresh_table()

    def _refresh_table(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for row, tunnel in enumerate(self.settings.tunnels):
            state = self.tunnel_states.get(tunnel.id, "Disabled" if not tunnel.enabled else "Pending")
            arrow = "←" if tunnel.direction == "local" else "→"
            tags = (state,) if row % 2 == 0 else (state, "oddrow")
            self.tree.insert("", "end", iid=str(tunnel.id), tags=tags,
                              values=("✓" if tunnel.enabled else "", tunnel.name, arrow, tunnel.listen_port, f"{tunnel.dest_host}:{tunnel.dest_port}", state))
        if selected and self.tree.exists(selected[0]): self.tree.selection_set(selected[0])

    def _poll_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log": self._write_log(str(data))
                elif kind == "tunnel": self.tunnel_states[data[0]] = data[1]; self._refresh_table()
                elif kind == "connection":
                    label, style_name = CONNECTION_STYLES[str(data)]
                    self.status_var.set(label); self.status_label.configure(style=style_name)
                    if data == "connected": self.connected_at = time.monotonic(); self._write_log("Connected")
                    elif data == "disconnected": self.connected_at = None; self.connect_btn.configure(text="Connect")
        except queue.Empty: pass
        self.after(100, self._poll_events)

    def _tick(self):
        seconds = int(time.monotonic() - self.connected_at) if self.connected_at else 0
        self.elapsed_var.set(f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"); self.after(1000, self._tick)

    def _write_log(self, message):
        self.log.configure(state="normal"); self.log.insert("end", time.strftime("%H:%M:%S ") + message + "\n"); self.log.see("end"); self.log.configure(state="disabled")

    def _quit(self):
        self.manager.shutdown(); self.destroy()


if __name__ == "__main__":
    App().mainloop()
