#!/usr/bin/env bash
set -e

echo "================================================"
echo "  AI System Benchmark - Setup and Run"
echo "================================================"
echo ""

# ------------------------------------------------------------------
# Check Python (try python3 first, then python)
# ------------------------------------------------------------------
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python is not installed."
    echo "        Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi
echo "[OK] Python: $($PYTHON_CMD --version 2>&1)"

# ------------------------------------------------------------------
# Check Ollama — find or auto-install
# ------------------------------------------------------------------
OLLAMA_BIN=""

# Try PATH
if command -v ollama &> /dev/null; then
    OLLAMA_BIN="ollama"
# Try common locations
elif [ -x "/usr/local/bin/ollama" ]; then
    OLLAMA_BIN="/usr/local/bin/ollama"
elif [ -x "/usr/bin/ollama" ]; then
    OLLAMA_BIN="/usr/bin/ollama"
elif [ -x "$HOME/.local/bin/ollama" ]; then
    OLLAMA_BIN="$HOME/.local/bin/ollama"
elif [ -x "/opt/homebrew/bin/ollama" ]; then
    OLLAMA_BIN="/opt/homebrew/bin/ollama"
fi

if [ -z "$OLLAMA_BIN" ]; then
    echo ""
    echo "Ollama is not installed. Installing automatically..."
    echo ""

    OS="$(uname -s)"
    case "$OS" in
        Linux)
            # Official install script
            if command -v curl &> /dev/null; then
                curl -fsSL https://ollama.com/install.sh | sh
            elif command -v wget &> /dev/null; then
                wget -qO- https://ollama.com/install.sh | sh
            else
                echo "[ERROR] Neither curl nor wget found. Install Ollama manually:"
                echo "        https://ollama.com/download"
                exit 1
            fi
            ;;
        Darwin)
            echo "Downloading Ollama for macOS..."
            TMPZIP="$(mktemp /tmp/ollama-XXXXXX.zip)"
            curl -fSL "https://ollama.com/download/Ollama-darwin.zip" -o "$TMPZIP"
            TMPDIR_EXTRACT="$(mktemp -d /tmp/ollama-extract-XXXXXX)"
            unzip -o -q "$TMPZIP" -d "$TMPDIR_EXTRACT"
            if [ -d "$TMPDIR_EXTRACT/Ollama.app" ]; then
                cp -R "$TMPDIR_EXTRACT/Ollama.app" /Applications/
                # Symlink CLI
                CLI_SRC="/Applications/Ollama.app/Contents/Resources/ollama"
                if [ -x "$CLI_SRC" ]; then
                    sudo ln -sf "$CLI_SRC" /usr/local/bin/ollama 2>/dev/null || \
                        ln -sf "$CLI_SRC" "$HOME/.local/bin/ollama" 2>/dev/null || true
                fi
                echo "[OK] Ollama.app installed to /Applications."
            else
                echo "[ERROR] Could not find Ollama.app in archive."
                exit 1
            fi
            rm -f "$TMPZIP"
            rm -rf "$TMPDIR_EXTRACT"
            ;;
        *)
            echo "[ERROR] Unsupported OS: $OS"
            echo "        Install Ollama manually: https://ollama.com/download"
            exit 1
            ;;
    esac

    # Re-detect
    sleep 2
    if command -v ollama &> /dev/null; then
        OLLAMA_BIN="ollama"
    elif [ -x "/usr/local/bin/ollama" ]; then
        OLLAMA_BIN="/usr/local/bin/ollama"
    else
        echo "[ERROR] Ollama installed but not found. Restart your terminal and try again."
        exit 1
    fi
fi

echo "[OK] Ollama found: $OLLAMA_BIN"

# ------------------------------------------------------------------
# Start Ollama server if not running
# ------------------------------------------------------------------
if ! curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "[INFO] Starting Ollama server..."
    nohup "$OLLAMA_BIN" serve > /dev/null 2>&1 &
    # Wait for it
    for i in $(seq 1 20); do
        sleep 1
        if curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
            echo "[OK] Ollama server started."
            break
        fi
        if [ "$i" -eq 20 ]; then
            echo "[ERROR] Ollama server did not start. Try: ollama serve"
            exit 1
        fi
    done
else
    echo "[OK] Ollama server is running."
fi

# ------------------------------------------------------------------
# Python venv and dependencies
# ------------------------------------------------------------------
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies (this may take a moment)..."
echo ""
python -m pip install --upgrade pip
python -m pip install --progress-bar on -r requirements.txt
python -m pip install --progress-bar on -e .
echo ""
echo "[OK] Dependencies installed."

# ------------------------------------------------------------------
# Run benchmark
# ------------------------------------------------------------------
echo ""
echo "Starting benchmark..."
echo ""
python -m ai_benchmark.cli run

echo ""
echo "================================================"
echo "  Benchmark complete! Results saved to"
echo "  benchmark_result.json"
echo "================================================"
