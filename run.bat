@echo off
cd /d "%~dp0"
if not exist venv (
    echo Setting up for first time - this takes 2 minutes...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)
echo Opening WiFrost Coverage Tool...
streamlit run app.py
pause
