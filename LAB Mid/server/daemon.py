import argparse
import base64
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

from shared.network_protocol import recv_json, send_json, sha256_file


class RenderWorker:
    def __init__(self, host: str = "0.0.0.0", port: int = 5005):
        self.host = host
        self.port = port
        self.client_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.shutdown_event = threading.Event()
        self.ffmpeg_path = self._detect_ffmpeg()

    def _detect_ffmpeg(self) -> Optional[str]:
        for candidate in ("ffmpeg", "C:/ffmpeg/bin/ffmpeg.exe", "C:/ffmpeg/bin/ffmpeg"):
            try:
                subprocess.run([candidate, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                return candidate
            except OSError:
                continue
        return None

    def _find_gpu_mode(self) -> str:
        if self.ffmpeg_path is None:
            return "software"

        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=10,
            )
            if "h264_nvenc" in result.stdout or "hevc_nvenc" in result.stdout:
                return "nvenc"
        except (subprocess.SubprocessError, OSError):
            return "software"
        return "software"

    def _build_command(self, config: Dict[str, Any]) -> list[str]:
        input_path = config["input_path"]
        output_path = config["output_path"]
        width = int(config.get("width") or 1920)
        height = int(config.get("height") or 1080)
        bitrate = str(config.get("bitrate") or "8M")
        preset = str(config.get("preset") or "fast")
        requested_codec = str(config.get("codec") or "h264_nvenc")
        codec = requested_codec
        if requested_codec in {"h264_nvenc", "hevc_nvenc"} and self._find_gpu_mode() != "nvenc":
            codec = "libx264" if requested_codec == "h264_nvenc" else "libx265"

        if self.ffmpeg_path is None:
            raise FileNotFoundError("FFmpeg is not installed or not available in PATH.")

        command = [
            self.ffmpeg_path,
            "-y",
            "-i",
            input_path,
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            codec,
            "-preset",
            preset,
            "-b:v",
            bitrate,
            "-an",
            output_path,
        ]

        return command

    def _parse_duration(self, input_path: str) -> Optional[float]:
        if self.ffmpeg_path is None:
            return None

        probe_cmd = [
            self.ffmpeg_path,
            "-i",
            input_path,
            "-f",
            "null",
            "-",
        ]
        try:
            result = subprocess.run(
                probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=20,
            )
            match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr or "")
            if match:
                hours, minutes, seconds = match.groups()
                return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        except (subprocess.SubprocessError, OSError):
            return None
        return None

    def _parse_progress(self, line: str, total_duration: Optional[float]) -> Optional[int]:
        if "time=" not in line:
            return None
        match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
        if not match:
            return None
        hours, minutes, seconds = match.groups()
        elapsed = float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        if total_duration and total_duration > 0:
            return min(100, max(0, int((elapsed / total_duration) * 100)))
        return None

    def _process_job(self, connection: socket.socket, config: Dict[str, Any]) -> None:
        input_path = config["input_path"]
        output_path = config["output_path"]

        if not os.path.exists(input_path):
            send_json(connection, {"type": "error", "message": f"Input file not found: {input_path}"})
            return

        if self.ffmpeg_path is None:
            send_json(connection, {"type": "error", "message": "FFmpeg is not installed. Please install FFmpeg to process the job."})
            return

        try:
            cmd = self._build_command(config)
            total_duration = self._parse_duration(input_path)
            send_json(connection, {"type": "job_received", "message": "Remote worker accepted the job."})
            send_json(connection, {"type": "status", "status": "transcoding", "message": f"Using {self._find_gpu_mode()} mode"})

            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            ) as proc:
                while True:
                    line = proc.stdout.readline() if proc.stdout else ""
                    if not line and proc.poll() is not None:
                        break
                    if not line:
                        continue
                    progress = self._parse_progress(line, total_duration)
                    if progress is not None:
                        send_json(connection, {
                            "type": "progress",
                            "percent": progress,
                            "status": "Transcoding",
                            "message": line.strip(),
                        })
                    else:
                        send_json(connection, {
                            "type": "log",
                            "message": line.strip(),
                        })

                return_code = proc.wait(timeout=60)
                if return_code != 0:
                    send_json(connection, {"type": "error", "message": f"Remote render failed with exit code {return_code}."})
                    return

            if not os.path.exists(output_path):
                send_json(connection, {"type": "error", "message": "Output file was not created."})
                return

            checksum = sha256_file(output_path)
            file_size = os.path.getsize(output_path)
            with open(output_path, "rb") as file_obj:
                while True:
                    chunk = file_obj.read(65536)
                    if not chunk:
                        break
                    payload = base64.b64encode(chunk).decode("ascii")
                    send_json(connection, {
                        "type": "file_chunk",
                        "data": payload,
                        "final": False,
                    })

            send_json(connection, {
                "type": "file_chunk",
                "data": "",
                "final": True,
                "checksum": checksum,
                "file_size": file_size,
                "status": "complete",
            })
            send_json(connection, {
                "type": "job_complete",
                "checksum": checksum,
                "file_size": file_size,
                "output_path": output_path,
                "message": "Render completed successfully.",
            })
        except Exception as exc:  # pragma: no cover - runtime pathway
            send_json(connection, {"type": "error", "message": str(exc)})

    def _serve_client(self, connection: socket.socket, address: str) -> None:
        try:
            connection.settimeout(10)
            message = recv_json(connection, timeout=10)
            if message is None:
                send_json(connection, {"type": "error", "message": "No handshake received."})
                return

            if message.get("type") == "handshake":
                send_json(connection, {
                    "type": "handshake_ack",
                    "status": "ready",
                    "gpu_mode": self._find_gpu_mode(),
                    "ffmpeg_available": self.ffmpeg_path is not None,
                    "host": self.host,
                    "port": self.port,
                })

            while True:
                message = recv_json(connection, timeout=20)
                if message is None:
                    break
                if message.get("type") == "ping":
                    send_json(connection, {"type": "pong", "client_time": message.get("ts"), "server_time": time.time()})
                    continue
                if message.get("type") == "job":
                    self._process_job(connection, message)
                    continue
                if message.get("type") == "disconnect":
                    break
        except (ConnectionError, OSError, ValueError) as exc:
            send_json(connection, {"type": "error", "message": f"Socket closed: {exc}"})
        finally:
            connection.close()
            print(f"Closed connection for {address}")

    def start(self) -> None:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(10)
        print(f"Remote worker listening on {self.host}:{self.port}")
        print(f"GPU mode detected: {self._find_gpu_mode()}")

        try:
            while not self.shutdown_event.is_set():
                server_socket.settimeout(1)
                try:
                    connection, address = server_socket.accept()
                except socket.timeout:
                    continue
                worker = threading.Thread(target=self._serve_client, args=(connection, str(address)), daemon=True)
                worker.start()
        finally:
            server_socket.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed GPU rendering daemon.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5005)
    args = parser.parse_args()

    worker = RenderWorker(host=args.host, port=args.port)
    try:
        worker.start()
    except KeyboardInterrupt:
        print("Shutting down worker daemon.")
        sys.exit(0)


if __name__ == "__main__":
    main()
