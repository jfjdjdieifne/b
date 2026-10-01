@echo off
REM BTC May 2026 field runner - single command wrapper (ASCII only).
REM Arabic explanation lives in README_RESULT_AR.txt / README_OWNER.txt (UTF-8).
setlocal
cd /d "%~dp0"
python run_btc_may_2026.py %*
exit /b %errorlevel%
