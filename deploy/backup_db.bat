@echo off
REM ---------------------------------------------------------------------------
REM Daily PostgreSQL backup for the queue database.
REM
REM Schedule with Task Scheduler after the clinic closes:
REM   schtasks /Create /TN "QueueBackup" /TR "%~f0" /SC DAILY /ST 19:00 /RU SYSTEM
REM
REM Reads DATABASE_URL and BACKUP_DIR from the repo-root .env. No credentials
REM appear in this file.
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion

set ROOT=%~dp0..
set ENV_FILE=%ROOT%\.env
set KEEP_DAYS=30
set DB_CONTAINER=queue-management-pg

if not exist "%ENV_FILE%" (
    echo [ERROR] %ENV_FILE% not found. Cannot back up without DATABASE_URL.
    exit /b 1
)

REM Pull the two values we need out of .env without echoing the rest.
for /f "usebackq tokens=1,* delims==" %%a in ("%ENV_FILE%") do (
    if /i "%%a"=="DATABASE_URL" set "DATABASE_URL=%%b"
    if /i "%%a"=="BACKUP_DIR" set "BACKUP_DIR=%%b"
)

if "%DATABASE_URL%"=="" (
    echo [ERROR] DATABASE_URL is not set in .env.
    exit /b 1
)

if "%BACKUP_DIR%"=="" (
    echo [ERROR] BACKUP_DIR is not set in .env. Point it at a different
    echo         physical disk from the database — a backup on the same disk
    echo         does not protect you from the disk failing.
    exit /b 1
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Sortable timestamp, locale-independent.
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set STAMP=%%t
set TARGET=%BACKUP_DIR%\queue-%STAMP%.dump

echo Backing up to %TARGET% ...

REM The clinic server has PostgreSQL installed, so pg_dump is on PATH and is
REM used directly. A development machine may instead run the database in the
REM container from docker-compose.yml, where pg_dump lives inside the container
REM and writes the dump out over stdout. Either way the file is identical.
where pg_dump >nul 2>&1 || goto :dump_in_container
pg_dump --format=custom --no-owner --dbname="%DATABASE_URL%" --file="%TARGET%"
goto :after_dump

:dump_in_container
where docker >nul 2>&1 || (
    echo [ERROR] Neither pg_dump nor docker is available. NO BACKUP WAS TAKEN.
    exit /b 1
)
docker exec %DB_CONTAINER% pg_dump --format=custom --no-owner --dbname="%DATABASE_URL%" > "%TARGET%"

:after_dump
if errorlevel 1 (
    echo [ERROR] pg_dump failed. NO BACKUP WAS TAKEN TONIGHT.
    REM Remove any part-written file: a truncated dump that looks like a
    REM backup is worse than an obvious absence.
    if exist "%TARGET%" del "%TARGET%"
    exit /b 1
)

REM A zero-byte file would pass a "does it exist" check and restore nothing.
for %%F in ("%TARGET%") do set SIZE=%%~zF
if "%SIZE%"=="0" (
    echo [ERROR] Backup file is empty. Deleting it.
    del "%TARGET%"
    exit /b 1
)

echo Backup complete: %SIZE% bytes.

echo Removing backups older than %KEEP_DAYS% days...
forfiles /P "%BACKUP_DIR%" /M queue-*.dump /D -%KEEP_DAYS% /C "cmd /c del @path" 2>nul

echo Done.
endlocal
exit /b 0
