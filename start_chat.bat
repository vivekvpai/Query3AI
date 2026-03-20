@echo off
title Query3AI Chat Interface
cls
echo Initializing Query3AI Engine...

IF NOT EXIST "venv" (
    echo [INFO] Virtual environment 'venv' not found. Creating it now...
    python -m venv venv
    
    echo [INFO] Activating environment...
    call .\venv\Scripts\activate.bat
    
    echo [INFO] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    
    echo [INFO] Installation successful!
) ELSE (
    call .\venv\Scripts\activate.bat
)

python main.py chat
pause
