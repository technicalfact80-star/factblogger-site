@echo off
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist logs mkdir logs
py automation_runner.py >> logs\automation.log 2>&1
exit /b %errorlevel%
