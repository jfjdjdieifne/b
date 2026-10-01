@echo off
chcp 65001 >nul 2>&1
setlocal
set "PYTHONIOENCODING=utf-8"
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

set "FILEPATH=%~1"
if defined FILEPATH goto :have_path
echo.
echo الرجاء لصق مسار ملف البيانات بالكامل ثم اضغط Enter:
set /p "FILEPATH=> "
:have_path
set "FILEPATH=%FILEPATH:"=%"
if not defined FILEPATH goto :err_empty
if not exist "%FILEPATH%" goto :err_missing

echo.
echo جارٍ فحص الملف ... قد يستغرق دقائق على الملفات الكبيرة، انتظر من فضلك.
"%PY%" "%ROOT%tools\reality_inspect.py" "%FILEPATH%" --out "%ROOT%outputs"
if errorlevel 1 goto :err_run

echo.
echo تم الفحص بنجاح
echo افتح مجلد outputs وستجد تقرير JSON جديداً باسم يبدأ بـ inspect_
echo يمكنك إرسال ملف التقرير كما هو.
pause
exit /b 0

:err_empty
echo.
echo لم يتم إدخال أي مسار. شغّل الملف مرة أخرى واملأ المسار.
pause
exit /b 2

:err_missing
echo.
echo لم يتم العثور على الملف. تأكد من المسار:
echo %FILEPATH%
pause
exit /b 2

:err_run
echo.
echo فشل الفحص - راجع سبب الخطأ المطبوع أعلاه.
pause
exit /b 1
