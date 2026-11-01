# LAN-Chat System

A Python desktop chat application for computers on the same local area network. One computer runs the TCP server; each participant runs a Tkinter client. The application works without an internet messaging service. Use it only on a trusted LAN because this lab version does not encrypt traffic.

## Project contents

- `server.py` — TCP server, client threads, login validation, presence, and group/private routing.
- `client.py` — Tkinter login and chat screens, TCP receiver thread, and message history.
- `requirements.txt` — no third-party packages are required.
- `screenshots/` — save real application screenshots from your demonstration here.
- `project_report/LAN_Chat_System_Report.docx` — project report and viva questions.

## Requirements

- Python 3.10 or newer on each computer.
- Tkinter installed with Python. On Windows, the standard python.org installer normally includes Tcl/Tk.
- All computers connected to the same Wi-Fi or wired LAN.
- Windows Firewall permits inbound TCP traffic on the server port (default 5000) on the Private profile.

Check Python with `py --version`. If Tkinter is missing, `py -m tkinter` should open a small demonstration window.

## Run on one computer

Open two Command Prompt windows in the project folder.

Window 1, start the server:

```bat
py server.py --host 0.0.0.0 --port 5000
```

Window 2, start a client:

```bat
py client.py
```

In the client, use a username, server address `127.0.0.1`, and port `5000`. Start a second client in another window with a different username to try group and private chat. Press Ctrl+C in the server window to stop the server.

## Connect computers on a LAN

1. Connect the server computer and client computers to the same trusted Wi-Fi network or wired LAN. Avoid guest Wi-Fi networks that isolate devices.
2. On the server computer, open Command Prompt and run `ipconfig`.
3. Find the active Wi-Fi or Ethernet adapter and note its `IPv4 Address`, for example `192.168.1.25`. Do not use the Default Gateway or `0.0.0.0` as the client address.
4. Start the server on the host computer with `py server.py --host 0.0.0.0 --port 5000`.
5. On Windows, open **Windows Defender Firewall with Advanced Security**. Select **Inbound Rules** > **New Rule** > **Port**. Choose **TCP**, enter `5000`, select **Allow the connection**, and apply the rule to **Private** networks only. Give it a name such as `LAN Chat TCP 5000`. Administrator rights may be required.
6. Run `py client.py` on each client computer. Enter the server computer's IPv4 address and port `5000`; choose a different username on each client.
7. If connection fails, verify the address, port, firewall rule, and that both devices are on the same network. Some routers enable client isolation, which blocks device-to-device traffic.

If you choose another server port, use it both when launching `server.py` and in every client's port field, and update the firewall rule to match.

## Message protocol

Each application message is a JSON object encoded as UTF-8 and terminated by a newline. Newline framing is needed because TCP is a byte stream and a `recv` call can contain part of a message or several messages. Client requests include `login`, `group`, and `private`. Server events include `login_result`, `user_list`, `user_joined`, `user_left`, `group_message`, `private_message`, `private_sent`, and `error`.

Group messages are broadcast to logged-in clients. A private message is delivered only to the selected recipient; the sender receives an acknowledgement. The server rejects duplicate online usernames, empty messages, invalid names, and messages longer than 2,000 characters.

## Manual test checklist

Record Pass/Fail after performing each check. These are instructions, not previously observed results.

1. Start the server and confirm it reports the listening address and port.
2. Connect one client and confirm its status changes to Connected.
3. Connect at least two clients, preferably from separate computers, and confirm their online lists update.
4. Send a group message and confirm all clients display its sender, text, and timestamp.
5. Send a private message and confirm only the selected recipient displays the message.
6. Connect and disconnect a client; confirm join/leave notices and online lists update.
7. Close a client unexpectedly; confirm the server continues and removes that user.
8. Stop the server and try to connect; confirm the client reports an error without freezing.
9. Repeat on computers using the same Wi-Fi network.

## Networking concepts in this implementation

- **LAN:** the shared local network connecting the server and client computers.
- **TCP/IP:** IP provides host addressing and TCP provides a reliable, ordered connection between sockets.
- **Socket programming:** `server.py` creates, binds, listens, and accepts; `client.py` opens a connection and exchanges bytes.
- **Client-server architecture:** clients initiate connections; the server accepts connections and routes messages.
- **IP address and port:** the client uses the server's LAN IPv4 address and TCP port to reach the listening service.
- **TCP three-way handshake:** the operating system establishes the TCP connection before the application sends its login JSON.
- **Connection-oriented communication:** each logged-in client maintains a TCP socket until it disconnects or the server stops.
- **Multithreading:** server handler threads isolate client reads; a client receiver thread prevents network waiting from blocking Tkinter.
- **Broadcast and unicast:** group messages go to all logged-in sockets; private messages go to one recipient socket.
- **Data transmission and protocol:** UTF-8 JSON carries typed fields, while newline framing identifies each message boundary.

## Limitations

This lab version has no encryption, password authentication, durable message history, or file transfer. Online status and chat history are held in memory. Use only on a trusted LAN and do not send passwords or sensitive information.
