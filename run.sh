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

# Ensure npm dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

echo "Starting WiFrost RF Backend on http://127.0.0.1:8000..."
./venv/bin/uvicorn api:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Starting WiFrost RF Frontend on http://127.0.0.1:3001..."
cd frontend
PORT=3001 npm run dev &
FRONTEND_PID=$!

cleanup() {
    echo "Shutting down servers..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    exit 0
}

trap cleanup SIGINT SIGTERM

wait
