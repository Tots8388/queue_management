@echo off
REM ---------------------------------------------------------------------------
REM Stop the Digital Queue & Patient-Flow Management System (Windows).
REM Safe to run when nothing is running. Keep ports in sync with start.bat.
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion

set BACKEND_PORT=8000
set FRONTEND_PORT=3000
set STOPPED=0

call :stop_port %BACKEND_PORT% backend
call :stop_port %FRONTEND_PORT% frontend

if "%STOPPED%"=="0" (
    echo Nothing was running on ports %BACKEND_PORT% or %FRONTEND_PORT%.
)
endlocal
exit /b 0

:stop_port
set PORT=%~1
set LABEL=%~2
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /r /c:":%PORT% "') do (
    echo Stopping %LABEL% ^(pid %%p on port %PORT%^)...
    taskkill /PID %%p /T /F >nul 2>&1
    if errorlevel 1 (
        echo   [!] Could not stop pid %%p — it may need an elevated prompt.
    ) else (
        set STOPPED=1
    )
)
exit /b 0
