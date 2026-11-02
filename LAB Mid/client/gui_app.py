import base64
import hashlib
import os
import socket
import tempfile
import threading
import time
from tkinter import filedialog, ttk

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover - fallback for minimal environments
    ctk = None
    import tkinter as tk

from shared.network_protocol import recv_json, send_json


class DistributedRenderClient:
    def __init__(self, root):
        self.root = root
        self.sock = None
        self.connected = False
        self.download_path = None
        self.download_temp_path = None
        self.output_file = None
        self.job_thread = None
        self._build_ui()

    def _build_ui(self):
        if ctk is not None:
            self.root.title("Distributed GPU Offloading Client")
            self.root.geometry("980x680")
            self.root.minsize(900, 620)
            self.root.grid_columnconfigure(0, weight=1)
            self.root.grid_rowconfigure(0, weight=1)

            self.main_frame = ctk.CTkFrame(self.root)
            self.main_frame.pack(fill="both", expand=True, padx=16, pady=16)

            self.main_frame.grid_columnconfigure(0, weight=1)
            self.main_frame.grid_columnconfigure(1, weight=1)
            self.main_frame.grid_rowconfigure(0, weight=0)
            self.main_frame.grid_rowconfigure(1, weight=0)
            self.main_frame.grid_rowconfigure(2, weight=0)
            self.main_frame.grid_rowconfigure(3, weight=1)

            self.title = ctk.CTkLabel(self.main_frame, text="Remote GPU Render Client", font=("Segoe UI", 20, "bold"))
            self.title.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))

            self.connection_frame = ctk.CTkFrame(self.main_frame)
            self.connection_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
            self.connection_frame.grid_columnconfigure(1, weight=1)

            self.host_label = ctk.CTkLabel(self.connection_frame, text="Server IP")
            self.host_label.grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")
            self.host_var = ctk.StringVar(value="127.0.0.1")
            self.host_entry = ctk.CTkEntry(self.connection_frame, textvariable=self.host_var)
            self.host_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))

            self.port_label = ctk.CTkLabel(self.connection_frame, text="Port")
            self.port_label.grid(row=0, column=2, padx=(12, 8), pady=10, sticky="w")
            self.port_var = ctk.StringVar(value="5005")
            self.port_entry = ctk.CTkEntry(self.connection_frame, textvariable=self.port_var, width=120)
            self.port_entry.grid(row=0, column=3, sticky="w", padx=(0, 12))

            self.connect_button = ctk.CTkButton(self.connection_frame, text="Connect", command=self.connect_to_server)
            self.connect_button.grid(row=0, column=4, padx=(0, 12), pady=10)

            self.input_frame = ctk.CTkFrame(self.main_frame)
            self.input_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
            self.input_frame.grid_columnconfigure(1, weight=1)

            self.input_label = ctk.CTkLabel(self.input_frame, text="Input File")
            self.input_label.grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")
            self.input_var = ctk.StringVar(value="")
            self.input_entry = ctk.CTkEntry(self.input_frame, textvariable=self.input_var)
            self.input_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
            self.browse_button = ctk.CTkButton(self.input_frame, text="Browse", command=self.browse_input)
            self.browse_button.grid(row=0, column=2, padx=(0, 12), pady=10)

            self.output_label = ctk.CTkLabel(self.input_frame, text="Output File")
            self.output_label.grid(row=1, column=0, padx=(12, 8), pady=(0, 10), sticky="w")
            self.output_var = ctk.StringVar(value="")
            self.output_entry = ctk.CTkEntry(self.input_frame, textvariable=self.output_var)
            self.output_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 10))
            self.output_button = ctk.CTkButton(self.input_frame, text="Choose", command=self.choose_output)
            self.output_button.grid(row=1, column=2, padx=(0, 12), pady=(0, 10))

            self.config_frame = ctk.CTkFrame(self.main_frame)
            self.config_frame.grid(row=3, column=0, sticky="nsew", padx=(12, 6), pady=8)
            self.config_frame.grid_columnconfigure(0, weight=1)
            self.config_frame.grid_rowconfigure(2, weight=1)

            self.settings_label = ctk.CTkLabel(self.config_frame, text="Render Settings", font=("Segoe UI", 16, "bold"))
            self.settings_label.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="w")

            self.resolution_label = ctk.CTkLabel(self.config_frame, text="Resolution")
            self.resolution_label.grid(row=1, column=0, padx=12, sticky="w")
            self.resolution_var = ctk.StringVar(value="1920x1080")
            self.resolution_entry = ctk.CTkEntry(self.config_frame, textvariable=self.resolution_var)
            self.resolution_entry.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

            self.bitrate_label = ctk.CTkLabel(self.config_frame, text="Bitrate")
            self.bitrate_label.grid(row=2, column=0, padx=12, sticky="w")
            self.bitrate_var = ctk.StringVar(value="8M")
            self.bitrate_entry = ctk.CTkEntry(self.config_frame, textvariable=self.bitrate_var)
            self.bitrate_entry.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="ew")

            self.preset_label = ctk.CTkLabel(self.config_frame, text="Preset")
            self.preset_label.grid(row=4, column=0, padx=12, sticky="w")
            self.preset_var = ctk.StringVar(value="fast")
            self.preset_entry = ctk.CTkEntry(self.config_frame, textvariable=self.preset_var)
            self.preset_entry.grid(row=5, column=0, padx=12, pady=(0, 10), sticky="ew")

            self.submit_button = ctk.CTkButton(self.config_frame, text="Submit Job", command=self.submit_job)
            self.submit_button.grid(row=6, column=0, padx=12, pady=(6, 10), sticky="ew")

            self.console_frame = ctk.CTkFrame(self.main_frame)
            self.console_frame.grid(row=3, column=1, sticky="nsew", padx=(6, 12), pady=8)
            self.console_frame.grid_columnconfigure(0, weight=1)
            self.console_frame.grid_rowconfigure(1, weight=1)

            self.progress_var = ctk.DoubleVar(value=0)
            self.progress_bar = ctk.CTkProgressBar(self.console_frame, variable=self.progress_var, progress_color="#5AA9FF")
            self.progress_bar.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
            self.progress_bar.set(0)

            self.log_box = ctk.CTkTextbox(self.console_frame, height=25, wrap="word")
            self.log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
            self.log_box.insert("end", "System ready. Connect to a worker node to begin.\n")
        else:
            self.root.title("Distributed GPU Offloading Client")
            self.root.geometry("980x680")
            self.root.minsize(900, 620)
            self.main_frame = tk.Frame(self.root, padx=16, pady=16)
            self.main_frame.pack(fill="both", expand=True)

            self.title = tk.Label(self.main_frame, text="Remote GPU Render Client", font=("Segoe UI", 20, "bold"))
            self.title.pack(anchor="w")

            connection = tk.LabelFrame(self.main_frame, text="Connection")
            connection.pack(fill="x", pady=(8, 10))

            host_row = tk.Frame(connection)
            host_row.pack(fill="x", padx=10, pady=6)
            tk.Label(host_row, text="Server IP").pack(side="left")
            self.host_var = tk.StringVar(value="127.0.0.1")
            tk.Entry(host_row, textvariable=self.host_var).pack(side="left", fill="x", expand=True)
            tk.Label(host_row, text="Port").pack(side="left", padx=(12, 4))
            self.port_var = tk.StringVar(value="5005")
            tk.Entry(host_row, textvariable=self.port_var, width=8).pack(side="left")
            tk.Button(host_row, text="Connect", command=self.connect_to_server).pack(side="left", padx=(12, 0))

            input_frame = tk.LabelFrame(self.main_frame, text="Job")
            input_frame.pack(fill="x", pady=(0, 10))
            row = tk.Frame(input_frame)
            row.pack(fill="x", padx=10, pady=6)
            tk.Label(row, text="Input File").pack(side="left")
            self.input_var = tk.StringVar(value="")
            tk.Entry(row, textvariable=self.input_var).pack(side="left", fill="x", expand=True)
            tk.Button(row, text="Browse", command=self.browse_input).pack(side="left", padx=(8, 0))

            row2 = tk.Frame(input_frame)
            row2.pack(fill="x", padx=10, pady=6)
            tk.Label(row2, text="Output File").pack(side="left")
            self.output_var = tk.StringVar(value="")
            tk.Entry(row2, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
            tk.Button(row2, text="Choose", command=self.choose_output).pack(side="left", padx=(8, 0))

            config = tk.LabelFrame(self.main_frame, text="Render Settings")
            config.pack(fill="x")
            self.resolution_var = tk.StringVar(value="1920x1080")
            self.bitrate_var = tk.StringVar(value="8M")
            self.preset_var = tk.StringVar(value="fast")

            for label_name, var_name in [("Resolution", "resolution_var"), ("Bitrate", "bitrate_var"), ("Preset", "preset_var")]:
                row = tk.Frame(config)
                row.pack(fill="x", padx=10, pady=6)
                tk.Label(row, text=label_name, width=12).pack(side="left")
                entry = tk.Entry(row, textvariable=getattr(self, var_name))
                entry.pack(fill="x", expand=True)

            tk.Button(config, text="Submit Job", command=self.submit_job).pack(fill="x", padx=10, pady=(8, 10))

            self.progress_var = tk.DoubleVar(value=0)
            self.progress_bar = ttk.Progressbar(self.main_frame, mode="determinate", maximum=100, variable=self.progress_var)
            self.progress_bar.pack(fill="x", pady=(10, 4))

            self.log_box = tk.Text(self.main_frame, height=16, wrap="word")
            self.log_box.pack(fill="both", expand=True)
            self.log_box.insert("end", "System ready. Connect to a worker node to begin.\n")

    def log(self, message: str):
        if ctk is not None:
            self.log_box.insert("end", f"{message}\n")
            self.log_box.see("end")
            self.root.update_idletasks()
        else:
            self.log_box.insert("end", f"{message}\n")
            self.log_box.see("end")
            self.root.update_idletasks()

    def browse_input(self):
        chosen = filedialog.askopenfilename(title="Select input media file")
        if chosen:
            self.input_var.set(chosen)

    def choose_output(self):
        chosen = filedialog.asksaveasfilename(defaultextension=".mp4", title="Select render output path")
        if chosen:
            self.output_var.set(chosen)

    def connect_to_server(self):
        host = self.host_var.get().strip()
        port = int(self.port_var.get())
        try:
            self.sock = socket.create_connection((host, port), timeout=5)
            self.sock.settimeout(10)
            send_json(self.sock, {"type": "handshake", "client": "python-client", "ts": time.time()})
            ack = recv_json(self.sock, timeout=10)
            if not ack or ack.get("type") != "handshake_ack":
                raise RuntimeError("Handshake failed. The remote daemon is not responding correctly.")
            send_json(self.sock, {"type": "ping", "ts": time.time()})
            pong = recv_json(self.sock, timeout=10)
            if not pong:
                raise RuntimeError("Latency check timed out.")
            latency_ms = max(1, int((time.time() - float(pong.get("client_time", time.time()))) * 1000))
            self.connected = True
            self.log(f"Connected to {host}:{port}. Latency: {latency_ms} ms")
            self.log(f"Remote worker mode: {ack.get('gpu_mode', 'unknown')}")
        except Exception as exc:
            self.connected = False
            self.log(f"Connection failed: {exc}")

    def submit_job(self):
        if not self.connected or self.sock is None:
            self.log("You must connect before submitting a remote render job.")
            return

        input_path = self.input_var.get().strip()
        output_path = self.output_var.get().strip()
        if not input_path or not os.path.exists(input_path):
            self.log("Please choose a valid input file before submitting.")
            return
        if not output_path:
            self.log("Please choose an output file path before submitting.")
            return

        width, height = self._parse_resolution(self.resolution_var.get())
        job = {
            "type": "job",
            "input_path": input_path,
            "output_path": output_path,
            "width": width,
            "height": height,
            "bitrate": self.bitrate_var.get().strip() or "8M",
            "preset": self.preset_var.get().strip() or "fast",
            "codec": "h264_nvenc",
        }
        self.download_path = output_path
        self.download_temp_path = None
        self.progress_var.set(0)
        self.log("Submitting render job to remote worker...")
        send_json(self.sock, job)
        self.job_thread = threading.Thread(target=self._listen_for_updates, daemon=True)
        self.job_thread.start()

    def _parse_resolution(self, value: str):
        parts = value.lower().replace(" ", "").split("x")
        if len(parts) != 2:
            return 1920, 1080
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return 1920, 1080

    def _listen_for_updates(self):
        while self.sock:
            try:
                message = recv_json(self.sock, timeout=15)
            except socket.timeout:
                continue
            if message is None:
                self.log("Connection closed by server.")
                break

            message_type = message.get("type")
            if message_type == "progress":
                percent = message.get("percent", 0)
                self.root.after(0, self._update_progress, percent, message.get("message", "Processing..."))
            elif message_type == "log":
                self.root.after(0, self.log, message.get("message", "Remote log update"))
            elif message_type == "job_received":
                self.root.after(0, self.log, message.get("message", "Remote worker accepted the job."))
            elif message_type == "status":
                self.root.after(0, self.log, message.get("message", f"Status: {message.get('status', 'processing')}"))
            elif message_type == "job_complete":
                self.root.after(0, self.log, message.get("message", "Render completed successfully."))
                self.root.after(0, self._update_progress, 100, "Render complete")
                self.root.after(0, self.log, f"Checksum: {message.get('checksum', 'n/a')}")
                break
            elif message_type == "error":
                self.root.after(0, self.log, f"Error: {message.get('message', 'Unknown remote failure')}")
                break
            elif message_type == "file_chunk":
                if self.output_file is None and self.download_path:
                    output_dir = os.path.dirname(os.path.abspath(self.download_path))
                    output_name = os.path.basename(self.download_path)
                    file_descriptor, self.download_temp_path = tempfile.mkstemp(
                        prefix=f".{output_name}.",
                        suffix=".part",
                        dir=output_dir,
                    )
                    self.output_file = os.fdopen(file_descriptor, "wb")
                if self.output_file is not None and message.get("data"):
                    self.output_file.write(base64.b64decode(message["data"]))
                if message.get("final"):
                    if self.output_file is not None:
                        self.output_file.close()
                        self.output_file = None
                    expected_checksum = message.get("checksum")
                    actual_checksum = (
                        self._sha256_file(self.download_temp_path)
                        if self.download_temp_path
                        else None
                    )
                    if expected_checksum and actual_checksum != expected_checksum:
                        if self.download_temp_path:
                            os.unlink(self.download_temp_path)
                        self.download_temp_path = None
                        self.root.after(0, self.log, "Downloaded output failed checksum verification.")
                        continue
                    if self.download_temp_path and self.download_path:
                        os.replace(self.download_temp_path, self.download_path)
                    self.download_temp_path = None
                    self.root.after(0, self.log, "Remote output file downloaded successfully.")

    @staticmethod
    def _sha256_file(file_path):
        digest = hashlib.sha256()
        with open(file_path, "rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _update_progress(self, percent, message):
        self.progress_var.set(min(100, max(0, int(percent))))
        self.log(f"Progress: {int(percent)}% - {message}")

    def disconnect(self):
        if self.sock is not None:
            try:
                send_json(self.sock, {"type": "disconnect"})
            except Exception:
                pass
            self.sock.close()
            self.sock = None
        self.connected = False


def main():
    if ctk is not None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
    else:
        import tkinter as tk
        root = tk.Tk()
    app = DistributedRenderClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
