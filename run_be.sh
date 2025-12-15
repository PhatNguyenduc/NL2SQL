#!/bin/bash
# Activate venv
source venv/bin/activate

# Run backend with uvicorn
exec uvicorn main:app --host 0.0.0.0 --port 8000
