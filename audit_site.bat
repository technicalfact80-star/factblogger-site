@echo off
cd /d "%~dp0"
echo Building FactBlogger before preflight...
py build_site.py
if errorlevel 1 goto :error
echo.
echo Running technical preflight...
py check_site.py
if errorlevel 1 echo Preflight reported blockers. This is expected until the live URL and contact details are configured.
pause
exit /b 0
:error
echo Build failed. Check Python installation and the error above.
pause
exit /b 1
