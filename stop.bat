@echo off
REM ---------------------------------------------------------------------------
REM Stop the Digital Queue & Patient-Flow Management System (Windows).
REM Safe to run when nothing is running. Keep ports in sync with start.bat.
REM ---------------------------------------------------------------------------
setlocal

set BACKEND_PORT=8000
set FRONTEND_PORT=3000
set STOPPED=0

call :stop_port %BACKEND_PORT% backend
call :stop_port %FRONTEND_PORT% frontend

if "%STOPPED%"=="0" (
    echo Nothing was running on ports %BACKEND_PORT% and %FRONTEND_PORT%.
) else (
    echo Done.
)
endlocal
exit /b 0

:stop_port
set PORT=%~1
set LABEL=%~2

REM A process listening on both IPv4 and IPv6 appears on several netstat lines
REM with the same PID. Without de-duplicating, the second taskkill targets an
REM already-dead process and reports a failure that did not happen.
set "SEEN="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"LISTENING" ^| findstr /r /c:":%PORT% "') do (
    echo %%SEEN%% | findstr /c:"[%%p]" >nul || (
        call :kill_pid %%p "%LABEL%" %PORT%
        call set "SEEN=%%SEEN%% [%%p]"
    )
)
exit /b 0

:kill_pid
set PID=%~1
set WHAT=%~2
set ON_PORT=%~3
echo Stopping %WHAT% (pid %PID% on port %ON_PORT%)...
taskkill /PID %PID% /T /F >nul 2>&1
if errorlevel 1 (
    echo   Warning: could not stop pid %PID%. It may need an elevated prompt.
) else (
    set STOPPED=1
)
exit /b 0
