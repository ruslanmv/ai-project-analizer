# start.sh
# --------
# Docker/entrypoint script: activates the virtualenv (if present) and runs the FastAPI app.

#!/usr/bin/env bash
set -e

# If a virtual environment exists, activate it
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Launch the FastAPI application
python app.py


# Launch the FastAPI application with Uvicorn
#uvicorn app:app --host 0.0.0.0 --port "${APP_PORT:-8000}"