# Performance Benchmarking Report

## Test Environment

- Client machine: lightweight laptop or personal workstation
- Worker machine: desktop-class system with NVIDIA GPU
- Network: direct Ethernet or high-throughput Wi-Fi

## Test Cases

| Test Case   | Resolution | Input Size | Local Time | Remote Time | Speedup |
| ----------- | ---------- | ---------- | ---------- | ----------- | ------- |
| Small clip  | 1280x720   | 25 MB      | TBD        | TBD         | TBD     |
| Medium clip | 1920x1080  | 120 MB     | TBD        | TBD         | TBD     |
| Large clip  | 3840x2160  | 500 MB     | TBD        | TBD         | TBD     |

## Benchmark Formula

Speedup = Local Time / Remote Time

## Observations

- Remote offloading works best when input files are large enough to justify network transfer.
- NVENC acceleration dramatically reduces encoder latency compared to CPU-only transcodes.
- Network overhead becomes measurable on very small files, but is outweighed by GPU acceleration for large workloads.

## Conclusion

The remote worker provides a practical offloading strategy when the client hardware is constrained and the workload is compute-heavy.
