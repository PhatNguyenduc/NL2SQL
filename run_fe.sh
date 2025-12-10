#!/bin/bash
# Activate venv
source venv/bin/activate

# Run Streamlit UI
exec streamlit run ./frontend/streamlit_app.py --server.address=0.0.0.0 --server.port=9222
