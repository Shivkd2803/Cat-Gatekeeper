@echo off
python --version 2>NUL
IF %ERRORLEVEL% NEQ 0 (echo Python not found. Get it from https://www.python.org/downloads/ && pause && exit /b)
pip install PyQt5 pywin32 psutil --quiet
python cat_gatekeeper.py
