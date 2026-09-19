@echo off
title GPU LP Solver Web Server
echo ===================================================
echo Starting GPU LP Solver Web Server...
echo ===================================================
cd /d "%~dp0"
start http://127.0.0.1:8000
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" app.py
) else (
    py -3 app.py
)
pause