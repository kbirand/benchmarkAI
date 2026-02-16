"""Best-effort power draw monitoring across GPU vendors."""

import platform
import subprocess
import threading
import time


class PowerMonitor:
    """Samples GPU power draw in a background thread during benchmark runs.
    
    Supported:
        - NVIDIA (all OS) via nvidia-smi
        - AMD Linux via rocm-smi
        - Apple Silicon via powermetrics (requires sudo, opt-in)
    
    Unsupported platforms gracefully return None.
    """

    def __init__(self):
        self._samples: list[float] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._method = self._detect_method()

    def _detect_method(self) -> str | None:
        """Detect which power monitoring method is available."""
        system = platform.system()

        # NVIDIA — works on Windows, Linux, macOS (rare)
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return "nvidia-smi"
        except FileNotFoundError:
            pass

        # AMD Linux via rocm-smi
        if system == "Linux":
            try:
                r = subprocess.run(
                    ["rocm-smi", "--showpower"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    return "rocm-smi"
            except FileNotFoundError:
                pass

        # Apple Silicon via powermetrics (needs sudo)
        if system == "Darwin":
            try:
                r = subprocess.run(
                    ["which", "powermetrics"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    return "powermetrics"
            except FileNotFoundError:
                pass

        return None

    def _sample_nvidia(self) -> float | None:
        """Read current power draw from nvidia-smi in watts."""
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                # Sum across all GPUs
                total = 0.0
                for line in r.stdout.strip().split("\n"):
                    val = line.strip()
                    if val:
                        total += float(val)
                return round(total, 2)
        except Exception:
            pass
        return None

    def _sample_rocm(self) -> float | None:
        """Read current power draw from rocm-smi in watts."""
        try:
            r = subprocess.run(
                ["rocm-smi", "--showpower"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                total = 0.0
                for line in r.stdout.split("\n"):
                    # Look for lines containing "Average Graphics Package Power" or "W"
                    lower = line.lower()
                    if "power" in lower and "w" in lower:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            try:
                                val = float(p)
                                # Heuristic: if next token is W or watts, this is the value
                                if i + 1 < len(parts) and parts[i + 1].lower().startswith("w"):
                                    total += val
                                    break
                                # Or if the value is reasonable wattage (1-1000)
                                elif 1 <= val <= 1000:
                                    total += val
                                    break
                            except ValueError:
                                continue
                if total > 0:
                    return round(total, 2)
        except Exception:
            pass
        return None

    def _sample_apple(self) -> float | None:
        """Read power from powermetrics (requires sudo). Returns None if not available."""
        try:
            r = subprocess.run(
                ["sudo", "-n", "powermetrics", "-n", "1", "-i", "100",
                 "--samplers", "gpu_power"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                for line in r.stdout.split("\n"):
                    if "GPU Power" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            val_str = parts[1].strip().split()[0]
                            return round(float(val_str) / 1000.0, 2)  # mW to W
        except Exception:
            pass
        return None

    def _sample(self) -> float | None:
        """Take a single power sample using the detected method."""
        if self._method == "nvidia-smi":
            return self._sample_nvidia()
        elif self._method == "rocm-smi":
            return self._sample_rocm()
        elif self._method == "powermetrics":
            return self._sample_apple()
        return None

    def _sampling_loop(self, interval: float = 0.5):
        """Background sampling loop."""
        while self._running:
            sample = self._sample()
            if sample is not None and sample > 0:
                self._samples.append(sample)
            time.sleep(interval)

    def start(self):
        """Start background power sampling."""
        if self._method is None:
            return  # No monitoring available
        self._samples = []
        self._running = True
        self._thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._thread.start()

    def stop(self) -> dict:
        """Stop sampling and return power statistics."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

        if not self._samples:
            return {
                "available": False,
                "method": self._method,
                "avg_watts": None,
                "max_watts": None,
                "min_watts": None,
                "samples": 0,
            }

        return {
            "available": True,
            "method": self._method,
            "avg_watts": round(sum(self._samples) / len(self._samples), 2),
            "max_watts": round(max(self._samples), 2),
            "min_watts": round(min(self._samples), 2),
            "samples": len(self._samples),
        }

    @property
    def is_available(self) -> bool:
        return self._method is not None

    @property
    def method_name(self) -> str:
        return self._method or "none"
