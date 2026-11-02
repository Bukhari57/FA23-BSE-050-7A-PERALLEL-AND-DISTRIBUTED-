# Distributed Task Offloading and Remote GPU Rendering System

This project implements a client-server distributed render system for the CSC-334 assignment. It allows a resource-constrained client machine to submit heavy media transcoding tasks to a more capable remote worker that can accelerate rendering with FFmpeg NVENC/CUDA when available.

## Features

- Client-side desktop GUI for job submission
- Direct LAN/Wi-Fi connection setup with handshake and latency check
- Remote worker daemon with a socket-based task queue
- FFmpeg-based GPU transcoding using `h264_nvenc` when available
- Real-time job progress and log streaming back to the client
- File integrity validation with SHA-256 checksums
- Graceful timeout and disconnect handling
- Benchmark script for comparing local vs remote execution

## Architecture

- `client/` contains the desktop GUI and socket client logic
- `server/` contains the daemon, queue, and GPU execution runner
- `shared/` contains the message protocol helpers used by both ends

## Repository Layout

- `client/gui_app.py` — desktop GUI app
- `server/daemon.py` — remote worker service
- `shared/network_protocol.py` — JSON message protocol helpers
- `run_client.py` — launch the client app
- `run_server.py` — launch the server daemon
- `scripts/benchmark.py` — performance benchmark harness

## Requirements

### Server machine

- Windows, Linux, or macOS
- Python 3.10+
- FFmpeg installed and available in PATH
- NVIDIA GPU recommended for NVENC acceleration

### Client machine

- Python 3.10+
- Network connectivity to the remote machine over Ethernet or Wi-Fi

## Setup

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. On macOS with Homebrew Python 3.14, install Tkinter:

   ```bash
   brew install python-tk@3.14
   ```

   Tkinter is provided separately from Homebrew Python. Install the matching
   `python-tk` package before launching the client GUI.

4. Install FFmpeg:

   - Ubuntu/Debian: `sudo apt install ffmpeg`
   - Fedora: `sudo dnf install ffmpeg`
   - Windows: download from https://www.ffmpeg.org/download.html and add to PATH

## Network Configuration Guide

Use a direct LAN connection between the client and the remote worker. A typical setup is:

- Server IP: `192.168.1.1`
- Client IP: `192.168.1.2`
- Subnet mask: `255.255.255.0`

### Windows setup example

```powershell
# Server machine
New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.1.1 -PrefixLength 24

# Client machine
New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.1.2 -PrefixLength 24
```

### Linux setup example

```bash
sudo ip addr add 192.168.1.1/24 dev eth0
```

Then test connectivity:

```bash
ping 192.168.1.1
```

## Running the System

### 1. Start the remote daemon

```bash
python run_server.py --host 0.0.0.0 --port 5005
```

The server will listen for client connections, perform a handshake, and start processing render jobs.

### 2. Start the client GUI

```bash
python run_client.py
```

In the GUI:

- Enter the server IP address and port
- Select the input media file
- Choose the output location
- Set resolution, preset, and bitrate
- Connect to the remote server
- Submit the job

## Job Behavior

The remote service accepts a transcoding request such as:

```json
{
  "type": "job",
  "input_path": "C:/videos/input.mp4",
  "output_path": "C:/videos/output.mp4",
  "width": 1920,
  "height": 1080,
  "bitrate": "8M",
  "preset": "fast",
  "codec": "h264_nvenc"
}
```

The daemon attempts to run:

```bash
ffmpeg -y -i input.mp4 -vf scale=1920:1080 -c:v h264_nvenc -preset fast -b:v 8M output.mp4
```

If GPU acceleration is unavailable, the system falls back to a software encode mode and still keeps the same client-server protocol.

## Progress Tracking

The server sends progress as JSON messages while the ffmpeg process is running:

```json
{
  "type": "progress",
  "percent": 54,
  "status": "Transcoding...",
  "message": "Processing frame 1,200"
}
```

The client listens for these updates and refreshes the progress bar and logs.

## Robustness Features

- Socket timeouts on idle and connect phases
- File checksum validation after upload and after completion
- Graceful disconnect handling
- Safe fallbacks when ffmpeg is missing or GPU is unavailable
- Error logging for failed tasks

## Benchmarking

The benchmark script compares local execution vs remote execution:

```bash
python scripts/benchmark.py --input sample.mp4 --local-output local.mp4 --remote-output remote.mp4
```

Metrics captured include:

- Processing time
- Transfer time overhead
- Speedup factor
- Network throughput

The formula for speedup is:

```text
Speedup = Local Time / Remote Time
```

## Demo and Screenshots

### Server

<img width="692" height="497" alt="Screenshot 2026-11-02 at 5 56 56 AM" src="https://github.com/user-attachments/assets/632c4985-bea0-4a44-b6ec-42fa9ee1e6e1" />

### Client

<img width="1092" height="824" alt="Screenshot 2026-11-02 at 5 57 17 AM" src="https://github.com/user-attachments/assets/bdde44a7-486f-4715-b345-3491b96ebd62" />

### Successful Render

<img width="1092" height="824" alt="Screenshot 2026-11-02 at 5 57 37 AM" src="https://github.com/user-attachments/assets/6e61870e-fd88-4b73-a781-168df1e3b386" />

### Output

<img width="2862" height="1782" alt="image" src="https://github.com/user-attachments/assets/b38b955a-2399-4419-8736-a77efed10736" />

### Benchmarks

<img width="692" height="497" alt="Screenshot 2026-11-02 at 5 58 43 AM" src="https://github.com/user-attachments/assets/f22e3ff5-59b0-4280-bee2-f4edf616ba59" />

## License

This project is intended for academic coursework use.
