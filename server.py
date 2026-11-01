"""TCP chat server for the LAN-Chat System lab project."""

from __future__ import annotations

import argparse
import json
import re
import socket
import threading
from datetime import datetime
from typing import Any

MAX_FRAME_BYTES = 64 * 1024
MAX_MESSAGE_CHARS = 2_000
MAX_USERNAME_CHARS = 20
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_ -]{1,20}\Z")


def timestamp() -> str:
    """Return a readable local timestamp, including the local UTC offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ClientSession:
    """Store one connected socket and serialize writes to that socket."""

    def __init__(self, connection: socket.socket, address: tuple[str, int]) -> None:
        self.connection = connection
        self.address = address
        self.username: str | None = None
        self.send_lock = threading.Lock()

    def send_json(self, message: dict[str, Any]) -> bool:
        """Send one newline-delimited JSON object; return False on socket failure."""
        try:
            frame = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
            with self.send_lock:
                self.connection.sendall(frame)
            return True
        except (OSError, TypeError, ValueError):
            return False


class ChatServer:
    """Accept clients and route group, private, and presence messages."""

    def __init__(self, host: str = "0.0.0.0", port: int = 5000) -> None:
        self.host = host
        self.port = port
        self.clients: dict[str, ClientSession] = {}
        self.clients_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.listener: socket.socket | None = None

    def start(self) -> None:
        """Bind the TCP port and handle each accepted client in a thread."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener = listener
        try:
            listener.bind((self.host, self.port))
            listener.listen()
            print(f"LAN-Chat server listening on {self.host}:{self.port}")
            print("Press Ctrl+C to stop the server.")
            while not self.stop_event.is_set():
                try:
                    connection, address = listener.accept()
                except OSError:
                    if self.stop_event.is_set():
                        break
                    raise
                session = ClientSession(connection, address)
                worker = threading.Thread(
                    target=self.handle_client,
                    args=(session,),
                    name=f"client-{address[0]}:{address[1]}",
                    daemon=True,
                )
                worker.start()
        finally:
            self.shutdown()

    def handle_client(self, session: ClientSession) -> None:
        """Read complete JSON frames and process them until the client leaves."""
        address = f"{session.address[0]}:{session.address[1]}"
        print(f"Connection opened: {address}")
        pending = bytearray()
        try:
            while not self.stop_event.is_set():
                chunk = session.connection.recv(4096)
                if not chunk:
                    break
                pending.extend(chunk)
                if len(pending) > MAX_FRAME_BYTES and b"\n" not in pending:
                    session.send_json({"type": "error", "message": "Message frame is too large."})
                    break
                while b"\n" in pending:
                    raw_frame, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    if len(raw_frame) > MAX_FRAME_BYTES:
                        session.send_json({"type": "error", "message": "Message frame is too large."})
                        return
                    if not raw_frame.strip():
                        continue
                    try:
                        message = json.loads(raw_frame.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        session.send_json({"type": "error", "message": "Invalid JSON message."})
                        continue
                    if not isinstance(message, dict):
                        session.send_json({"type": "error", "message": "Each message must be a JSON object."})
                        continue
                    self.process_message(session, message)
        except (ConnectionResetError, OSError) as error:
            if not self.stop_event.is_set():
                print(f"Connection error for {address}: {error}")
        finally:
            self.remove_client(session)
            try:
                session.connection.close()
            except OSError:
                pass
            print(f"Connection closed: {address}")

    def process_message(self, session: ClientSession, message: dict[str, Any]) -> None:
        """Validate a client message and dispatch it to the matching handler."""
        message_type = message.get("type")
        if session.username is None:
            if message_type == "login":
                self.login(session, message.get("username"))
            else:
                session.send_json({"type": "login_result", "ok": False, "message": "Log in before sending messages."})
            return
        if message_type == "group":
            self.send_group_message(session, message.get("message"))
        elif message_type == "private":
            self.send_private_message(session, message.get("to"), message.get("message"))
        elif message_type == "login":
            session.send_json({"type": "error", "message": "This connection is already logged in."})
        else:
            session.send_json({"type": "error", "message": "Unknown message type."})

    def login(self, session: ClientSession, raw_username: Any) -> None:
        """Validate and reserve a unique username, then publish the new presence."""
        if not isinstance(raw_username, str):
            session.send_json({"type": "login_result", "ok": False, "message": "Enter a username."})
            return
        username = raw_username.strip()
        if not USERNAME_PATTERN.fullmatch(username) or len(username) > MAX_USERNAME_CHARS:
            session.send_json({
                "type": "login_result",
                "ok": False,
                "message": "Use 1–20 letters, numbers, spaces, underscores, or hyphens.",
            })
            return
        key = username.casefold()
        with self.clients_lock:
            if key in self.clients:
                session.send_json({"type": "login_result", "ok": False, "message": "That username is already online."})
                return
            session.username = username
            self.clients[key] = session
            online_users = self.online_usernames_locked()
        if not session.send_json({"type": "login_result", "ok": True, "username": username, "message": "Connected to the server."}):
            self.remove_client(session)
            return
        print(f"{username} joined from {session.address[0]}:{session.address[1]}")
        self.broadcast({"type": "user_joined", "username": username, "timestamp": timestamp()})
        self.broadcast({"type": "user_list", "users": online_users})

    def send_group_message(self, sender: ClientSession, raw_text: Any) -> None:
        """Broadcast a valid group message to every currently connected user."""
        text = self.validate_message_text(raw_text, sender)
        if text is None:
            return
        self.broadcast({
            "type": "group_message",
            "from": sender.username,
            "message": text,
            "timestamp": timestamp(),
        })

    def send_private_message(self, sender: ClientSession, raw_recipient: Any, raw_text: Any) -> None:
        """Send a private message only to its named online recipient."""
        text = self.validate_message_text(raw_text, sender)
        if text is None:
            return
        if not isinstance(raw_recipient, str) or not raw_recipient.strip():
            sender.send_json({"type": "error", "message": "Choose an online recipient."})
            return
        recipient_name = raw_recipient.strip()
        with self.clients_lock:
            recipient = self.clients.get(recipient_name.casefold())
        if recipient is None:
            sender.send_json({"type": "error", "message": f"{recipient_name} is not online."})
            return
        sent_at = timestamp()
        if not recipient.send_json({
            "type": "private_message",
            "from": sender.username,
            "message": text,
            "timestamp": sent_at,
        }):
            self.remove_client(recipient)
            sender.send_json({"type": "error", "message": f"{recipient_name} disconnected before delivery."})
            return
        sender.send_json({"type": "private_sent", "to": recipient.username, "timestamp": sent_at})

    def validate_message_text(self, raw_text: Any, sender: ClientSession) -> str | None:
        """Reject non-text, blank, or excessively long chat messages."""
        if not isinstance(raw_text, str) or not raw_text.strip():
            sender.send_json({"type": "error", "message": "Messages cannot be empty."})
            return None
        text = raw_text.strip()
        if len(text) > MAX_MESSAGE_CHARS:
            sender.send_json({"type": "error", "message": f"Messages must be {MAX_MESSAGE_CHARS} characters or fewer."})
            return None
        return text

    def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to a snapshot of all logged-in sessions."""
        with self.clients_lock:
            recipients = list(self.clients.values())
        for recipient in recipients:
            if not recipient.send_json(message):
                self.remove_client(recipient)

    def online_usernames_locked(self) -> list[str]:
        """Return usernames; the caller must already hold clients_lock."""
        return sorted(
            (session.username for session in self.clients.values() if session.username is not None),
            key=str.casefold,
        )

    def remove_client(self, session: ClientSession) -> None:
        """Remove a session once and notify the remaining users if it had logged in."""
        username = session.username
        was_removed = False
        with self.clients_lock:
            if username is not None:
                key = username.casefold()
                if self.clients.get(key) is session:
                    del self.clients[key]
                    was_removed = True
                    online_users = self.online_usernames_locked()
        if was_removed:
            print(f"{username} left the chat")
            self.broadcast({"type": "user_left", "username": username, "timestamp": timestamp()})
            self.broadcast({"type": "user_list", "users": online_users})

    def shutdown(self) -> None:
        """Stop accepting work and close all connected sockets safely."""
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
        with self.clients_lock:
            sessions = list(self.clients.values())
            self.clients.clear()
        for session in sessions:
            try:
                session.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                session.connection.close()
            except OSError:
                pass
        print("Server stopped.")


def main() -> None:
    """Read command-line options and launch the chat server."""
    parser = argparse.ArgumentParser(description="Run the LAN-Chat TCP server.")
    parser.add_argument("--host", default="0.0.0.0", help="Interface address to bind (default: all IPv4 interfaces).")
    parser.add_argument("--port", type=int, default=5000, help="TCP port to listen on (default: 5000).")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    server = ChatServer(args.host, args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.shutdown()
    except OSError as error:
        print(f"Could not start or continue the server: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
