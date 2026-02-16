"""Cross-platform system detection: CPU, GPU, RAM, OS for all vendors."""

import platform
import subprocess
import os
import uuid
import psutil


def get_os_info() -> dict:
    """Detect OS name and version."""
    system = platform.system()
    info = {
        "platform": system,
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
    }

    try:
        if system == "Darwin":
            info["os_name"] = "macOS"
            r = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True, timeout=10,
            )
            info["os_version"] = r.stdout.strip()
        elif system == "Linux":
            info["os_name"] = "Linux"
            try:
                r = subprocess.run(
                    ["lsb_release", "-d", "-s"],
                    capture_output=True, text=True, timeout=10,
                )
                info["os_version"] = r.stdout.strip()
            except FileNotFoundError:
                # Fallback: parse /etc/os-release
                if os.path.exists("/etc/os-release"):
                    with open("/etc/os-release") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                info["os_version"] = line.split("=", 1)[1].strip().strip('"')
                                break
        elif system == "Windows":
            info["os_name"] = "Windows"
            r = subprocess.run(
                ["powershell.exe", "(Get-CimInstance Win32_OperatingSystem).Caption"],
                capture_output=True, text=True, timeout=15,
            )
            info["os_version"] = r.stdout.strip()
    except Exception:
        pass

    info.setdefault("os_version", platform.version())
    return info


def get_cpu_info() -> dict:
    """Detect CPU name, cores, threads."""
    system = platform.system()
    info = {
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "cpu_name": "unknown",
    }

    try:
        if system == "Darwin":
            r = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=10,
            )
            name = r.stdout.strip()
            if not name:
                # Apple Silicon doesn't have brand_string, use chip name
                r = subprocess.run(
                    ["sysctl", "-n", "hw.chip"],
                    capture_output=True, text=True, timeout=10,
                )
                name = r.stdout.strip()
            if not name:
                r = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True, text=True, timeout=15,
                )
                for line in r.stdout.split("\n"):
                    if "Chip" in line:
                        name = line.split(":", 1)[1].strip()
                        break
            info["cpu_name"] = name or "unknown"

        elif system == "Linux":
            try:
                r = subprocess.run(
                    ["lscpu"], capture_output=True, text=True, timeout=10,
                )
                for line in r.stdout.split("\n"):
                    if "Model name" in line:
                        info["cpu_name"] = line.split(":", 1)[1].strip()
                        break
            except FileNotFoundError:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line.lower():
                            info["cpu_name"] = line.split(":", 1)[1].strip()
                            break

        elif system == "Windows":
            r = subprocess.run(
                ["powershell.exe", "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True, text=True, timeout=15,
            )
            info["cpu_name"] = r.stdout.strip() or "unknown"
    except Exception:
        pass

    return info


def get_ram_info() -> dict:
    """Detect total and available RAM in GB."""
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024 ** 3), 2),
        "available_gb": round(mem.available / (1024 ** 3), 2),
    }


def _detect_gpu_nvidia() -> list[dict]:
    """Detect NVIDIA GPUs via nvidia-smi."""
    gpus = []
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3:
                    try:
                        vram = int(float(parts[1]))
                        mem_type = "dedicated"
                    except (ValueError, TypeError):
                        # Unified memory (e.g. Jetson) — use system RAM
                        ram = get_ram_info()
                        vram = int(ram["total_gb"] * 1024)
                        mem_type = "unified"
                    driver = parts[2] if parts[2] not in ("[N/A]", "N/A", "") else None
                    gpus.append({
                        "vendor": "NVIDIA",
                        "name": parts[0],
                        "vram_mb": vram,
                        "memory_type": mem_type,
                        "driver": driver,
                    })
    except FileNotFoundError:
        pass
    return gpus


