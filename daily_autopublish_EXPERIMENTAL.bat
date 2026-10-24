@echo off
set PYTHONUTF8=1
cd /d "%~dp0"
echo WARNING: This mode may publish AI output without per-article human approval.
echo Use only after reviewing many drafts, confirming image licences and accepting factual-error risk.
if not exist logs mkdir logs
py daily_publish.py --enable-autopublish --push >> logs\daily-autopublish.log 2>&1
exit /b %errorlevel%
