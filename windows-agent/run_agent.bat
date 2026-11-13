@echo off
cd /d "%~dp0"
python soares_activity_agent.py
if errorlevel 1 pause
