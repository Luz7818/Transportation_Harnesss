@echo off
rem Build single-file exe: dist\TransportationHarness.exe
rem First run creates an isolated venv at packaging\.venv and installs deps into it.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [build] ERROR: python not found in PATH.
    exit /b 1
)

if not exist .venv (
    echo [build] First build: creating venv and installing fastapi/uvicorn/pywebview/pyinstaller ...
    python -m venv .venv
    if errorlevel 1 exit /b 1
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install "fastapi>=0.110" "uvicorn>=0.29" "pywebview>=5" "pyinstaller>=6.0"
    if errorlevel 1 exit /b 1
)

echo [build] Running PyInstaller ...
.venv\Scripts\pyinstaller harness.spec --noconfirm --distpath ..\dist --workpath ..\build
if errorlevel 1 (
    echo [build] FAILED - see output above.
    exit /b 1
)
echo [build] DONE: %~dp0..\dist\TransportationHarness.exe
endlocal
