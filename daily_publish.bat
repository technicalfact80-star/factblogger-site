@echo off
cd /d "%~dp0"
echo WARNING: Unattended publication can publish factual errors and can hurt reader trust or AdSense readiness.
echo Default mode only creates a draft. Edit this file only after testing the website and reviewing many generated articles.
py daily_publish.py
pause
