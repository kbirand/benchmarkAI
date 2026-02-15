"""Cleanup / uninstall: remove benchmark model, Ollama data, and Ollama itself."""

import os
import sys
import shutil
import platform
import subprocess


# ---------------------------------------------------------------------------
# Model removal (cross-platform, uses Ollama API)
# ---------------------------------------------------------------------------

def remove_benchmark_model(model: str = "llama3.1:8b") -> bool:
    """Delete the benchmark model from Ollama."""
    try:
        import ollama
        ollama.delete(model)
        return True
    except Exception as e:
        print(f"  Could not remove model via API: {e}")
        return False


# ---------------------------------------------------------------------------
# Ollama data directories per platform
# ---------------------------------------------------------------------------

def get_ollama_data_paths() -> list[str]:
    """Return paths where Ollama stores models and data."""
    system = platform.system()
    paths = []

    if system == "Windows":
        # Default: %USERPROFILE%\.ollama
        home = os.environ.get("USERPROFILE", "")
        if home:
            paths.append(os.path.join(home, ".ollama"))
        # Also check OLLAMA_MODELS env var
        custom = os.environ.get("OLLAMA_MODELS")
        if custom:
            paths.append(custom)

    elif system == "Darwin":
        home = os.path.expanduser("~")
        paths.append(os.path.join(home, ".ollama"))
        custom = os.environ.get("OLLAMA_MODELS")
        if custom:
            paths.append(custom)

    elif system == "Linux":
        # Ollama service runs as 'ollama' user, data in /usr/share/ollama
        paths.append("/usr/share/ollama/.ollama")
        # User installs
        home = os.path.expanduser("~")
        paths.append(os.path.join(home, ".ollama"))
        custom = os.environ.get("OLLAMA_MODELS")
        if custom:
            paths.append(custom)

    return [p for p in paths if os.path.exists(p)]


def get_ollama_data_size() -> float:
    """Get total size of Ollama data directories in MB."""
    total = 0
    for path in get_ollama_data_paths():
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    return total / (1024 * 1024)


def remove_ollama_data() -> bool:
    """Remove all Ollama data directories (models, blobs, manifests)."""
    paths = get_ollama_data_paths()
    success = True
    for path in paths:
        try:
            shutil.rmtree(path)
            print(f"  Removed: {path}")
        except PermissionError:
            # Try with elevated permissions on Linux
            if platform.system() == "Linux":
                try:
                    subprocess.run(["sudo", "rm", "-rf", path], check=True, timeout=30)
                    print(f"  Removed (sudo): {path}")
                except Exception as e:
                    print(f"  Failed to remove {path}: {e}")
                    success = False
            else:
                print(f"  Permission denied: {path}")
                success = False
        except Exception as e:
            print(f"  Failed to remove {path}: {e}")
            success = False
    return success


# ---------------------------------------------------------------------------
# Ollama uninstall per platform
# ---------------------------------------------------------------------------

def stop_ollama_server():
    """Stop the Ollama server if running."""
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/version", timeout=2)
        # Server is running — try to stop it
        system = platform.system()
        if system == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama.exe"],
                capture_output=True, timeout=10,
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama_llama_server.exe"],
                capture_output=True, timeout=10,
            )
            # Also kill the Ollama app (tray icon)
            subprocess.run(
                ["taskkill", "/F", "/IM", "Ollama.exe"],
                capture_output=True, timeout=10,
            )
        else:
            subprocess.run(["pkill", "-f", "ollama"], capture_output=True, timeout=10)
            if system == "Linux":
                subprocess.run(
                    ["sudo", "systemctl", "stop", "ollama"],
                    capture_output=True, timeout=10,
                )
        print("  Ollama server stopped.")
    except Exception:
        pass  # Server not running or can't stop — that's fine


