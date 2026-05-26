@echo off
title Cat Gatekeeper Setup
echo ================================
echo   Cat Gatekeeper - First Setup
echo ================================
echo.
echo Step 1: Checking Python installation...
python --version 2>NUL
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Python is not installed!
    echo Please download and install Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b
)
echo Python found!
echo.
echo Step 2: Installing required packages...
pip install PyQt5 Pillow --quiet
echo.
echo Step 3: Launching Cat Gatekeeper...
echo.
python cat_gatekeeper.py
