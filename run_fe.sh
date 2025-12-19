#!/bin/bash
source venv/bin/activate
cd frontend

# Run Vite dev server with host + port
exec npm run dev -- --host 0.0.0.0 --port 9222
