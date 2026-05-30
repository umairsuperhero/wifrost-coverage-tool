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

if not exist frontend\node_modules (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo Starting WiFrost RF Backend on http://127.0.0.1:8000...
start "WiFrost Backend" cmd /c "call venv\Scripts\activate && uvicorn api:app --host 127.0.0.1 --port 8000"

echo Starting WiFrost RF Frontend on http://127.0.0.1:3000...
cd frontend
start "WiFrost Frontend" cmd /c "npm run dev"
cd ..

echo WiFrost TVWS Coverage tool is running.
echo Close the newly opened terminal windows to stop the servers.
pause
