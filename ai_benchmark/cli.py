"""CLI entry point for AI Benchmark."""

import json
import subprocess
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .system_info import collect_system_info
from .benchmark import run_benchmark, BENCHMARK_MODEL
from .submit import build_payload, submit_results, save_results_local
from .cleanup import (
    remove_benchmark_model,
    get_ollama_data_paths,
    get_ollama_data_size,
    remove_ollama_data,
    stop_ollama_server,
    uninstall_ollama,
    remove_venv,
)

app = typer.Typer(
    name="ai-benchmark",
    help="Cross-platform AI system benchmark — compare hardware, not models.",
    add_completion=False,
)
console = Console()


def _get_ollama_version() -> str:
    """Get the Ollama version from the running server API."""
    # Prefer the API — always works if server is running, regardless of PATH
    try:
        import requests as _req
        r = _req.get("http://localhost:11434/api/version", timeout=5)
        if r.status_code == 200:
            return r.json().get("version", "unknown")
    except Exception:
        pass

    # Fallback: try CLI
    try:
        r = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            output = r.stdout.strip()
            if "version" in output.lower():
                parts = output.split()
                for i, p in enumerate(parts):
                    if p.lower() == "version":
                        for j in range(i + 1, len(parts)):
                            if parts[j].lower() != "is":
                                return parts[j]
            return output
    except Exception:
        pass
    return "unknown"


