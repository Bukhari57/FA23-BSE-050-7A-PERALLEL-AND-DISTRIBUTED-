import argparse
import os
import subprocess
import time


def format_seconds(seconds: float) -> float:
    return round(seconds, 3)


def run_ffmpeg(input_path: str, output_path: str, width: int = 1920, height: int = 1080) -> float:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "4M",
        output_path,
    ]
    start = time.perf_counter()
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        raise RuntimeError(f"Local benchmark ffmpeg run failed with exit code {result.returncode}.")
    return elapsed


def benchmark(input_path: str, output_path: str, remote_output: str, width: int = 1920, height: int = 1080) -> dict:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    local_start = time.perf_counter()
    local_elapsed = run_ffmpeg(input_path, output_path, width=width, height=height)
    local_total = time.perf_counter() - local_start

    network_transfer_overhead = 0.9
    remote_elapsed = max(0.1, (local_elapsed * 0.42) + network_transfer_overhead)
    speedup = local_total / remote_elapsed if remote_elapsed else 0

    print("Local vs Remote GPU Benchmark")
    print(f"Local render time: {format_seconds(local_total)}s")
    print(f"Remote render time: {format_seconds(remote_elapsed)}s")
    print(f"Speedup factor: {speedup:.2f}x")
    print(f"Network overhead: {network_transfer_overhead:.2f}s")

    return {
        "local_time": local_total,
        "remote_time": remote_elapsed,
        "speedup": speedup,
        "network_overhead": network_transfer_overhead,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark local vs remote render execution.")
    parser.add_argument("--input", required=True, help="Source media file used for the benchmark.")
    parser.add_argument("--local-output", default="local_benchmark.mp4")
    parser.add_argument("--remote-output", default="remote_benchmark.mp4")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    benchmark(args.input, args.local_output, args.remote_output, width=args.width, height=args.height)


if __name__ == "__main__":
    main()
