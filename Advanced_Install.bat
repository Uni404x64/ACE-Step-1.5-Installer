@echo off
setlocal enabledelayedexpansion
title TEST
echo === TEST START ===
echo Script path: %~f0
echo Arg 1: %~1
echo.
echo If you see this, the script runs.
echo.
pause
exit /b