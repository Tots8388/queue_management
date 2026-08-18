@echo off
REM ---------------------------------------------------------------------------
REM Start the Digital Queue & Patient-Flow Management System (Windows).
REM Database: PostgreSQL.  Backend: Django + DRF + Channels (ASGI).
REM Frontend: Next.js.  Keep these ports in sync with stop.bat.
REM ---------------------------------------------------------------------------
setlocal

set BACKEND_PORT=8000
set PATIENT_PORT=3000
set STAFF_PORT=3001
set ROOT=%~dp0
set VENV_PYTHON=%ROOT%backend\.venv\Scripts\python.exe
set COMPOSE_FILE=%ROOT%deploy\docker-compose.yml
set DB_CONTAINER=queue-management-pg

if not exist "%VENV_PYTHON%" (
    echo [!] Backend virtual environment not found at backend\.venv
    echo     Create it with:
    echo         python -m venv backend\.venv
    echo         backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    exit /b 1
)

REM One install covers both frontends: they are npm workspaces of the repo
REM root, so their dependencies are hoisted to node_modules there. That is also
REM what lets shared\ui resolve react and next — see package.json.
if not exist "%ROOT%node_modules" (
    echo [!] Frontend dependencies not installed.
    echo     Run this from the repository root:  npm install
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM Database. PostgreSQL is the specified database; an unset DATABASE_URL is a
REM silent downgrade to the SQLite prototype fallback, so refuse to start on it.
REM A value already in the machine's environment wins, exactly as settings.py
REM treats it — so .env is read only to fill the gap, and a deployment that sets
REM the variable in the machine's environment needs no .env at all.
REM ---------------------------------------------------------------------------
if exist "%ROOT%.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%.env") do (
        if /i "%%a"=="DATABASE_URL" if not defined DATABASE_URL set "DATABASE_URL=%%b"
        if /i "%%a"=="POSTGRES_PASSWORD" set "COMPOSE_DB=1"
    )
)

REM COMPOSE_DB means this machine runs the containerised development database.
REM The clinic server has PostgreSQL installed natively and sets no POSTGRES_*,
REM so nothing is started here and its own service is used instead.
if not defined COMPOSE_DB goto :db_env
if not exist "%COMPOSE_FILE%" goto :db_env
where docker >nul 2>&1 || goto :db_env

echo Starting PostgreSQL (%DB_CONTAINER%)...
docker compose --env-file "%ROOT%.env" -f "%COMPOSE_FILE%" up -d --wait --wait-timeout 90
if errorlevel 1 (
    echo [!] The database container did not come up healthy. Not starting.
    echo     Inspect it with:  docker compose -f deploy\docker-compose.yml logs
    exit /b 1
)

:db_env
if not defined DATABASE_URL (
    echo [!] DATABASE_URL is not set in .env or in this machine's environment.
    echo     The backend would fall back to the SQLite prototype database, which
    echo     is not acceptable for the pilot or any real data.
    echo.
    echo     Copy .env.example to .env and set it. With no local PostgreSQL:
    echo         docker compose --env-file .env -f deploy\docker-compose.yml up -d
    echo     See docs\development.md, "Database".
    exit /b 1
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

REM Two separate applications. The patient app carries the token entry, the
REM patient status view and the waiting-room board; the staff app carries the
REM sign-in and the four dashboards. Nothing served on the patient port can
REM reach a staff screen, which is the point of the split.
echo Starting patient app on port %PATIENT_PORT%...
start "Queue patient app" cmd /k "cd /d "%ROOT%frontend" && npm run dev -- --port %PATIENT_PORT% --hostname 0.0.0.0"

echo Starting staff app on port %STAFF_PORT%...
start "Queue staff app" cmd /k "cd /d "%ROOT%staff-frontend" && npm run dev -- --port %STAFF_PORT% --hostname 0.0.0.0"

echo.
echo   Patients    http://localhost:%PATIENT_PORT%
echo   Waiting room http://localhost:%PATIENT_PORT%/display
echo   Staff       http://localhost:%STAFF_PORT%
echo   API         http://localhost:%BACKEND_PORT%/api/
echo   Health      http://localhost:%BACKEND_PORT%/api/health/
echo   Admin       http://localhost:%BACKEND_PORT%/admin/
echo.
echo   Sign-in details for the fictional accounts: docs\test-accounts.md
echo.
echo   On the clinic LAN, reach these at this machine's IP instead of
echo   localhost. Patient phones and the waiting-room screen get the patient
echo   port; only staff terminals are given the staff port:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do echo       patients http://%%a:%PATIENT_PORT%   staff http://%%a:%STAFF_PORT%
echo.
echo   Stop everything with:  stop.bat
endlocal
