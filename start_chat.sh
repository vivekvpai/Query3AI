#!/bin/bash
clear
echo "Initializing Query3AI Engine..."

# Check if 'venv' directory exists
if [ ! -d "venv" ]; then
    echo "[INFO] Virtual environment 'venv' not found. Creating it now..."
    # 'python3' is standard for Unix distributions
    python3 -m venv venv
    
    echo "[INFO] Activating environment..."
    source venv/bin/activate
    
    echo "[INFO] Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    
    echo "[INFO] Installation successful!"
else
    source venv/bin/activate
fi

python main.py chat