def _detect_gpu_amd_linux() -> list[dict]:
    """Detect AMD GPUs via rocm-smi on Linux."""
    gpus = []
    if platform.system() != "Linux":
        return gpus
    try:
        r = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            for line in r.stdout.split("\n"):
                if "Card series" in line or "card series" in line.lower():
                    name = line.split(":")[-1].strip()
                    if name:
                        gpus.append({"vendor": "AMD", "name": name, "vram_mb": None, "memory_type": "dedicated", "driver": None})
        # Try to get VRAM
        if gpus:
            r2 = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True, text=True, timeout=10,
            )
            if r2.returncode == 0:
                for line in r2.stdout.split("\n"):
                    if "Total" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p == "Total":
                                try:
                                    vram_bytes = int(parts[i + 2])
                                    if gpus:
                                        gpus[0]["vram_mb"] = vram_bytes // (1024 * 1024)
                                except (IndexError, ValueError):
                                    pass
    except FileNotFoundError:
        pass

    # Fallback: rocminfo
    if not gpus:
        try:
            r = subprocess.run(
                ["rocminfo"], capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                for line in r.stdout.split("\n"):
                    if "Marketing Name:" in line:
                        name = line.split("Marketing Name:")[1].strip()
                        if name and name != "N/A" and "Intel" not in name:
                            gpus.append({"vendor": "AMD", "name": name, "vram_mb": None, "memory_type": "dedicated", "driver": None})
        except FileNotFoundError:
            pass

    return gpus


def _detect_gpu_apple() -> list[dict]:
    """Detect Apple Silicon GPU."""
    if platform.system() != "Darwin":
        return []
    gpus = []
    try:
        r = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.split("\n"):
            if "Chip" in line:
                chip = line.split(":", 1)[1].strip()
                if chip.startswith("Apple"):
                    # Get memory — Apple Silicon uses unified memory
                    ram = get_ram_info()
                    gpus.append({
                        "vendor": "Apple",
                        "name": chip,
                        "vram_mb": int(ram["total_gb"] * 1024),  # unified memory
                        "memory_type": "unified",
                        "driver": "Metal",
                    })
                break
    except Exception:
        pass
    return gpus


def _detect_gpu_intel() -> list[dict]:
    """Detect Intel GPUs (Arc / integrated)."""
    gpus = []
    system = platform.system()

    if system == "Windows":
        try:
            r = subprocess.run(
                [
                    "powershell.exe",
                    "Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like '*Intel*' } | Select-Object -ExpandProperty Name",
                ],
                capture_output=True, text=True, timeout=15,
            )
            for line in r.stdout.strip().split("\n"):
                name = line.strip()
                if name:
                    gpus.append({"vendor": "Intel", "name": name, "vram_mb": None, "memory_type": "shared", "driver": None})
        except Exception:
            pass

    elif system == "Linux":
        try:
            r = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.split("\n"):
                if "VGA" in line and "Intel" in line:
                    name = line.split(":")[-1].strip()
                    gpus.append({"vendor": "Intel", "name": name, "vram_mb": None, "memory_type": "shared", "driver": None})
        except FileNotFoundError:
            pass

    return gpus


def _detect_gpu_windows_fallback() -> list[dict]:
    """Fallback: detect any GPU on Windows via WMI (catches AMD, etc.)."""
    gpus = []
    try:
        r = subprocess.run(
            [
                "powershell.exe",
                "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ForEach-Object { $_.Name + '|' + $_.AdapterRAM + '|' + $_.DriverVersion }",
            ],
            capture_output=True, text=True, timeout=15,
        )
        for line in r.stdout.strip().split("\n"):
            parts = line.strip().split("|")
            if len(parts) >= 1 and parts[0]:
                name = parts[0].strip()
                # Skip Microsoft Basic Display Adapter
                if "Microsoft" in name:
                    continue
                vram = None
                driver = None
                if len(parts) >= 2 and parts[1].strip():
                    try:
                        vram = int(parts[1].strip()) // (1024 * 1024)
                    except ValueError:
                        pass
                if len(parts) >= 3:
                    driver = parts[2].strip() or None

                vendor = "Unknown"
                name_lower = name.lower()
                if "nvidia" in name_lower or "geforce" in name_lower or "rtx" in name_lower or "gtx" in name_lower:
                    vendor = "NVIDIA"
                elif "amd" in name_lower or "radeon" in name_lower:
                    vendor = "AMD"
                elif "intel" in name_lower:
                    vendor = "Intel"

                gpus.append({"vendor": vendor, "name": name, "vram_mb": vram, "memory_type": "dedicated", "driver": driver})
    except Exception:
        pass
    return gpus


def get_gpu_info() -> list[dict]:
    """Detect all GPUs across all vendors. Returns a list of GPU dicts."""
    gpus = []

    # NVIDIA (all platforms)
    gpus.extend(_detect_gpu_nvidia())

    # Apple Silicon
    gpus.extend(_detect_gpu_apple())

    # AMD on Linux
    gpus.extend(_detect_gpu_amd_linux())

    # Intel
    gpus.extend(_detect_gpu_intel())

    # Windows fallback for anything we missed (AMD on Windows, etc.)
    if platform.system() == "Windows":
        existing_names = {g["name"].lower() for g in gpus}
        for g in _detect_gpu_windows_fallback():
            if g["name"].lower() not in existing_names:
                gpus.append(g)

    if not gpus:
        gpus.append({"vendor": "None", "name": "No dedicated GPU detected", "vram_mb": None, "memory_type": None, "driver": None})

    return gpus


def generate_machine_uuid(sys_info: dict) -> str:
    """Generate a deterministic UUID5 from system fingerprint."""
    cpu = sys_info.get("cpu", {}).get("cpu_name", "unknown")
    gpu_names = ", ".join(g["name"] for g in sys_info.get("gpu", []))
    ram = sys_info.get("ram", {}).get("total_gb", 0)
    os_name = sys_info.get("os", {}).get("os_name", "unknown")

    fingerprint = f"{os_name}|{cpu}|{gpu_names}|{ram}"
    return str(uuid.uuid5(uuid.NAMESPACE_X500, fingerprint))


def collect_system_info() -> dict:
    """Collect all system information into a single dict."""
    info = {
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "ram": get_ram_info(),
        "gpu": get_gpu_info(),
    }
    info["machine_uuid"] = generate_machine_uuid(info)
    return info
