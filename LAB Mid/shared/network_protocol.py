import base64
import hashlib
import json
import os
import socket
import time
from typing import Any, Dict, Optional


def send_json(sock: socket.socket, payload: Dict[str, Any]) -> None:
    message = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header = len(message).to_bytes(4, byteorder="big", signed=False)
    sock.sendall(header + message)


def recv_json(sock: socket.socket, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
    if timeout is not None:
        sock.settimeout(timeout)

    try:
        header = sock.recv(4)
    except socket.timeout:
        return None

    if len(header) == 0:
        return None
    if len(header) < 4:
        raise ConnectionError("Incomplete network header received from remote socket.")

    payload_size = int.from_bytes(header, byteorder="big", signed=False)
    data = bytearray()
    while len(data) < payload_size:
        chunk = sock.recv(payload_size - len(data))
        if not chunk:
            raise ConnectionError("Socket closed while reading payload.")
        data.extend(chunk)

    try:
        return json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload received: {exc}") from exc


def sha256_file(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_parent_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def format_latency_ms(start_time: float) -> int:
    return max(1, int((time.time() - start_time) * 1000))
