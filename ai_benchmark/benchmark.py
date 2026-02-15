"""Benchmark runner using Ollama Python API for structured metrics."""

import time
import ollama
from .power_monitor import PowerMonitor

# The single standardized benchmark model
BENCHMARK_MODEL = "llama3.1:8b"

# Benchmark prompts — diverse workloads to stress different aspects
BENCHMARK_PROMPTS = [
    {
        "id": "instruct_code",
        "category": "Code Generation",
        "prompt": "Write a Python function that implements binary search on a sorted list. Include error handling and type hints.",
    },
    {
        "id": "reasoning",
        "category": "Reasoning",
        "prompt": "A farmer has 17 sheep. All but 9 run away. How many sheep does the farmer have left? Explain your reasoning step by step.",
    },
    {
        "id": "creative_writing",
        "category": "Creative Writing",
        "prompt": "Write a short story in exactly 3 paragraphs about a robot discovering music for the first time.",
    },
    {
        "id": "summarization",
        "category": "Summarization",
        "prompt": "Explain quantum computing to a 10-year-old in simple terms. Keep it under 100 words.",
    },
    {
        "id": "instruction_following",
        "category": "Instruction Following",
        "prompt": "List the top 5 largest countries by area. For each, provide the country name, continent, and approximate area in square kilometers. Format as a numbered list.",
    },
]


def ensure_model_available() -> bool:
    """Pull the benchmark model if not already present. Returns True if ready."""
    try:
        # Check if model exists
        models = ollama.list()
        model_names = []
        for m in models.get("models", []):
            name = m.get("name", "") if isinstance(m, dict) else getattr(m, "name", "")
            model_names.append(name)

        # Check with and without :latest suffix
        found = any(
            BENCHMARK_MODEL in name or BENCHMARK_MODEL.split(":")[0] in name
            for name in model_names
        )

        if not found:
            print(f"  Pulling {BENCHMARK_MODEL} (first run — downloading model)...")
            _pull_with_progress(BENCHMARK_MODEL)
            print(f"\n  Model {BENCHMARK_MODEL} ready.")
        else:
            print(f"  Model {BENCHMARK_MODEL} already available.")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False


def _pull_with_progress(model: str):
    """Pull a model with a live progress bar."""
    last_status = ""
    for progress in ollama.pull(model, stream=True):
        status = getattr(progress, "status", "") or ""
        completed = getattr(progress, "completed", None)
        total = getattr(progress, "total", None)

        if completed is not None and total is not None and total > 0:
            pct = int(completed / total * 100)
            completed_mb = completed / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            bar_len = 30
            filled = int(bar_len * completed / total)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(
                f"\r  {status}: {bar} {pct:3d}% ({completed_mb:.1f}/{total_mb:.1f} MB)",
                end="", flush=True,
            )
        elif status != last_status:
            print(f"\n  {status}...", end="", flush=True)

        last_status = status


def run_single_prompt(prompt_info: dict, warmup: bool = False) -> dict | None:
    """Run a single prompt and return structured metrics from the Ollama API.
    
    The Ollama API returns timing data in nanoseconds:
        - total_duration: total wall clock time
        - load_duration: time to load the model
        - prompt_eval_count: number of tokens in the prompt
        - prompt_eval_duration: time to process the prompt
        - eval_count: number of generated tokens
        - eval_duration: time to generate tokens
    """
    try:
        response = ollama.generate(
            model=BENCHMARK_MODEL,
            prompt=prompt_info["prompt"],
            options={
                "temperature": 0.7,
                "num_predict": 256,  # Cap output length for consistency
            },
        )

        # Convert nanoseconds to milliseconds/seconds
        total_duration_ms = response.get("total_duration", 0) / 1e6
        load_duration_ms = response.get("load_duration", 0) / 1e6
        prompt_eval_duration_ms = response.get("prompt_eval_duration", 0) / 1e6
        eval_duration_ms = response.get("eval_duration", 0) / 1e6

        prompt_eval_count = response.get("prompt_eval_count", 0)
        eval_count = response.get("eval_count", 0)

        # Calculate tokens/s
        prompt_eval_tps = (
            (prompt_eval_count / (prompt_eval_duration_ms / 1000.0))
            if prompt_eval_duration_ms > 0 else 0
        )
        eval_tps = (
            (eval_count / (eval_duration_ms / 1000.0))
            if eval_duration_ms > 0 else 0
        )

        # Time to first token = load + prompt eval
        ttft_ms = load_duration_ms + prompt_eval_duration_ms

        result = {
            "prompt_id": prompt_info["id"],
            "category": prompt_info["category"],
            "total_duration_ms": round(total_duration_ms, 2),
            "load_duration_ms": round(load_duration_ms, 2),
            "prompt_eval_count": prompt_eval_count,
            "prompt_eval_duration_ms": round(prompt_eval_duration_ms, 2),
            "prompt_eval_tps": round(prompt_eval_tps, 2),
            "eval_count": eval_count,
            "eval_duration_ms": round(eval_duration_ms, 2),
            "eval_tps": round(eval_tps, 2),
            "ttft_ms": round(ttft_ms, 2),
        }

        if warmup:
            result["warmup"] = True

        return result

    except Exception as e:
        return {
            "prompt_id": prompt_info["id"],
            "category": prompt_info["category"],
            "error": str(e),
        }


