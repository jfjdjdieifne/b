@echo off
chcp 65001 >nul 2>&1
setlocal
set "PYTHONIOENCODING=utf-8"
set "ROOT=%~dp0"

echo ============================================
echo   اعداد بيئة العمل المحلية - مرة واحدة
echo ============================================
echo.

set "PY="
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=python"
  )
)
if not defined PY goto :no_python

echo [1/5] تم العثور على Python مناسب:
call %PY% --version
echo.

echo [2/5] انشاء البيئة الافتراضية .venv ...
call %PY% -m venv "%ROOT%.venv"
if errorlevel 1 goto :fail_venv

echo [3/5] تحديث pip ...
"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail_pip

echo [4/5] تثبيت متطلبات المشروع ...
"%ROOT%.venv\Scripts\python.exe" -m pip install -e "%ROOT%trading_project[dev]"
if errorlevel 1 goto :fail_install

echo [5/5] مطابقة بيئة الاختبار المعتمَدة (pandas 2.x كما اجتازت الاعتماد) ...
"%ROOT%.venv\Scripts\python.exe" -m pip install "pandas>=2.0,<3"
if errorlevel 1 goto :fail_pin

echo.
echo تم الاعداد بنجاح
echo يمكنك الان تشغيل inspect_data.bat و run_tests.bat
pause
exit /b 0

:no_python
echo.
echo لم يتم العثور على Python 3.10 او احدث.
echo حمّل Python من python.org واثناء التثبيت فعّل خيار Add python.exe to PATH
echo ثم شغّل هذا الملف مرة أخرى.
pause
exit /b 1

:fail_venv
echo.
echo فشل انشاء البيئة الافتراضية. تأكد من وجود مساحة كافية ثم اعد المحاولة.
pause
exit /b 1

:fail_pip
echo.
echo فشل تحديث pip. تأكد من الاتصال بالانترنت ثم اعد المحاولة.
pause
exit /b 1

:fail_install
echo.
echo فشل تثبيت متطلبات المشروع. تأكد من الاتصال بالانترنت ثم اعد المحاولة.
pause
exit /b 1

:fail_pin
echo.
echo فشل مطابقة بيئة الاختبار. تأكد من الاتصال بالانترنت ثم اعد المحاولة.
pause
exit /b 1
