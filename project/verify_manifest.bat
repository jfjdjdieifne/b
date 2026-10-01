@echo off
chcp 65001 >nul 2>&1
setlocal
set "PYTHONIOENCODING=utf-8"
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo جارٍ التحقق من سلامة ملفات المشروع ...
"%PY%" "%ROOT%tools\verify_manifest.py" --root "%ROOT%trading_project"
if errorlevel 1 goto :fail

echo.
echo تم التحقق بنجاح
pause
exit /b 0

:fail
echo.
echo فشل التحقق - توجد ملفات غير مطابقة. راجع التفاصيل أعلاه.
pause
exit /b 1
