@echo off
cd /d "%~dp0"
echo Building FactBlogger...
py build_site.py
if errorlevel 1 (
  echo Build failed. Check the error above and make sure Python 3.11+ is installed.
  pause
  exit /b 1
)
echo.
echo Opening FactBlogger at http://localhost:8000
 echo Keep this window open while previewing.
py -m http.server 8000 --directory public
pause
