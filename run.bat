@echo off
echo ================================================
echo   AI System Benchmark - Setup and Run
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found.

:: Check Ollama — try PATH first, then common locations
set "OLLAMA_BIN="
ollama --version >nul 2>&1
if %errorlevel% equ 0 (
    set "OLLAMA_BIN=ollama"
    goto :ollama_found
)
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_BIN=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    goto :ollama_found
)
if exist "%PROGRAMFILES%\Ollama\ollama.exe" (
    set "OLLAMA_BIN=%PROGRAMFILES%\Ollama\ollama.exe"
    goto :ollama_found
)

:: Ollama not found — download and install
echo.
echo Ollama is not installed. Downloading and installing...
echo.
set "INSTALLER=%TEMP%\OllamaSetup.exe"
powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%INSTALLER%'"
if not exist "%INSTALLER%" (
    echo [ERROR] Failed to download Ollama installer.
    pause
    exit /b 1
)
echo Installing Ollama (this may take a minute)...
"%INSTALLER%" /VERYSILENT /NORESTART /MERGETASKS=!desktopicon
timeout /t 3 /nobreak >nul
del "%INSTALLER%" >nul 2>&1

:: Re-check after install
ollama --version >nul 2>&1
if %errorlevel% equ 0 (
    set "OLLAMA_BIN=ollama"
    goto :ollama_found
)
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_BIN=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    goto :ollama_found
)
echo [ERROR] Ollama installation failed. Please install manually from https://ollama.com/download
pause
exit /b 1

:ollama_found
echo [OK] Ollama found: %OLLAMA_BIN%

:: Check if Ollama server is running, start if not
powershell -Command "try { Invoke-WebRequest -Uri 'http://localhost:11434/api/version' -TimeoutSec 3 -UseBasicParsing | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Starting Ollama server...
    start /b "" "%OLLAMA_BIN%" serve >nul 2>&1
    timeout /t 5 /nobreak >nul
    echo [OK] Ollama server started.
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies (this may take a moment)...
echo.
python -m pip install --upgrade pip
python -m pip install --progress-bar on -r requirements.txt
python -m pip install --progress-bar on -e .
echo.
echo [OK] Dependencies installed.

:: Run the benchmark
echo.
echo Starting benchmark...
echo.
python -m ai_benchmark.cli run --no-submit

echo.
echo ================================================
echo   Benchmark complete! Results saved to
echo   benchmark_result.json
echo ================================================
pause
