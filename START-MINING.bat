@echo off
REM ============================================================
REM  QUASAR MINING - one double-click starts everything.
REM  No typing. No black window. No PowerShell.
REM  Installs Python automatically on first run (one time only).
REM ============================================================
setlocal
cd /d "%~dp0"

REM --- find a Python that can run the miner ---
set PYW=
where pythonw >nul 2>nul
if %errorlevel%==0 set PYW=pythonw
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not defined PYW if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"

if not defined PYW (
    echo Quasar Mining: installing Python - one time only, please wait...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
        set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    ) else (
        echo Automatic install did not finish. Opening python.org for you -
        echo tick "Add python.exe to PATH", then double-click START-MINING again.
        start https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

REM --- launch the miner GUI with no console window ---
start "" "%PYW%" "%~dp0QuasarMiner.py"
exit /b 0
