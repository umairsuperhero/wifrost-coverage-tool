#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
    echo "Setting up for first time - this takes 2 minutes..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
echo "Opening WiFrost Coverage Tool..."
streamlit run app.py
