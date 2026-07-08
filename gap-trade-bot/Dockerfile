FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

EXPOSE 5000

# Bind to Render's injected $PORT (falls back to 5000 locally). Shell form so
# ${PORT} expands; `exec` keeps gunicorn as PID 1 for correct signal handling.
# --graceful-timeout gives in-flight work a moment to finish on redeploy.
CMD exec gunicorn --worker-class eventlet -w 1 --timeout 120 --graceful-timeout 30 --bind 0.0.0.0:${PORT:-5000} app:app
