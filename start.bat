@echo off
REM ---------------------------------------------------------------------------
REM Start the Digital Queue & Patient-Flow Management System (Windows).
REM Backend: Django + DRF + Channels (ASGI).  Frontend: Next.js.
REM Keep these ports in sync with stop.bat.
REM ---------------------------------------------------------------------------
setlocal

set BACKEND_PORT=8000
set FRONTEND_PORT=3000
set ROOT=%~dp0
set VENV_PYTHON=%ROOT%backend\.venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo [!] Backend virtual environment not found at backend\.venv
    echo     Create it with:
    echo         python -m venv backend\.venv
    echo         backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
    echo [!] Frontend dependencies not installed.
    echo     Run:  cd frontend ^&^& npm install
    exit /b 1
)

if not exist "%ROOT%.env" (
    echo [i] No .env found — using development defaults.
    echo     Copy .env.example to .env to configure this machine.
)

echo Applying database migrations...
pushd "%ROOT%backend"
"%VENV_PYTHON%" manage.py migrate --noinput
if errorlevel 1 (
    echo [!] Migrations failed. Not starting.
    popd
    exit /b 1
)
popd

echo Starting backend on port %BACKEND_PORT%...
start "Queue backend" cmd /k "cd /d "%ROOT%backend" && "%VENV_PYTHON%" manage.py runserver 0.0.0.0:%BACKEND_PORT%"

echo Starting frontend on port %FRONTEND_PORT%...
start "Queue frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev -- --port %FRONTEND_PORT% --hostname 0.0.0.0"

echo.
echo   Frontend    http://localhost:%FRONTEND_PORT%
echo   API         http://localhost:%BACKEND_PORT%/api/
echo   Health      http://localhost:%BACKEND_PORT%/api/health/
echo   Admin       http://localhost:%BACKEND_PORT%/admin/
echo.
echo   On the clinic LAN, staff terminals and display screens reach these at
echo   this machine's IP instead of localhost:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do echo       http://%%a:%FRONTEND_PORT%
echo.
echo   Stop everything with:  stop.bat
endlocal
