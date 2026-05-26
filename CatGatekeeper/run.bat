@echo off
echo Checking Python...
python --version 2>NUL
IF %ERRORLEVEL% NEQ 0 (
    echo Python not found. Please install Python from https://python.org
    pause
    exit
)
echo Installing dependencies...
pip install PyQt5 Pillow --quiet
echo Launching Cat Gatekeeper...
python cat_gatekeeper.py
