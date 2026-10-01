@echo off
chcp 65001 >nul 2>&1
setlocal
set "PYTHONIOENCODING=utf-8"
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" goto :no_venv

set "MODE=%~1"
pushd "%ROOT%trading_project" || goto :fail_cd
if /i "%MODE%"=="dedicated" goto :dedicated

echo تشغيل الاختبارات الكاملة ... قد تستغرق دقائق.
"%PY%" -m pytest
goto :after

:dedicated
echo تشغيل الاختبارات المخصصة Stage 4C-1 ...
"%PY%" -m pytest tests\test_trajectory_stage4c.py

:after
set "RC=%errorlevel%"
popd
if not "%RC%"=="0" goto :fail_tests
echo.
echo نجحت جميع الاختبارات
pause
exit /b 0

:no_venv
echo.
echo لم يتم العثور على البيئة الافتراضية .venv
echo شغّل setup_windows.bat اولاً ثم اعد المحاولة.
pause
exit /b 2

:fail_cd
echo.
echo تعذر فتح مجلد المشروع trading_project. تأكد من سلامة فك الضغط.
pause
exit /b 2

:fail_tests
echo.
echo فشلت بعض الاختبارات. راجع التفاصيل أعلاه.
pause
exit /b %RC%
