@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Virtual environment not found: .venv
    echo Create it first with: py -3.11 -m venv .venv
    pause
    exit /b 1
)

echo [1/3] Installing runtime and build dependencies...
"%PYTHON%" -m pip install --disable-pip-version-check -r requirements-build.txt
if errorlevel 1 goto :error

echo.
echo [2/3] Running tests...
"%PYTHON%" -m pytest -q
if errorlevel 1 goto :error

echo.
echo [3/3] Building standalone Windows executable...
"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed --name HPBarWatcher --distpath dist --workpath build\pyinstaller --specpath build main.py
if errorlevel 1 goto :error

echo.
echo Build completed:
echo %~dp0dist\HPBarWatcher.exe
pause
exit /b 0

:error
echo.
echo [ERROR] Build failed. See the messages above.
pause
exit /b 1