def uninstall_ollama_windows() -> bool:
    """Uninstall Ollama on Windows using the Inno Setup uninstaller."""
    # Find uninstaller in registry
    uninstall_cmd = None
    try:
        r = subprocess.run(
            [
                "powershell.exe",
                "Get-ChildItem 'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall' -ErrorAction SilentlyContinue | "
                "ForEach-Object { $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue; "
                "if ($p.DisplayName -like '*Ollama*') { $p.UninstallString } }"
            ],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            uninstall_cmd = r.stdout.strip().strip('"')
    except Exception:
        pass

    # Fallback: check known location
    if not uninstall_cmd:
        default = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs", "Ollama", "unins000.exe",
        )
        if os.path.isfile(default):
            uninstall_cmd = default

    if not uninstall_cmd:
        print("  Could not find Ollama uninstaller.")
        # Manual cleanup
        install_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama"
        )
        if os.path.isdir(install_dir):
            try:
                shutil.rmtree(install_dir)
                print(f"  Manually removed: {install_dir}")
                return True
            except Exception as e:
                print(f"  Failed to remove {install_dir}: {e}")
                return False
        return False

    try:
        print(f"  Running uninstaller...")
        subprocess.run(
            [uninstall_cmd, "/VERYSILENT", "/NORESTART"],
            timeout=120,
        )
        print("  Ollama uninstalled.")
        return True
    except Exception as e:
        print(f"  Uninstall failed: {e}")
        return False


def uninstall_ollama_linux() -> bool:
    """Uninstall Ollama on Linux."""
    success = True

    # Stop and disable service
    try:
        subprocess.run(
            ["sudo", "systemctl", "stop", "ollama"],
            capture_output=True, timeout=15,
        )
        subprocess.run(
            ["sudo", "systemctl", "disable", "ollama"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass

    # Remove service file
    service_file = "/etc/systemd/system/ollama.service"
    if os.path.exists(service_file):
        try:
            subprocess.run(["sudo", "rm", "-f", service_file], check=True, timeout=10)
            print(f"  Removed: {service_file}")
        except Exception as e:
            print(f"  Failed to remove service file: {e}")
            success = False

    # Remove binary
    for bin_path in ["/usr/local/bin/ollama", "/usr/bin/ollama"]:
        if os.path.exists(bin_path):
            try:
                subprocess.run(["sudo", "rm", "-f", bin_path], check=True, timeout=10)
                print(f"  Removed: {bin_path}")
            except Exception as e:
                print(f"  Failed to remove {bin_path}: {e}")
                success = False

    # Remove ollama user and group
    try:
        subprocess.run(
            ["sudo", "userdel", "-r", "ollama"],
            capture_output=True, timeout=10,
        )
        subprocess.run(
            ["sudo", "groupdel", "ollama"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass

    if success:
        print("  Ollama uninstalled.")
    return success


def uninstall_ollama_macos() -> bool:
    """Uninstall Ollama on macOS."""
    success = True

    # Remove Ollama.app
    app_path = "/Applications/Ollama.app"
    if os.path.exists(app_path):
        try:
            shutil.rmtree(app_path)
            print(f"  Removed: {app_path}")
        except PermissionError:
            try:
                subprocess.run(["sudo", "rm", "-rf", app_path], check=True, timeout=30)
                print(f"  Removed (sudo): {app_path}")
            except Exception as e:
                print(f"  Failed to remove {app_path}: {e}")
                success = False

    # Remove CLI symlink
    for symlink in ["/usr/local/bin/ollama", os.path.expanduser("~/.local/bin/ollama")]:
        if os.path.exists(symlink):
            try:
                os.remove(symlink)
                print(f"  Removed: {symlink}")
            except Exception:
                try:
                    subprocess.run(["sudo", "rm", "-f", symlink], check=True, timeout=10)
                    print(f"  Removed (sudo): {symlink}")
                except Exception as e:
                    print(f"  Failed to remove {symlink}: {e}")

    if success:
        print("  Ollama uninstalled.")
    return success


def uninstall_ollama() -> bool:
    """Uninstall Ollama for the current platform."""
    system = platform.system()
    if system == "Windows":
        return uninstall_ollama_windows()
    elif system == "Linux":
        return uninstall_ollama_linux()
    elif system == "Darwin":
        return uninstall_ollama_macos()
    else:
        print(f"  Unsupported platform: {system}")
        return False


# ---------------------------------------------------------------------------
# Venv cleanup
# ---------------------------------------------------------------------------

def remove_venv(script_dir: str) -> bool:
    """Remove the .venv directory."""
    venv_dir = os.path.join(script_dir, ".venv")
    if os.path.isdir(venv_dir):
        try:
            shutil.rmtree(venv_dir)
            print(f"  Removed: {venv_dir}")
            return True
        except Exception as e:
            print(f"  Failed to remove {venv_dir}: {e}")
            return False
    return True
