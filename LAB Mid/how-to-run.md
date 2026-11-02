# How to Run the Project on macOS

This guide explains how to set up, run, and test the distributed rendering project on macOS.

## 1. Install prerequisites

Install Homebrew packages:

```bash
brew install python ffmpeg
```

Verify the installation:

```bash
python3 --version
ffmpeg -version
python3 -m tkinter
```

Python 3.10 or newer is required.

## 2. Open the project

```bash
cd "/Users/zainbukhari/Documents/7th Semester/Parallel and Distributed Computing/LAB Mid"
```

Create and activate a project virtual environment:

```bash
python3 -m venv .venv-mac
source .venv-mac/bin/activate
```

Install the Python dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Check the Python files

Run the syntax check:

```bash
python -m compileall client server shared run_client.py run_server.py
```

## 4. Start the server

Open Terminal 1, activate the environment, and start the server:

```bash
cd "/Users/zainbukhari/Documents/7th Semester/Parallel and Distributed Computing/LAB Mid"
source .venv-mac/bin/activate
python run_server.py --host 127.0.0.1 --port 5005
```

The server should display:

```text
Remote worker listening on 127.0.0.1:5005
```

Keep this terminal running.

## 5. Start the client GUI

Open Terminal 2:

```bash
cd "/Users/zainbukhari/Documents/7th Semester/Parallel and Distributed Computing/LAB Mid"
source .venv-mac/bin/activate
python run_client.py
```

In the GUI:

1. Set **Server IP** to `127.0.0.1`.
2. Set **Port** to `5005`.
3. Click **Connect**.
4. Select an input video.
5. Select an output `.mp4` path.
6. Choose settings, for example:
   - Resolution: `1280x720`
   - Bitrate: `4M`
   - Preset: `fast`
7. Click **Submit Job**.

The rendered output should be downloaded to the selected output path.

## 6. Create a test video

If you do not have an input video, create one with FFmpeg:

```bash
ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 \
  -pix_fmt yuv420p sample.mp4
```

Select `sample.mp4` in the client GUI.

## 7. Run the benchmark

With the virtual environment activated, run:

```bash
python scripts/benchmark.py \
  --input sample.mp4 \
  --local-output local.mp4 \
  --remote-output remote.mp4
```

You can change the resolution:

```bash
python scripts/benchmark.py \
  --input sample.mp4 \
  --local-output local.mp4 \
  --remote-output remote.mp4 \
  --width 1280 \
  --height 720
```

The benchmark compares local encoding time with a calculated remote execution estimate. The actual client-server rendering workflow should be tested through the GUI.

## 8. Testing on two Macs

On the Mac running the server, start it on all network interfaces:

```bash
python run_server.py --host 0.0.0.0 --port 5005
```

Find the server Mac's local IP address:

```bash
ipconfig getifaddr en0
```

On the client Mac:

1. Connect both Macs to the same Wi-Fi or LAN.
2. Start the client with `python run_client.py`.
3. Enter the server Mac's IP address in the **Server IP** field.
4. Enter port `5005`.
5. Click **Connect** and submit a test job.

Allow Python through the macOS firewall if macOS displays a security prompt. If the connection fails, verify that both Macs can reach each other:

```bash
ping SERVER_IP_ADDRESS
```

## Important limitation

The current implementation sends file paths in the job request rather than uploading the input file. Therefore, the input path must be accessible on the server Mac as well. Testing the client and server on the same Mac with `127.0.0.1` is the simplest reliable setup.

Most Macs do not have an NVIDIA GPU, so the server normally uses software encoding instead of `h264_nvenc`. FFmpeg must still be installed on the server Mac.
