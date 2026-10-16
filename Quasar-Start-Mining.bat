@echo off
REM ============================================================
REM  QUASAR COIN - One-Click Miner
REM  Double-click this file. No typing needed. Nothing to learn.
REM  It sets up everything and starts mining automatically.
REM ============================================================
title Quasar Miner - One-Click Mining
color 0E

echo ============================================================
echo   QUASAR COIN - One-Click Miner
echo   No typing needed. Just watch - everything is automatic.
echo ============================================================
echo.

REM ---- Step 1: Python check ----
python --version >nul 2>&1
if errorlevel 1 (
  echo  [!!] Python is not installed on this computer.
  echo       Opening the download page for you...
  start https://www.python.org/downloads/
  echo.
  echo  Install Python ^(tick "Add python.exe to PATH"^),
  echo  then double-click this file again.
  echo.
  pause
  exit /b
)
echo  [1/5] Python found - OK

REM ---- Step 2: needed component ----
python -m pip install --quiet ecdsa >nul 2>&1
echo  [2/5] Components ready - OK

REM ---- Step 3: data folder (next to this file, no typing) ----
set "QDATA=%~dp0QuasarData"
if not exist "%QDATA%" mkdir "%QDATA%" >nul 2>&1
set QUASAR_DATA_DIR=%QDATA%
echo  [3/5] Data folder ready - OK

REM ---- Step 4: go to the miner folder (this file lives inside it) ----
cd /d "%~dp0"

REM ---- Step 5: wallet (created once, reused forever) ----
if not exist "%QDATA%\wallets\miner.json" (
  echo  [4/5] Creating your wallet - one time only...
  python quasar_cli.py new-address miner >nul 2>&1
  echo        Wallet created - OK
) else (
  echo  [4/5] Wallet found - OK
)

REM ---- Optional: website wallet link ----
if exist "%~dp0quasar-report.txt" (
  set /p QUASAR_REPORT_URL=<"%~dp0quasar-report.txt"
  echo  [5/5] Website wallet link - ON
) else (
  echo  [5/5] Website wallet link - off ^(optional^)
)

REM ---- Seed node: join the main network ----
set SEEDARG=
if exist "%~dp0seed.txt" call :readseed

echo.
echo ============================================================
echo   MINING STARTED!
echo   This window must stay OPEN while mining.
echo   New coins go to your wallet automatically every ~30 sec.
echo.
echo   To STOP: press Ctrl+C, or just close this window.
echo   Your coins stay saved - nothing is lost.
echo ============================================================
echo.

python quasar_cli.py start-node --datadir "%QDATA%" --mine-auto miner %SEEDARG%

echo.
echo  Miner stopped. Your wallet and coins are saved in:
echo  %QDATA%
echo  Double-click this file anytime to mine again.
pause
goto :eof

REM ---- Seed reader: safe against empty / comment / template lines ----
:readseed
set /p QSEED=<"%~dp0seed.txt"
if "%QSEED%"=="" goto :eof
echo %QSEED% | findstr /B /C:"#">nul
if not errorlevel 1 goto :eof
echo %QSEED% | findstr /C:"REPLACE_THIS">nul
if not errorlevel 1 (
  echo        [seed.txt] me apna seed address likho, phir dobara chalao.
  echo        Bina seed ke ye laptop KHUD seed node banega.
  goto :eof
)
set SEEDARG=--seed %QSEED%
echo        Network seed found - joining: %QSEED%
goto :eof