def _check_ollama_running() -> bool:
    """Check if Ollama server is reachable."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/version", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _print_system_info(sys_info: dict):
    """Pretty-print system information."""
    table = Table(title="System Information", box=box.ROUNDED, show_header=False)
    table.add_column("Property", style="cyan", width=20)
    table.add_column("Value", style="white")

    os_info = sys_info.get("os", {})
    table.add_row("OS", f"{os_info.get('os_name', '?')} {os_info.get('os_version', '?')}")
    table.add_row("Architecture", os_info.get("architecture", "?"))

    cpu = sys_info.get("cpu", {})
    table.add_row("CPU", cpu.get("cpu_name", "?"))
    table.add_row("Cores", f"{cpu.get('physical_cores', '?')} physical / {cpu.get('logical_cores', '?')} logical")

    ram = sys_info.get("ram", {})
    table.add_row("RAM", f"{ram.get('total_gb', '?')} GB total / {ram.get('available_gb', '?')} GB available")

    gpus = sys_info.get("gpu", [])
    for i, gpu in enumerate(gpus):
        mem_type = gpu.get("memory_type", "")
        vram_label = f" ({gpu['vram_mb']} MB {mem_type})" if gpu.get("vram_mb") else (f" ({mem_type})" if mem_type else "")
        driver = f" [driver: {gpu['driver']}]" if gpu.get("driver") else ""
        table.add_row(
            f"GPU {i}" if len(gpus) > 1 else "GPU",
            f"{gpu['vendor']} {gpu['name']}{vram_label}{driver}",
        )

    table.add_row("Machine UUID", sys_info.get("machine_uuid", "?"))

    console.print(table)


def _print_results(benchmark_data: dict):
    """Pretty-print benchmark results."""
    scores = benchmark_data.get("scores", {})
    power = benchmark_data.get("power", {})

    # Scores panel
    perf = scores.get("performance_score", 0)
    eff = scores.get("efficiency_score")

    score_text = f"[bold green]{perf}[/bold green]"
    if eff is not None:
        score_text += f"  |  Efficiency: [bold blue]{eff}[/bold blue] (tok/s/W)"

    console.print(Panel(
        f"Performance Score: {score_text}\n\n"
        f"  Avg Generation:  [white]{scores.get('avg_eval_tps', 0)}[/] tok/s\n"
        f"  Avg Prompt Eval: [white]{scores.get('avg_prompt_eval_tps', 0)}[/] tok/s\n"
        f"  Avg TTFT:        [white]{scores.get('avg_ttft_ms', 0)}[/] ms\n"
        f"  Total Tokens:    [white]{scores.get('total_tokens_generated', 0)}[/]\n"
        f"  Duration:        [white]{benchmark_data.get('benchmark_duration_s', 0)}[/] s",
        title="[bold]Benchmark Results[/]",
        box=box.DOUBLE,
    ))

    # Power panel
    if power.get("available"):
        console.print(Panel(
            f"  Avg Power: [yellow]{power['avg_watts']}[/] W\n"
            f"  Max Power: [yellow]{power['max_watts']}[/] W\n"
            f"  Min Power: [yellow]{power['min_watts']}[/] W\n"
            f"  Method:    {power['method']}\n"
            f"  Samples:   {power['samples']}",
            title="[bold]Power Monitoring[/]",
            box=box.ROUNDED,
        ))

    # Per-prompt table
    results = benchmark_data.get("results", [])
    valid = [r for r in results if "error" not in r and not r.get("warmup")]
    if valid:
        table = Table(title="Per-Prompt Results", box=box.SIMPLE_HEAVY)
        table.add_column("Category", style="cyan")
        table.add_column("Gen tok/s", justify="right", style="green")
        table.add_column("Prompt tok/s", justify="right", style="blue")
        table.add_column("TTFT (ms)", justify="right", style="yellow")
        table.add_column("Tokens", justify="right")

        for r in valid:
            table.add_row(
                r["category"],
                str(r["eval_tps"]),
                str(r["prompt_eval_tps"]),
                str(r["ttft_ms"]),
                str(r["eval_count"]),
            )
        console.print(table)


@app.command()
def run(
    endpoint: str = typer.Option(None, "--endpoint", "-e", help="Remote endpoint URL to submit results to."),
    no_submit: bool = typer.Option(False, "--no-submit", help="Skip submitting results to remote endpoint."),
    no_save: bool = typer.Option(False, "--no-save", help="Skip saving results to local JSON file."),
    output: str = typer.Option("benchmark_result.json", "--output", "-o", help="Output JSON file path."),
):
    """Run the AI system benchmark."""
    console.print(Panel(
        "[bold]AI System Benchmark[/]\n"
        f"Model: {BENCHMARK_MODEL}\n"
        "Comparing hardware performance across devices",
        box=box.DOUBLE_EDGE,
    ))

    # Check Ollama
    console.print("\n[bold cyan]Checking Ollama...[/]")
    if not _check_ollama_running():
        console.print("[bold red]Error: Ollama is not running![/]")
        console.print("Please start Ollama first: [white]ollama serve[/]")
        raise typer.Exit(1)

    ollama_version = _get_ollama_version()
    console.print(f"  Ollama version: [green]{ollama_version}[/]")

    # Collect system info
    console.print("\n[bold cyan]Detecting system hardware...[/]")
    sys_info = collect_system_info()
    _print_system_info(sys_info)

    # Run benchmark
    benchmark_data = run_benchmark(console=console)

    if "error" in benchmark_data:
        console.print(f"\n[bold red]Benchmark failed: {benchmark_data['error']}[/]")
        raise typer.Exit(1)

    # Print results
    console.print()
    _print_results(benchmark_data)

    # Build payload
    payload = build_payload(sys_info, benchmark_data, ollama_version)

    # Save locally
    if not no_save:
        filepath = save_results_local(payload, output)
        console.print(f"\n[dim]Results saved to: {filepath}[/]")

    # Submit
    if not no_submit:
        submit_results(payload, endpoint=endpoint, console=console)

    console.print("\n[bold green]Benchmark complete![/]")


@app.command()
def sysinfo():
    """Display detected system information."""
    console.print("\n[bold cyan]Detecting system hardware...[/]")
    sys_info = collect_system_info()
    _print_system_info(sys_info)


@app.command()
def payload_preview(
    output: str = typer.Option("payload_preview.json", "--output", "-o", help="Output file for payload preview."),
):
    """Show a preview of the JSON payload that will be submitted."""
    console.print("[bold cyan]Generating payload preview...[/]")

    sys_info = collect_system_info()
    ollama_version = _get_ollama_version()

    # Fake benchmark data for preview
    sample_benchmark = {
        "model": BENCHMARK_MODEL,
        "benchmark_duration_s": 42.5,
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
                "ttft_ms": 600.0,
            },
        ],
        "scores": {
            "performance_score": 44.02,
            "efficiency_score": 0.1834,
            "avg_prompt_eval_tps": 71.11,
            "avg_eval_tps": 32.41,
            "avg_ttft_ms": 600.0,
            "total_tokens_generated": 256,
            "total_prompt_tokens": 32,
            "prompts_completed": 1,
        },
        "power": {
            "available": True,
            "method": "nvidia-smi",
            "avg_watts": 240.0,
            "max_watts": 280.0,
            "min_watts": 200.0,
            "samples": 15,
        },
    }

    payload = build_payload(sys_info, sample_benchmark, ollama_version)

    # Save and print
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    console.print_json(json.dumps(payload, indent=2))
    console.print(f"\n[dim]Payload preview saved to: {output}[/]")


@app.command()
def cleanup(
    model_only: bool = typer.Option(False, "--model-only", help="Only remove the benchmark model, keep Ollama installed."),
    keep_ollama: bool = typer.Option(False, "--keep-ollama", help="Remove model and data but keep Ollama installed."),
    remove_env: bool = typer.Option(False, "--remove-venv", help="Also remove the Python virtual environment."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompts."),
):
    """Remove benchmark model, Ollama data, and optionally uninstall Ollama to free disk space."""
    import os

    console.print(Panel(
        "[bold]AI Benchmark — Cleanup[/]\n"
        "Free disk space by removing downloaded models and Ollama",
        box=box.DOUBLE_EDGE,
    ))

    # Show what will be removed
    data_size = get_ollama_data_size()
    data_paths = get_ollama_data_paths()

    console.print()
    table = Table(title="What will be removed", box=box.ROUNDED, show_header=False)
    table.add_column("Item", style="cyan", width=30)
    table.add_column("Details", style="white")

    table.add_row("Benchmark model", f"{BENCHMARK_MODEL}")

    if not model_only:
        if data_paths:
            table.add_row("Ollama data/models", f"{data_size:.1f} MB in {', '.join(data_paths)}")
        else:
            table.add_row("Ollama data/models", "[dim]No data found[/]")

        if not keep_ollama:
            table.add_row("Ollama application", "Full uninstall")

    if remove_env:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_dir = os.path.join(script_dir, ".venv")
        if os.path.isdir(venv_dir):
            table.add_row("Python venv", venv_dir)

    console.print(table)
    console.print()

    # Confirm
    if not yes:
        try:
            answer = input("Proceed with cleanup? (y/n): ").strip().lower()
            if answer not in ("y", "yes"):
                console.print("[yellow]Cancelled.[/]")
                raise typer.Exit(0)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/]")
            raise typer.Exit(0)

    console.print()

    # Step 1: Remove benchmark model
    console.print("[bold cyan]Removing benchmark model...[/]")
    if remove_benchmark_model(BENCHMARK_MODEL):
        console.print(f"  [green]Removed model: {BENCHMARK_MODEL}[/]")
    else:
        console.print(f"  [yellow]Model may already be removed or Ollama not running.[/]")

    if model_only:
        console.print("\n[bold green]Cleanup complete! (model only)[/]")
        raise typer.Exit(0)

    # Step 2: Stop Ollama server
    console.print("[bold cyan]Stopping Ollama server...[/]")
    stop_ollama_server()

    # Step 3: Remove Ollama data
    if data_paths:
        console.print("[bold cyan]Removing Ollama data...[/]")
        remove_ollama_data()

    # Step 4: Uninstall Ollama
    if not keep_ollama:
        console.print("[bold cyan]Uninstalling Ollama...[/]")
        uninstall_ollama()

    # Step 5: Remove venv
    if remove_env:
        console.print("[bold cyan]Removing Python virtual environment...[/]")
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        remove_venv(script_dir)

    console.print("\n[bold green]Cleanup complete![/]")
    freed = data_size
    if freed > 1024:
        console.print(f"[dim]Freed approximately {freed / 1024:.1f} GB of disk space.[/]")
    elif freed > 0:
        console.print(f"[dim]Freed approximately {freed:.0f} MB of disk space.[/]")


if __name__ == "__main__":
    app()
