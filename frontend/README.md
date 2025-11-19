# 🎨 NL2SQL Frontend Demo

Interactive Streamlit UI to chat with your database using natural language.

## 🚀 Quick Start

### 1. Make sure API is running

```powershell
# In project root
.\setup_docker.ps1

# Or if already running:
docker-compose -f docker-compose.full.yml up -d
```

### 2. Install frontend dependencies

```powershell
cd frontend
pip install -r requirements.txt
```

### 3. Run Streamlit app

```powershell
streamlit run streamlit_app.py
```

**App will open at:** http://localhost:8501

---

## ✨ Features

### 💬 Interactive Chat

- Natural language input
- Real-time SQL generation
- Auto-execute queries
- Session-based conversation

### 📊 Data Visualization

- Pretty table display with Pandas
- Download results as CSV
- Query execution metrics
- Confidence scores

### 🗄️ Schema Viewer

- Browse all database tables
- View columns, types, constraints
- Quick reference for queries

### ⚙️ Settings

- Adjustable LLM temperature
- Toggle auto-execution
- API health monitoring
- Example questions

### 🎯 Pre-built Examples

- "How many users do we have?"
- "Show me top 10 products by sales"
- "What's the average order value?"
- "List orders placed in the last 7 days"
- And more...

---

## 🖼️ Screenshots

### Main Chat Interface

```
🤖 NL2SQL Chat Demo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 Ask Questions About Your Database

👤 You: How many users do we have?

🤖 Assistant:

🔍 Generated SQL
Confidence: ✅ 95%

┌─────────────────────────────────┐
│ SELECT COUNT(*) as user_count  │
│ FROM users;                     │
└─────────────────────────────────┘

💡 Explanation: Counts total number of users

📊 Query Results
✅ Query executed successfully! (1 rows, 0.023s)

┌─────────────┐
│ user_count  │
├─────────────┤
│     500     │
└─────────────┘
```

---

## 🔧 Configuration

### API Endpoint

Default: `http://localhost:8000`

To change, edit `streamlit_app.py`:

```python
API_BASE_URL = "http://your-api-url:8000"
```

### Streamlit Settings

Create `.streamlit/config.toml`:

```toml
[server]
port = 8501
address = "localhost"

[theme]
primaryColor = "#1f77b4"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"
```

---

## 🐛 Troubleshooting

### "Connection Error"

- Check if API is running: `curl http://localhost:8000/health`
- Verify Docker containers: `docker ps`
- Check logs: `docker-compose -f docker-compose.full.yml logs nl2sql-api`

### "API is disconnected"

- Start API: `.\setup_docker.ps1`
- Wait for MySQL to be ready (~30s)

### Port already in use

```powershell
# Change Streamlit port
streamlit run streamlit_app.py --server.port 8502
```

---

## 📦 Dependencies

- **streamlit** - Web UI framework
- **requests** - HTTP client for API calls
- **pandas** - Data manipulation and display

---

## 🎨 Customization

### Add More Example Questions

Edit `streamlit_app.py`:

```python
examples = [
    "Your custom question 1",
    "Your custom question 2",
    # Add more...
]
```

### Change Theme Colors

Edit CSS in `streamlit_app.py`:

```python
st.markdown("""
<style>
    .main-header {
        color: #your-color;
    }
</style>
""", unsafe_allow_html=True)
```

---

## 🚀 Deployment

### Run in Production

```powershell
# Install production server
pip install streamlit gunicorn

# Run with authentication
streamlit run streamlit_app.py --server.enableCORS false --server.enableXsrfProtection true
```

### Docker (Optional)

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY frontend/ .

RUN pip install -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0"]
```

```powershell
# Build and run
docker build -t nl2sql-frontend .
docker run -p 8501:8501 nl2sql-frontend
```

---

## 📝 Notes

- Streamlit auto-reloads on file changes during development
- Session state persists during page interactions
- Chat history is stored in browser session only
- For production, consider adding authentication

---

Enjoy chatting with your database! 🎉
