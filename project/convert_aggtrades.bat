@echo off
chcp 65001 >nul 2>&1
setlocal
REM convert_aggtrades.bat - LOCAL SOURCE CONVERTER runner (converter boundary only)
REM Converts Binance Spot public-data aggTrades CSV -> 1-minute fact table CSV + sidecar JSON.
REM Usage: convert_aggtrades.bat "X:\path\BTCUSDT-aggTrades-2026-05.csv" [optional_output_prefix]

set "TOOLS_DIR=%~dp0tools"
set "PY="
if exist "%TOOLS_DIR%\.venv\Scripts\python.exe" set "PY=%TOOLS_DIR%\.venv\Scripts\python.exe"
if "%PY%"=="" (where python >nul 2>&1 && set "PY=python")
if "%PY%"=="" (where py >nul 2>&1 && set "PY=py -3")
if "%PY%"=="" (
    echo [!] Python was not found on PATH. Install Python 3.8+ first.
    exit /b 1
)

set "SOURCE=%~1"
if "%SOURCE%"=="" (
    set /p "SOURCE=Enter the full path of the aggTrades CSV: "
)
if "%SOURCE%"=="" (
    echo [!] No source path provided. Cancelled.
    exit /b 1
)
if not exist "%SOURCE%" (
    echo [!] File not found: %SOURCE%
    exit /b 1
)

echo Converting (streaming, bounded memory):
echo   SOURCE: %SOURCE%
echo.

set "EXTRA="
if not "%~2"=="" set "EXTRA=--out %~2"

%PY% "%TOOLS_DIR%\aggtrades_to_minute_facts.py" "%SOURCE%" %EXTRA%
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo [!] Conversion FAILED with exit code %RC% ^(fail-closed^). See .FAILED.json next to the output prefix.
)
exit /b %RC%
