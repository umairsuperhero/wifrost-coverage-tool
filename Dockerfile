FROM python:3.11-slim

WORKDIR /app

# Build tools needed by some Python packages (e.g. numpy, scipy wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure the SQLite history database directory exists
RUN mkdir -p /app/data

# Render (and most PaaS) inject $PORT at runtime — fall back to 8000 for local Docker use.
# Shell form is required so the variable is expanded before uvicorn sees it.
EXPOSE 8000
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
