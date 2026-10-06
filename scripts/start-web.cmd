@echo off
setlocal
cd /d "%~dp0\.."
where python >nul 2>nul
if errorlevel 1 (
  py -3 -m idea_parallax web --open
) else (
  python -m idea_parallax web --open
)
if errorlevel 1 pause
