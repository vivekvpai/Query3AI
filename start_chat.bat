@echo off
title Query3AI Chat Interface
cls
echo Initializing Query3AI Engine...

IF NOT EXIST "venv" (
    echo [INFO] Virtual environment 'venv' not found. Creating it now...
    python -m venv venv
    
    echo [INFO] Activating environment...
    call .\venv\Scripts\activate.bat
    
    echo [INFO] Installing package query3ai...
    pip install -e .
    
    echo [INFO] Installation successful!
) ELSE (
    call .\venv\Scripts\activate.bat
)

query3ai chat
pause
