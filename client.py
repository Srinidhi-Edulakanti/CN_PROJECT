"""Tkinter client for the LAN-Chat System lab project."""

from __future__ import annotations

import ipaddress
import json
import queue
import re
import socket
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Any

MAX_FRAME_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 2_000
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_ -]{1,20}\Z")

BG = "#f3f6fb"
PANEL = "#ffffff"
NAVY = "#172554"
BLUE = "#2563eb"
MUTED = "#64748b"
TEXT = "#172033"
GREEN = "#15803d"
RED = "#b91c1c"


def local_timestamp() -> str:
    """Format the current local time for messages composed by this client."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def display_time(value: Any) -> str:
    """Show a server timestamp as a short local-friendly time string."""
    if not isinstance(value, str):
        return ""
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone().strftime("%H:%M:%S")
    except ValueError:
        return value


class LanChatClient:
    """Manage the Tkinter screens and the background TCP connection."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("LAN-Chat System")
        self.root.geometry("1000x680")
        self.root.minsize(760, 520)
        self.root.configure(bg=BG)

        self.events: queue.Queue[tuple[int, str, Any]] = queue.Queue()
        self.send_lock = threading.Lock()
        self.sock: socket.socket | None = None
        self.generation = 0
        self.closing = False
        self.username: str | None = None
        self.online_users: list[str] = []
        self.current_chat = "group"
        self.chat_histories: dict[str, list[dict[str, str]]] = {"group": []}
        self.private_names: dict[str, str] = {}

        self._build_login_screen()
        self._build_chat_screen()
        self.login_screen.tkraise()
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.root.after(100, self._process_events)

    def _build_login_screen(self) -> None:
        """Create the connection form shown before a user joins the chat."""
        self.login_screen = tk.Frame(self.root, bg=BG)
        self.login_screen.place(relx=0, rely=0, relwidth=1, relheight=1)

        card = tk.Frame(self.login_screen, bg=PANEL, padx=42, pady=34, highlightthickness=1, highlightbackground="#dbe3ef")
        card.place(relx=0.5, rely=0.48, anchor="center")
        tk.Label(card, text="LAN-Chat System", bg=PANEL, fg=NAVY, font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(card, text="Real-time messaging over your local network", bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 24))

        self.username_var = tk.StringVar()
        self.server_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="5000")
        self.login_status = tk.StringVar(value="Enter your details to connect.")

        self._add_form_field(card, "Username", self.username_var)
        self._add_form_field(card, "Server IPv4 address", self.server_var)
        self._add_form_field(card, "TCP port", self.port_var)

        self.connect_button = tk.Button(
            card,
            text="Connect",
            command=self.connect,
            bg=BLUE,
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=10,
            cursor="hand2",
        )
        self.connect_button.pack(fill="x", pady=(18, 10))
        tk.Label(card, textvariable=self.login_status, bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=360, justify="left").pack(anchor="w")
        self.username_entry.focus_set()
        self.username_entry.bind("<Return>", lambda _event: self.connect())
        self.server_entry.bind("<Return>", lambda _event: self.connect())
        self.port_entry.bind("<Return>", lambda _event: self.connect())

    def _add_form_field(self, parent: tk.Widget, label: str, variable: tk.StringVar) -> None:
        """Add a labeled entry and retain it for keyboard navigation."""
        tk.Label(parent, text=label, bg=PANEL, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))
        entry = tk.Entry(parent, textvariable=variable, font=("Segoe UI", 11), relief="solid", bd=1, highlightthickness=1, highlightcolor=BLUE)
        entry.pack(fill="x", ipady=8, pady=(0, 14))
        if label == "Username":
            self.username_entry = entry
        elif label == "Server IPv4 address":
            self.server_entry = entry
        else:
            self.port_entry = entry

    def _build_chat_screen(self) -> None:
        """Create the online-user sidebar, chat transcript, and message composer."""
        self.chat_screen = tk.Frame(self.root, bg=BG)
        self.chat_screen.place(relx=0, rely=0, relwidth=1, relheight=1)

        header = tk.Frame(self.chat_screen, bg=NAVY, height=66, padx=20)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="LAN-Chat", bg=NAVY, fg="white", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.header_status = tk.StringVar(value="Disconnected")
        tk.Label(header, textvariable=self.header_status, bg=NAVY, fg="#cbd5e1", font=("Segoe UI", 9)).pack(side="left", padx=(18, 0))
        self.header_user = tk.Label(header, text="", bg=NAVY, fg="white", font=("Segoe UI", 10, "bold"))
        self.header_user.pack(side="right", padx=(12, 0))
        tk.Button(header, text="Disconnect", command=self.disconnect, bg="#334155", fg="white", activebackground="#475569", activeforeground="white", relief="flat", padx=12, pady=7, cursor="hand2").pack(side="right")

        body = tk.Frame(self.chat_screen, bg=BG, padx=18, pady=18)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, bg=PANEL, width=230, highlightthickness=1, highlightbackground="#dbe3ef")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="CHATS", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"), padx=16, pady=15).pack(anchor="w")
        self.group_button = tk.Button(sidebar, text="▣   Group Chat", anchor="w", command=self.select_group, bg="#eff6ff", fg=BLUE, relief="flat", padx=14, pady=10, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.group_button.pack(fill="x", padx=8)
        tk.Label(sidebar, text="ONLINE USERS", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold"), padx=16, pady=16).pack(anchor="w")
        self.users_list = tk.Listbox(sidebar, borderwidth=0, highlightthickness=0, activestyle="none", bg=PANEL, fg=TEXT, selectbackground="#dbeafe", selectforeground=NAVY, font=("Segoe UI", 10), exportselection=False)
        self.users_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self.users_list.bind("<<ListboxSelect>>", self.select_private_user)
        tk.Label(sidebar, text="Select a user to start a private chat.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=190, justify="left", padx=14, pady=12).pack(anchor="w")

        conversation = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground="#dbe3ef")
        conversation.pack(side="left", fill="both", expand=True, padx=(14, 0))
        conversation.grid_columnconfigure(0, weight=1)
        conversation.grid_rowconfigure(2, weight=1)
        conversation_header = tk.Frame(conversation, bg=PANEL, padx=20, pady=14)
        conversation_header.grid(row=0, column=0, sticky="ew")
        self.chat_title = tk.StringVar(value="Group Chat")
        self.chat_subtitle = tk.StringVar(value="Messages are visible to everyone online")
        tk.Label(conversation_header, textvariable=self.chat_title, bg=PANEL, fg=NAVY, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(conversation_header, textvariable=self.chat_subtitle, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        ttk.Separator(conversation, orient="horizontal").grid(row=1, column=0, sticky="ew")

        transcript_frame = tk.Frame(conversation, bg=PANEL, padx=20, pady=14)
        transcript_frame.grid(row=2, column=0, sticky="nsew")
        self.transcript = tk.Text(transcript_frame, wrap="word", state="disabled", bg=PANEL, fg=TEXT, relief="flat", font=("Segoe UI", 10), padx=4, pady=4, spacing1=3, spacing3=8)
        scrollbar = ttk.Scrollbar(transcript_frame, orient="vertical", command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.transcript.tag_configure("meta", foreground=MUTED, font=("Segoe UI", 8))
        self.transcript.tag_configure("sender", foreground=BLUE, font=("Segoe UI", 9, "bold"))
        self.transcript.tag_configure("mine", foreground=GREEN, font=("Segoe UI", 9, "bold"))
        self.transcript.tag_configure("body", foreground=TEXT, font=("Segoe UI", 10))
        self.transcript.tag_configure("notice", foreground=MUTED, font=("Segoe UI", 9, "italic"))
        self.transcript.tag_configure("error", foreground=RED, font=("Segoe UI", 9, "bold"))

        composer = tk.Frame(conversation, bg="#f8fafc", padx=16, pady=14)
        composer.grid(row=3, column=0, sticky="ew")
        self.message_var = tk.StringVar()
        self.message_entry = tk.Entry(composer, textvariable=self.message_var, font=("Segoe UI", 10), relief="solid", bd=1, highlightthickness=1, highlightcolor=BLUE)
        self.message_entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 10))
        self.message_entry.bind("<Return>", self.send_message)
        tk.Button(composer, text="Send", command=self.send_message, bg=BLUE, fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=20, pady=9, cursor="hand2").pack(side="right")

        self.footer_status = tk.StringVar(value="Connect to a server to begin.")
        tk.Label(self.chat_screen, textvariable=self.footer_status, bg=BG, fg=MUTED, anchor="w", padx=20, pady=5, font=("Segoe UI", 8)).pack(fill="x")

    def connect(self) -> None:
        """Validate the form and begin connecting without blocking Tkinter."""
        username = self.username_var.get().strip()
        server_ip = self.server_var.get().strip()
        port_text = self.port_var.get().strip()
        if not USERNAME_PATTERN.fullmatch(username):
            self.login_status.set("Use 1–20 letters, numbers, spaces, underscores, or hyphens for the username.")
            return
        try:
            ipaddress.IPv4Address(server_ip)
        except ipaddress.AddressValueError:
            self.login_status.set("Enter a valid server IPv4 address, such as 192.168.1.25.")
            return
        try:
            port = int(port_text)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.login_status.set("Enter a port number from 1 to 65535.")
            return

        self.generation += 1
        generation = self.generation
        self._close_socket()
        self.connect_button.configure(state="disabled")
        self.login_status.set(f"Connecting to {server_ip}:{port}…")
        worker = threading.Thread(target=self._connection_worker, args=(generation, server_ip, port, username), name="lan-chat-receiver", daemon=True)
        worker.start()

    def _connection_worker(self, generation: int, server_ip: str, port: int, username: str) -> None:
        """Connect, send the login frame, then receive server frames in a thread."""
        connection: socket.socket | None = None
        try:
            connection = socket.create_connection((server_ip, port), timeout=8)
            connection.settimeout(None)
            if generation != self.generation or self.closing:
                connection.close()
                return
            login_frame = (json.dumps({"type": "login", "username": username}) + "\n").encode("utf-8")
            connection.sendall(login_frame)
            self.events.put((generation, "socket_ready", connection))
            self._receive_messages(generation, connection)
        except (OSError, json.JSONDecodeError) as error:
            self.events.put((generation, "connection_lost", str(error)))
        finally:
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    pass

    def _receive_messages(self, generation: int, connection: socket.socket) -> None:
        """Reassemble newline-delimited JSON frames and queue them for Tkinter."""
        pending = bytearray()
        while not self.closing and generation == self.generation:
            chunk = connection.recv(4096)
            if not chunk:
                raise ConnectionError("The server closed the connection.")
            pending.extend(chunk)
            while b"\n" in pending:
                raw_frame, _, remainder = pending.partition(b"\n")
                pending = bytearray(remainder)
                if len(raw_frame) > MAX_FRAME_BYTES:
                    raise ConnectionError("The server sent a frame that is too large.")
                if not raw_frame.strip():
                    continue
                try:
                    message = json.loads(raw_frame.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ConnectionError("The server sent an invalid message.") from error
                if not isinstance(message, dict):
                    raise ConnectionError("The server sent a message in an unsupported format.")
                self.events.put((generation, "server_message", message))
            if len(pending) > MAX_FRAME_BYTES:
                raise ConnectionError("The server sent a frame that is too large.")

    def _process_events(self) -> None:
        """Apply queued network events on Tkinter's main thread."""
        try:
            while True:
                generation, event_type, payload = self.events.get_nowait()
                if generation != self.generation:
                    continue
                if event_type == "socket_ready":
                    self.sock = payload
                elif event_type == "connection_lost":
                    if self.username is None:
                        self._close_socket()
                        self.connect_button.configure(state="normal")
                        self.login_status.set(f"Could not connect: {payload}")
                        self.header_status.set("Disconnected")
                    else:
                        self._return_to_login(f"Connection lost: {payload}")
                elif event_type == "server_message":
                    self._handle_server_message(payload)
        except queue.Empty:
            pass
        if not self.closing:
            self.root.after(100, self._process_events)

    def _handle_server_message(self, message: dict[str, Any]) -> None:
        """Update login, presence, and chat views for a decoded server event."""
        message_type = message.get("type")
        if message_type == "login_result":
            if message.get("ok"):
                self.username = str(message.get("username", self.username_var.get().strip()))
                self.header_user.configure(text=f"Signed in as {self.username}")
                self.header_status.set("Connected")
                self.footer_status.set("Connected to the LAN-Chat server.")
                self.current_chat = "group"
                self.chat_screen.tkraise()
                self._render_current_chat()
            else:
                self.connect_button.configure(state="normal")
                self.login_status.set(str(message.get("message", "Login failed.")))
                self.disconnect(return_to_login=True, quiet=True)
        elif message_type == "user_list":
            users = message.get("users", [])
            if isinstance(users, list):
                own_key = (self.username or "").casefold()
                self.online_users = sorted(
                    {user for user in users if isinstance(user, str) and user.casefold() != own_key},
                    key=str.casefold,
                )
                self._refresh_user_list()
        elif message_type in ("user_joined", "user_left"):
            username = str(message.get("username", "A user"))
            username_key = username.casefold()
            if message_type == "user_joined":
                if username_key != (self.username or "").casefold() and not any(
                    user.casefold() == username_key for user in self.online_users
                ):
                    self.online_users.append(username)
                    self.online_users.sort(key=str.casefold)
            else:
                self.online_users = [
                    user for user in self.online_users if user.casefold() != username_key
                ]
            self._refresh_user_list()
            action = "joined" if message_type == "user_joined" else "left"
            self._append_history("group", "notice", "", f"{username} {action} the chat", message.get("timestamp"))
            if self.current_chat == "group":
                self._render_current_chat()
        elif message_type == "group_message":
            self._append_history("group", "message", str(message.get("from", "Unknown")), str(message.get("message", "")), message.get("timestamp"))
            if self.current_chat == "group":
                self._render_current_chat()
        elif message_type == "private_message":
            sender = str(message.get("from", "Unknown"))
            key = sender.casefold()
            self.private_names[key] = sender
            self._append_history(key, "message", sender, str(message.get("message", "")), message.get("timestamp"))
            if self.current_chat == key:
                self._render_current_chat()
            else:
                self.root.bell()
                self.footer_status.set(f"New private message from {sender}.")
        elif message_type == "private_sent":
            self.footer_status.set(f"Private message sent to {message.get('to', 'user')} at {display_time(message.get('timestamp'))}.")
        elif message_type == "error":
            text = str(message.get("message", "Server error."))
            self._append_history(self.current_chat, "error", "", text, local_timestamp())
            self._render_current_chat()
            self.footer_status.set(text)

    def _refresh_user_list(self) -> None:
        """Refresh the online users list while preserving the active selection."""
        selected_name = self.private_names.get(self.current_chat)
        self.users_list.delete(0, tk.END)
        for username in self.online_users:
            self.users_list.insert(tk.END, f"●  {username}")
        if selected_name in self.online_users:
            index = self.online_users.index(selected_name)
            self.users_list.selection_set(index)

    def select_group(self) -> None:
        """Switch the transcript to the shared group conversation."""
        self.current_chat = "group"
        self.chat_title.set("Group Chat")
        self.chat_subtitle.set("Messages are visible to everyone online")
        self.group_button.configure(bg="#eff6ff", fg=BLUE)
        self.users_list.selection_clear(0, tk.END)
        self._render_current_chat()
        self.message_entry.focus_set()

    def select_private_user(self, _event: tk.Event) -> None:
        """Open a private conversation for the selected online user."""
        selection = self.users_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self.online_users):
            return
        username = self.online_users[index]
        self.current_chat = username.casefold()
        self.private_names[self.current_chat] = username
        self.chat_title.set(username)
        self.chat_subtitle.set("Private conversation")
        self.group_button.configure(bg=PANEL, fg=TEXT)
        self._render_current_chat()
        self.message_entry.focus_set()

    def send_message(self, _event: tk.Event | None = None) -> str:
        """Send the text in the composer to the group or selected user."""
        text = self.message_var.get().strip()
        if not text:
            return "break"
        if len(text) > MAX_MESSAGE_CHARS:
            self.footer_status.set(f"Messages must be {MAX_MESSAGE_CHARS} characters or fewer.")
            return "break"
        if self.sock is None:
            self.footer_status.set("Not connected to a server.")
            return "break"
        if self.current_chat == "group":
            payload = {"type": "group", "message": text}
        else:
            recipient = self.private_names.get(self.current_chat)
            if recipient is None or recipient not in self.online_users:
                self.footer_status.set("That user is no longer online.")
                return "break"
            payload = {"type": "private", "to": recipient, "message": text}
        try:
            frame = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            with self.send_lock:
                self.sock.sendall(frame)
        except OSError as error:
            self._return_to_login(f"Connection lost: {error}")
            return "break"
        if payload["type"] == "private":
            self._append_history(self.current_chat, "message", "You", text, local_timestamp())
            self._render_current_chat()
        self.message_var.set("")
        self.message_entry.focus_set()
        return "break"

    def _append_history(self, key: str, kind: str, sender: str, text: str, timestamp: Any) -> None:
        """Append one display item and keep each conversation bounded in memory."""
        history = self.chat_histories.setdefault(key, [])
        history.append({"kind": kind, "sender": sender, "text": text, "timestamp": str(timestamp or "")})
        if len(history) > 500:
            del history[:-500]

    def _render_current_chat(self) -> None:
        """Render the active conversation history in the read-only transcript."""
        history = self.chat_histories.get(self.current_chat, [])
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", tk.END)
        for item in history:
            kind = item["kind"]
            time_text = display_time(item["timestamp"])
            if kind == "notice":
                self.transcript.insert(tk.END, f"{item['text']}  {time_text}\n", "notice")
            elif kind == "error":
                self.transcript.insert(tk.END, f"{item['text']}  {time_text}\n", "error")
            else:
                sender_tag = "mine" if item["sender"] == "You" or item["sender"] == self.username else "sender"
                self.transcript.insert(tk.END, f"{item['sender']}  ", sender_tag)
                self.transcript.insert(tk.END, f"{time_text}\n", "meta")
                self.transcript.insert(tk.END, f"{item['text']}\n\n", "body")
        self.transcript.configure(state="disabled")
        self.transcript.see(tk.END)

    def _close_socket(self) -> None:
        """Close the active socket to unblock its receiver thread."""
        connection = self.sock
        self.sock = None
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass

    def disconnect(self, return_to_login: bool = True, quiet: bool = False) -> None:
        """Disconnect from the server and optionally show the login form."""
        self.generation += 1
        self._close_socket()
        self.online_users.clear()
        self._refresh_user_list()
        self.username = None
        self.header_user.configure(text="")
        self.header_status.set("Disconnected")
        self.footer_status.set("Disconnected from the server.")
        if return_to_login:
            self.connect_button.configure(state="normal")
            self.login_screen.tkraise()
            if not quiet:
                self.login_status.set("Disconnected. Enter details to reconnect.")

    def _return_to_login(self, message: str) -> None:
        """Report a connection loss and return to the login screen."""
        self.disconnect(return_to_login=True, quiet=True)
        self.login_status.set(message)

    def close_window(self) -> None:
        """Close the connection and terminate the Tkinter application."""
        self.closing = True
        self.generation += 1
        self._close_socket()
        self.root.destroy()


def main() -> None:
    """Create the window and start Tkinter's event loop."""
    root = tk.Tk()
    LanChatClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()




