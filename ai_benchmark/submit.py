"""Result submission to remote endpoint."""

import json
import time
import requests


# Placeholder — user will provide the real endpoint later
DEFAULT_ENDPOINT = "https://benchverz.com/api/llm-bench"


def build_payload(system_info: dict, benchmark_data: dict, ollama_version: str) -> dict:
    """Build the full payload to submit to the remote endpoint.
    
    This is the complete JSON structure that will be POSTed.
    """
    return {
        "version": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),

        # Machine identity
        "machine_uuid": system_info.get("machine_uuid", "unknown"),

        # System info
        "system": {
            "os": system_info.get("os", {}),
            "cpu": system_info.get("cpu", {}),
            "ram": system_info.get("ram", {}),
            "gpu": system_info.get("gpu", []),
        },

        # Ollama
        "ollama_version": ollama_version,

        # Benchmark config
        "benchmark": {
            "model": benchmark_data.get("model", ""),
            "duration_s": benchmark_data.get("benchmark_duration_s", 0),
        },

        # Scores (the key numbers for leaderboard)
        "scores": benchmark_data.get("scores", {}),

        # Power monitoring
        "power": benchmark_data.get("power", {}),

        # Per-prompt detailed results
        "results": benchmark_data.get("results", []),
    }


def submit_results(
    payload: dict,
    endpoint: str | None = None,
    console=None,
) -> bool:
    """POST the payload to the remote endpoint.
    
    Returns True on success, False on failure.
    """
    url = endpoint or DEFAULT_ENDPOINT

    try:
        if console:
            console.print(f"[cyan]Submitting results to {url}...[/]")
        else:
            print(f"Submitting results to {url}...")

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code in (200, 201):
            if console:
                console.print("[green]Results submitted successfully![/]")
            else:
                print("Results submitted successfully!")
            return True
        else:
            if console:
                console.print(f"[red]Submission failed: HTTP {response.status_code}[/]")
                console.print(f"[dim]{response.text[:200]}[/]")
            else:
                print(f"Submission failed: HTTP {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        msg = "Could not connect to endpoint."
        if console:
            console.print(f"[red]{msg}[/]")
        else:
            print(msg)
        return False
    except Exception as e:
        if console:
            console.print(f"[red]Submission error: {e}[/]")
        else:
            print(f"Submission error: {e}")
        return False


def save_results_local(payload: dict, filepath: str = "benchmark_result.json") -> str:
    """Save the full payload to a local JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return filepath
