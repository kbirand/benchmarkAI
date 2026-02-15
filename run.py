#!/usr/bin/env python3
"""
Universal bootstrap script — works on Windows, macOS, and Linux.
Automatically installs Ollama if not present.
Run with: python run.py
"""

import subprocess
import sys
import os
import platform
import tempfile
import time
import venv
import urllib.request
import urllib.error


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(SCRIPT_DIR, ".venv")

# ---------------------------------------------------------------------------
# Ollama install URLs per platform
# ---------------------------------------------------------------------------
OLLAMA_URLS = {
    "windows_amd64": "https://ollama.com/download/OllamaSetup.exe",
    "linux_amd64": "https://ollama.com/install.sh",
    "linux_arm64": "https://ollama.com/install.sh",
    "darwin_arm64": "https://ollama.com/download/Ollama-darwin.zip",
    "darwin_amd64": "https://ollama.com/download/Ollama-darwin.zip",
}

# Common Ollama install locations per platform
OLLAMA_SEARCH_PATHS = {
    "win32": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Ollama", "ollama.exe"),
    ],
    "linux": [
        "/usr/local/bin/ollama",
        "/usr/bin/ollama",
        os.path.expanduser("~/.local/bin/ollama"),
        "/snap/bin/ollama",
    ],
    "darwin": [
        "/usr/local/bin/ollama",
        "/opt/homebrew/bin/ollama",
        os.path.expanduser("~/.local/bin/ollama"),
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_ollama():
    """Find the ollama executable. Returns path string or None."""
    # Try PATH first
    try:
        r = subprocess.run(["ollama", "--version"], capture_output=True, timeout=10)
        return "ollama"
    except FileNotFoundError:
        pass
    except Exception:
        return "ollama"

    # Search common install locations
    key = "win32" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
    for path in OLLAMA_SEARCH_PATHS.get(key, []):
        if path and os.path.isfile(path):
            return path

    return None


def check_ollama_running():
    """Check if the Ollama server is reachable."""
    try:
        r = urllib.request.urlopen("http://localhost:11434/api/version", timeout=5)
        return r.status == 200
    except Exception:
        return False


def download_file(url, dest, label="Downloading"):
    """Download a file with progress indication."""
    print(f"{label}: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-benchmark/1.0"})
        resp = urllib.request.urlopen(req, timeout=120)
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 256  # 256 KB

        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded / total * 100)
                    mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    print(f"\r  {mb:.1f} / {total_mb:.1f} MB ({pct}%)", end="", flush=True)
                else:
                    mb = downloaded / (1024 * 1024)
                    print(f"\r  {mb:.1f} MB downloaded", end="", flush=True)
        print()  # newline after progress
        return True
    except Exception as e:
        print(f"\n  Download failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Platform-specific Ollama installers
# ---------------------------------------------------------------------------

def install_ollama_windows():
    """Download and silently install Ollama on Windows."""
    url = OLLAMA_URLS["windows_amd64"]
    installer = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")

    if not download_file(url, installer, "Downloading Ollama for Windows"):
        return False

    print("Installing Ollama (this may take a minute)...")
    try:
        # /VERYSILENT runs the Inno Setup installer without any UI
        result = subprocess.run(
            [installer, "/VERYSILENT", "/NORESTART", "/MERGETASKS=!desktopicon"],
            timeout=300,
        )
        if result.returncode == 0:
            print("[OK] Ollama installed successfully.")
            return True
        else:
            print(f"[WARNING] Installer exited with code {result.returncode}, checking if it worked anyway...")
            # Sometimes returns non-zero but still installs
            time.sleep(3)
            if find_ollama():
                print("[OK] Ollama installed successfully.")
                return True
            return False
    except subprocess.TimeoutExpired:
        print("[ERROR] Installation timed out.")
        return False
    except Exception as e:
        print(f"[ERROR] Installation failed: {e}")
        return False
    finally:
        # Clean up installer
        try:
            os.remove(installer)
        except OSError:
            pass


def install_ollama_linux():
    """Install Ollama on Linux using the official install script."""
    print("Installing Ollama for Linux...")
    try:
        # The official one-liner: curl -fsSL https://ollama.com/install.sh | sh
        result = subprocess.run(
            ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            timeout=300,
        )
        if result.returncode == 0:
            print("[OK] Ollama installed successfully.")
            return True
        else:
            print(f"[ERROR] Install script exited with code {result.returncode}")
            print("        You may need to run with sudo:")
            print("        curl -fsSL https://ollama.com/install.sh | sudo sh")
            return False
    except FileNotFoundError:
        print("[ERROR] 'curl' or 'bash' not found. Install Ollama manually:")
        print("        curl -fsSL https://ollama.com/install.sh | sh")
        return False
    except Exception as e:
        print(f"[ERROR] Installation failed: {e}")
        return False


def install_ollama_macos():
    """Download and install Ollama on macOS."""
    url = OLLAMA_URLS["darwin_arm64"]
    zip_path = os.path.join(tempfile.gettempdir(), "Ollama-darwin.zip")

    if not download_file(url, zip_path, "Downloading Ollama for macOS"):
        return False

    print("Installing Ollama...")
    try:
        extract_dir = os.path.join(tempfile.gettempdir(), "ollama_extract")
        subprocess.run(["unzip", "-o", "-q", zip_path, "-d", extract_dir], check=True, timeout=60)

        # Move Ollama.app to /Applications
        app_src = os.path.join(extract_dir, "Ollama.app")
        app_dest = "/Applications/Ollama.app"
        if os.path.exists(app_src):
            subprocess.run(["cp", "-R", app_src, app_dest], check=True, timeout=60)
            print("[OK] Ollama.app installed to /Applications.")

            # The CLI binary is inside the .app bundle, symlink it
            cli_src = os.path.join(app_dest, "Contents", "Resources", "ollama")
            if os.path.exists(cli_src):
                try:
                    subprocess.run(
                        ["ln", "-sf", cli_src, "/usr/local/bin/ollama"],
                        check=True, timeout=10,
                    )
                except subprocess.CalledProcessError:
                    # May need sudo
                    subprocess.run(
                        ["sudo", "ln", "-sf", cli_src, "/usr/local/bin/ollama"],
                        timeout=30,
                    )
            print("[OK] Ollama installed successfully.")
            return True
        else:
            print("[ERROR] Could not find Ollama.app in downloaded archive.")
            return False
    except Exception as e:
        print(f"[ERROR] Installation failed: {e}")
        return False
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass


def install_ollama():
    """Auto-detect platform and install Ollama."""
    print()
    print("Ollama is not installed. Installing automatically...")
    print()

    system = platform.system()
    if system == "Windows":
        return install_ollama_windows()
    elif system == "Linux":
        return install_ollama_linux()
    elif system == "Darwin":
        return install_ollama_macos()
    else:
        print(f"[ERROR] Unsupported platform: {system}")
        print("        Please install Ollama manually from https://ollama.com/download")
        return False


# ---------------------------------------------------------------------------
# Ollama server management
# ---------------------------------------------------------------------------

def start_ollama_server(ollama_bin):
    """Start ollama serve in the background and wait for it."""
    print()
    print("[INFO] Ollama server is not running. Starting it...")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        for i in range(20):
            time.sleep(1)
            if check_ollama_running():
                print("[OK] Ollama server started.")
                return True

        print("[ERROR] Ollama server did not start in time.")
        print("        Try starting it manually: ollama serve")
        return False
    except Exception as e:
        print(f"[ERROR] Could not start Ollama server: {e}")
        print("        Try starting it manually: ollama serve")
        return False


# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------

def get_venv_python():
    """Get the path to the Python executable inside the venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def setup_venv():
    """Create and set up the virtual environment."""
    if not os.path.exists(VENV_DIR):
        print("Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)

    python = get_venv_python()

    print("Installing dependencies (this may take a moment)...")
    print()
    subprocess.run(
        [python, "-m", "pip", "install", "--upgrade", "pip"],
        cwd=SCRIPT_DIR, check=True,
    )
    subprocess.run(
        [python, "-m", "pip", "install", "--progress-bar", "on", "-r", "requirements.txt"],
        cwd=SCRIPT_DIR, check=True,
    )
    subprocess.run(
        [python, "-m", "pip", "install", "--progress-bar", "on", "-e", "."],
        cwd=SCRIPT_DIR, check=True,
    )
    print()
    print("[OK] Dependencies installed.")

    return python


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 48)
    print("  AI System Benchmark - Setup and Run")
    print("=" * 48)
    print()
    print(f"[OK] Python {sys.version.split()[0]}")

    # --- Ollama: find, install if missing, start if not running ---
    ollama_bin = find_ollama()

    if ollama_bin is None:
        success = install_ollama()
        if not success:
            sys.exit(1)
        # Re-detect after install
        time.sleep(2)
        ollama_bin = find_ollama()
        if ollama_bin is None:
            print("[ERROR] Ollama was installed but could not be found.")
            print("        You may need to restart your terminal/shell and run again.")
            sys.exit(1)

    print(f"[OK] Ollama found: {ollama_bin}")

    if not check_ollama_running():
        if not start_ollama_server(ollama_bin):
            sys.exit(1)
    else:
        print("[OK] Ollama server is running.")

    # --- Setup Python venv and deps ---
    python = setup_venv()

    # --- Run benchmark ---
    print()
    print("Starting benchmark...")
    print()

    result = subprocess.run(
        [python, "-m", "ai_benchmark.cli", "run", "--no-submit"],
        cwd=SCRIPT_DIR,
    )

    print()
    print("=" * 48)
    if result.returncode == 0:
        print("  Benchmark complete! Results saved to")
        print("  benchmark_result.json")
    else:
        print("  Benchmark failed. See errors above.")
    print("=" * 48)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
