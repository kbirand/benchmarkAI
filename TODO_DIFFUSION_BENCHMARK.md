# Image Generation Benchmark — TODO

A separate one-command benchmark for image generation performance, similar to `run.py` for LLM inference.

## Goal

```bash
python run_diffusion.py
```

One command that auto-installs everything, runs a standardized image generation test, and outputs a comparable score.

## Model

**Stable Diffusion 1.5** (`runwayml/stable-diffusion-v1-5`)
- ~4 GB download
- Fits in 8GB VRAM
- Well-supported on all PyTorch backends
- Standardized and deterministic with fixed seeds

## Metrics to Capture

| Metric | Description | Direction |
|---|---|---|
| **Images/min** | Throughput — images generated per minute | Higher = better |
| **Time per image** | Latency per 512x512 image (seconds) | Lower = better |
| **Steps/second** | Diffusion steps per second (granular) | Higher = better |
| **VRAM peak** | Peak GPU memory during generation | Context only |
| **Power draw** | Avg/max/min watts during generation | Context only |
| **Efficiency** | Images per minute per watt | Higher = better |

## Platform Support

| Platform | PyTorch Backend | Install Command |
|---|---|---|
| NVIDIA (CUDA) | `torch` + CUDA | `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| Apple Silicon | `torch` + MPS | `pip install torch` (MPS included by default) |
| AMD Linux | `torch` + ROCm | `pip install torch --index-url https://download.pytorch.org/whl/rocm6.0` |
| AMD Windows | `torch-directml` | `pip install torch-directml` |
| Intel Arc | IPEX / XPU | `pip install intel-extension-for-pytorch` |
| CPU-only | `torch` CPU | `pip install torch --index-url https://download.pytorch.org/whl/cpu` |

## Build Steps

### 1. Bootstrap script (`run_diffusion.py`)
- [ ] Check Python version (3.10+)
- [ ] Create `.venv_diffusion` (separate from LLM benchmark venv)
- [ ] Auto-detect GPU vendor (NVIDIA/AMD/Apple/Intel/CPU)
- [ ] Install correct PyTorch variant based on detected GPU
- [ ] Install `diffusers`, `accelerate`, `transformers`
- [ ] Download SD 1.5 from HuggingFace (with progress)
- [ ] Run benchmark
- [ ] Output `benchmark_diffusion_result.json`

### 2. Benchmark runner
- [ ] 5 fixed prompts with fixed seeds for reproducibility
- [ ] 512x512 resolution, 30 inference steps (standardized)
- [ ] Warm-up pass (1 image, discarded)
- [ ] Measure per-image timing
- [ ] Capture power draw (reuse `power_monitor.py` from LLM benchmark)
- [ ] Calculate scores

### 3. GPU detection & PyTorch install
- [ ] Detect NVIDIA via `nvidia-smi`
- [ ] Detect Apple Silicon via `platform.machine() == 'arm64'` + `platform.system() == 'Darwin'`
- [ ] Detect AMD via `rocminfo` (Linux) or WMI (Windows)
- [ ] Detect Intel via `lspci` / WMI
- [ ] Fallback to CPU

### 4. Result payload
- [ ] Same structure as LLM benchmark (system info, scores, power, per-prompt results)
- [ ] Add diffusion-specific fields: resolution, steps, scheduler, model name
- [ ] Submit to same endpoint (or separate diffusion endpoint)

### 5. Cleanup
- [ ] `cleanup_diffusion` command to remove model cache (~4GB) and venv

## Challenges

- **PyTorch install size**: ~2-3 GB for PyTorch alone + ~4 GB for the model
- **Backend detection**: Must correctly identify which PyTorch variant to install
- **DirectML (AMD Windows)**: Experimental, may have issues
- **Intel Arc**: Limited support, may need special handling
- **Run time**: ~30-120 seconds vs ~5 seconds for LLM benchmark

## Dependencies

```
torch (platform-specific)
diffusers
accelerate
transformers
psutil
requests
rich
```
