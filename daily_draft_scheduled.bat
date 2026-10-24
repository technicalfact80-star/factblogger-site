@echo off
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist logs mkdir logs
py daily_draft.py >> logs\daily-draft.log 2>&1
exit /b %errorlevel%