def compute_score(results: list[dict], power_stats: dict) -> dict:
    """Compute benchmark scores from results.
    
    Performance Score = (avg_prompt_eval_tps * 0.3) + (avg_eval_tps * 0.7)
    Efficiency Score  = performance_score / avg_watts (when power data available)
    """
    valid = [r for r in results if "error" not in r and not r.get("warmup")]

    if not valid:
        return {"performance_score": 0, "efficiency_score": None}

    avg_prompt_tps = sum(r["prompt_eval_tps"] for r in valid) / len(valid)
    avg_eval_tps = sum(r["eval_tps"] for r in valid) / len(valid)
    avg_ttft = sum(r["ttft_ms"] for r in valid) / len(valid)
    total_tokens = sum(r["eval_count"] for r in valid)
    total_prompt_tokens = sum(r["prompt_eval_count"] for r in valid)

    performance_score = round((avg_prompt_tps * 0.3) + (avg_eval_tps * 0.7), 2)

    efficiency_score = None
    if power_stats.get("available") and power_stats.get("avg_watts"):
        efficiency_score = round(performance_score / power_stats["avg_watts"], 4)

    return {
        "performance_score": performance_score,
        "efficiency_score": efficiency_score,
        "avg_prompt_eval_tps": round(avg_prompt_tps, 2),
        "avg_eval_tps": round(avg_eval_tps, 2),
        "avg_ttft_ms": round(avg_ttft, 2),
        "total_tokens_generated": total_tokens,
        "total_prompt_tokens": total_prompt_tokens,
        "prompts_completed": len(valid),
    }


def run_benchmark(console=None) -> dict:
    """Run the full benchmark suite. Returns structured results dict."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    power = PowerMonitor()

    # Step 1: Ensure model is available
    if console:
        console.print(f"\n[bold cyan]Preparing benchmark model:[/] {BENCHMARK_MODEL}")
    else:
        print(f"\nPreparing benchmark model: {BENCHMARK_MODEL}")

    if not ensure_model_available():
        return {"error": "Failed to pull benchmark model. Is Ollama running?"}

    # Step 2: Warmup pass (load model into memory, discard results)
    if console:
        console.print("[bold cyan]Warming up...[/]")
    else:
        print("Warming up...")

    warmup_prompt = {
        "id": "warmup",
        "category": "Warmup",
        "prompt": "Hello, how are you?",
    }
    run_single_prompt(warmup_prompt, warmup=True)

    # Step 3: Run benchmark with power monitoring
    if console:
        console.print("[bold cyan]Running benchmark...[/]")
        if power.is_available:
            console.print(f"  Power monitoring: [green]{power.method_name}[/]")
        else:
            console.print("  Power monitoring: [yellow]not available[/]")
    else:
        print("Running benchmark...")
        print(f"  Power monitoring: {power.method_name if power.is_available else 'not available'}")

    power.start()
    benchmark_start = time.time()

    results = []
    for i, prompt_info in enumerate(BENCHMARK_PROMPTS, 1):
        label = f"  [{i}/{len(BENCHMARK_PROMPTS)}] {prompt_info['category']}"
        if console:
            console.print(f"{label}...", end=" ")
        else:
            print(f"{label}...", end=" ", flush=True)

        result = run_single_prompt(prompt_info)
        results.append(result)

        if result and "error" not in result:
            msg = f"{result['eval_tps']} tok/s"
            if console:
                console.print(f"[green]{msg}[/]")
            else:
                print(msg)
        else:
            err = result.get("error", "unknown error") if result else "no result"
            if console:
                console.print(f"[red]ERROR: {err}[/]")
            else:
                print(f"ERROR: {err}")

    benchmark_duration = round(time.time() - benchmark_start, 2)
    power_stats = power.stop()

    # Step 4: Compute scores
    scores = compute_score(results, power_stats)

    return {
        "model": BENCHMARK_MODEL,
        "benchmark_duration_s": benchmark_duration,
        "results": results,
        "scores": scores,
        "power": power_stats,
    }
