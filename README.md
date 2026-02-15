# AI System Benchmark

Cross-platform hardware benchmark for AI inference — **compare systems, not models**.

Uses a single standardized model (`llama3.1:8b`) via [Ollama](https://ollama.com) to produce comparable performance scores across any hardware: NVIDIA, AMD, Intel, Apple Silicon, or CPU-only.

## Quick Start

Just run the script — it handles everything automatically (installs Ollama if needed, downloads the model, runs the benchmark):

```bash
python run.py
```

## What It Measures

### Performance Score (primary ranking metric)

The single headline number used to rank devices on a leaderboard. Calculated as:

```
Performance Score = (Avg Prompt Eval tok/s * 0.3) + (Avg Generation tok/s * 0.7)
```

Weighted toward generation speed since that's what users feel most during interactive use. **Higher is better.**

### Generation Speed (avg tok/s)

How fast the system generates output tokens — this is the speed at which text appears to the user. The most user-visible metric and the primary component of the performance score. **Higher is better.**

### Prompt Eval Speed (avg tok/s)

How fast the system processes the input prompt. Matters for long-context use cases like RAG and document analysis. **Higher is better.**

### Time to First Token — TTFT (avg ms)

The latency before the first token appears. Measures responsiveness — critical for interactive chat UX. **Lower is better.**

### Power Draw (avg watts)

GPU power consumption during the benchmark, measured via `nvidia-smi` (NVIDIA), `rocm-smi` (AMD Linux), or `powermetrics` (Apple Silicon). Not available on all platforms. Reported as average, min, and max watts.

### Efficiency Score (tok/s per watt)

Performance per watt of power consumed. Calculated as:

```
Efficiency Score = Performance Score / Avg Watts
```

Only available when power monitoring is supported. Great for comparing Apple Silicon (low power, good performance) vs discrete GPUs (high power, high performance). **Higher is better.**

### What's NOT important for comparison

- **Total Tokens / Duration** — artifacts of test length, not comparable across systems
- **Per-prompt breakdowns** — useful for debugging but too granular for a leaderboard
- **Load duration** — varies by whether the model was already cached in memory

## Key Metrics Summary

| Metric | Payload Field | Unit | Direction |
|---|---|---|---|
| **Performance Score** | `scores.performance_score` | points | Higher = better |
| **Generation Speed** | `scores.avg_eval_tps` | tok/s | Higher = better |
| **Prompt Eval Speed** | `scores.avg_prompt_eval_tps` | tok/s | Higher = better |
| **Time to First Token** | `scores.avg_ttft_ms` | ms | Lower = better |
| **Efficiency** | `scores.efficiency_score` | tok/s/W | Higher = better |
| **Power Draw** | `power.avg_watts` | watts | Context only |

## Prerequisites

- **Python 3.10+** — the only requirement. Everything else is handled automatically.
- Ollama is **automatically downloaded and installed** if not present.
- The benchmark model is **automatically pulled** on first run.

## Usage

### One-command run (recommended)

Works on Windows, macOS, and Linux. Handles everything: installs Ollama, creates a virtual environment, installs dependencies, pulls the model, and runs the benchmark.

```bash
python run.py
```

Platform-specific alternatives:

```bash
# Windows — double-click or run in cmd
run.bat

# Linux / macOS
chmod +x run.sh && ./run.sh
```

### Advanced CLI usage

If you prefer manual control, install dependencies first:

```bash
pip install -r requirements.txt
pip install -e .
```

Then use the CLI directly:

```bash
ai-benchmark run                    # Run benchmark and submit results
ai-benchmark run --no-submit        # Run without submitting
ai-benchmark run --endpoint URL     # Submit to a custom endpoint
ai-benchmark sysinfo                # Show detected hardware info
ai-benchmark payload-preview        # Preview the JSON payload
```

### Cleanup / Uninstall

Remove the benchmark model, Ollama data, and optionally uninstall Ollama to free disk space:

```bash
ai-benchmark cleanup                # Full uninstall (model + data + Ollama)
ai-benchmark cleanup --model-only   # Only remove the benchmark model
ai-benchmark cleanup --keep-ollama  # Remove model + data, keep Ollama installed
ai-benchmark cleanup --remove-venv  # Also remove the Python virtual environment
ai-benchmark cleanup --yes          # Skip confirmation prompt
```

## Payload Structure

The benchmark submits the following JSON to your endpoint via POST:

```json
{
  "version": "1.0.0",
  "timestamp": "2025-02-16T00:00:00Z",
  "machine_uuid": "deterministic-uuid-from-hardware",
  "system": {
    "os": {
      "platform": "Windows",
      "os_name": "Windows",
      "os_version": "Microsoft Windows 11 Pro",
      "architecture": "AMD64"
    },
    "cpu": {
      "cpu_name": "AMD Ryzen 9 7950X",
      "physical_cores": 16,
      "logical_cores": 32
    },
    "ram": {
      "total_gb": 64.0,
      "available_gb": 48.2
    },
    "gpu": [
      {
        "vendor": "NVIDIA",
        "name": "NVIDIA GeForce RTX 4090",
        "vram_mb": 24564,
        "driver": "546.33"
      }
    ]
  },
  "ollama_version": "0.6.2",
  "benchmark": {
    "model": "llama3.1:8b",
    "duration_s": 42.5
  },
  "scores": {
    "performance_score": 44.02,
    "efficiency_score": 0.1834,
    "avg_prompt_eval_tps": 71.11,
    "avg_eval_tps": 32.41,
    "avg_ttft_ms": 600.0,
    "total_tokens_generated": 1280,
    "total_prompt_tokens": 160,
    "prompts_completed": 5
  },
  "power": {
    "available": true,
    "method": "nvidia-smi",
    "avg_watts": 240.0,
    "max_watts": 280.0,
    "min_watts": 200.0,
    "samples": 15
  },
  "results": [
    {
      "prompt_id": "instruct_code",
      "category": "Code Generation",
      "total_duration_ms": 8500.0,
      "load_duration_ms": 150.0,
      "prompt_eval_count": 32,
      "prompt_eval_duration_ms": 450.0,
      "prompt_eval_tps": 71.11,
      "eval_count": 256,
      "eval_duration_ms": 7900.0,
      "eval_tps": 32.41,
      "ttft_ms": 600.0
    }
  ]
}
```

## Supported Hardware

| Platform | GPU Detection | Power Monitoring |
|---|---|---|
| NVIDIA (Windows/Linux) | nvidia-smi | nvidia-smi |
| AMD (Linux) | rocm-smi / rocminfo | rocm-smi |
| AMD (Windows) | WMI fallback | Not available |
| Intel Arc/iGPU | lspci / WMI | Not available |
| Apple Silicon | system_profiler | powermetrics (sudo) |
| CPU-only | N/A | Not available |

## License

MIT
