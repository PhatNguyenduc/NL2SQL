"""
NL2SQL Streamlit Demo
Interactive UI to chat with database using natural language
"""

import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
DEFAULT_SESSION_ID = "streamlit-demo"

# Page config
st.set_page_config(
    page_title="NL2SQL Chat Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stAlert {
        border-radius: 10px;
    }
    .sql-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
    }
    .confidence-high {
        color: #28a745;
        font-weight: bold;
    }
    .confidence-medium {
        color: #ffc107;
        font-weight: bold;
    }
    .confidence-low {
        color: #dc3545;
        font-weight: bold;
    }
    .message-user {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .message-assistant {
        background-color: #f5f5f5;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def check_api_health() -> Dict[str, Any]:
    """Check if API is accessible and healthy"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "unhealthy", "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def send_chat_message(message: str, execute: bool = True, session_id: str = DEFAULT_SESSION_ID) -> Optional[Dict]:
    """Send chat message to API"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "message": message,
                "execute_query": execute,
                "session_id": session_id,
                "temperature": st.session_state.get("temperature", 0.1)
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None


def get_schema() -> Optional[Dict]:
    """Get database schema"""
    try:
        response = requests.get(f"{API_BASE_URL}/schema", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Failed to fetch schema: {str(e)}")
        return None


def get_conversation_history(session_id: str = DEFAULT_SESSION_ID, limit: int = 50) -> Optional[Dict]:
    """Get conversation history"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/conversation/history",
            json={"session_id": session_id, "limit": limit},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Failed to fetch history: {str(e)}")
        return None


def format_confidence(confidence: float) -> str:
    """Format confidence with color"""
    if confidence >= 0.8:
        css_class = "confidence-high"
        emoji = "✅"
    elif confidence >= 0.6:
        css_class = "confidence-medium"
        emoji = "⚠️"
    else:
        css_class = "confidence-low"
        emoji = "❌"
    
    return f'<span class="{css_class}">{emoji} {confidence:.1%}</span>'


def display_query_result(data: Dict):
    """Display query result in a nice format"""
    
    # SQL Generation
    if "sql_generation" in data:
        sql_gen = data["sql_generation"]
        
        st.markdown("### 🔍 Generated SQL")
        
        # Confidence badge
        if "confidence" in sql_gen:
            st.markdown(
                f"**Confidence:** {format_confidence(sql_gen['confidence'])}",
                unsafe_allow_html=True
            )
        
        # SQL Query
        st.markdown('<div class="sql-box">', unsafe_allow_html=True)
        st.code(sql_gen.get("query", ""), language="sql")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Explanation
        if "explanation" in sql_gen:
            st.info(f"💡 **Explanation:** {sql_gen['explanation']}")
    
    # Execution Results
    if "execution" in data and data["execution"]:
        exec_result = data["execution"]
        
        st.markdown("### 📊 Query Results")
        
        if exec_result.get("success"):
            rows = exec_result.get("rows", [])
            row_count = exec_result.get("row_count", 0)
            exec_time = exec_result.get("execution_time", 0)
            
            st.success(f"✅ Query executed successfully! ({row_count} rows, {exec_time:.3f}s)")
            
            if rows:
                # Display as DataFrame
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
                
                # Download button with unique key
                csv = df.to_csv(index=False)
                download_key = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key=download_key
                )
            else:
                st.warning("No data returned")
        else:
            error_msg = exec_result.get("error", "Unknown error")
            st.error(f"❌ Query execution failed: {error_msg}")


def sidebar():
    """Sidebar with settings and info"""
    st.sidebar.title("⚙️ Settings")
    
    # API Status
    st.sidebar.markdown("### 🔌 API Status")
    health = check_api_health()
    
    if health.get("status") == "healthy":
        st.sidebar.success("✅ Connected")
        
        # Display API info
        with st.sidebar.expander("📊 API Info"):
            st.write(f"**LLM Provider:** {health.get('llm_provider', 'N/A')}")
            st.write(f"**Model:** {health.get('llm_model', 'N/A')}")
            st.write(f"**Database:** {health.get('database_connected', False) and '✅' or '❌'}")
            st.write(f"**Tables:** {health.get('tables', 0)}")
    else:
        st.sidebar.error("❌ Disconnected")
        st.sidebar.warning(f"Error: {health.get('error', 'Unknown')}")
        st.sidebar.info("Make sure API is running at http://localhost:8000")
    
    # Temperature slider
    st.sidebar.markdown("### 🌡️ LLM Temperature")
    temperature = st.sidebar.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.1,
        help="Lower = more deterministic, Higher = more creative"
    )
    st.session_state.temperature = temperature
    
    # Auto-execute toggle
    st.sidebar.markdown("### 🚀 Execution")
    auto_execute = st.sidebar.checkbox("Auto-execute queries", value=True)
    st.session_state.auto_execute = auto_execute
    
    # Example questions
    st.sidebar.markdown("### 💡 Example Questions")
    examples = [
        "How many users do we have?",
        "Show me top 10 products by sales",
        "What's the average order value?",
        "List orders placed in the last 7 days",
        "Show categories with most products",
        "Users who never placed an order",
        "Products with rating above 4.5",
        "Total revenue by month",
        "Top 5 customers by spending",
        "Products out of stock"
    ]
    
    for example in examples:
        if st.sidebar.button(f"💬 {example}", key=example):
            st.session_state.example_clicked = example
    
    # Database schema viewer
    if st.sidebar.button("🗄️ View Database Schema"):
        st.session_state.show_schema = True


def main():
    """Main app"""
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = DEFAULT_SESSION_ID
    if "example_clicked" not in st.session_state:
        st.session_state.example_clicked = None
    if "show_schema" not in st.session_state:
        st.session_state.show_schema = False
    
    # Sidebar
    sidebar()
    
    # Main header
    st.markdown('<div class="main-header">🤖 NL2SQL Chat Demo</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Schema viewer
    if st.session_state.show_schema:
        with st.expander("🗄️ Database Schema", expanded=True):
            schema = get_schema()
            if schema:
                # Display tables
                for table_name, table_info in schema.get("tables", {}).items():
                    with st.container():
                        st.markdown(f"**📋 {table_name}**")
                        
                        columns_data = []
                        for col in table_info.get("columns", []):
                            columns_data.append({
                                "Column": col.get("name"),
                                "Type": col.get("type"),
                                "Nullable": "✅" if col.get("nullable") else "❌",
                                "Primary Key": "🔑" if col.get("primary_key") else ""
                            })
                        
                        if columns_data:
                            df_cols = pd.DataFrame(columns_data)
                            st.dataframe(df_cols, use_container_width=True, hide_index=True)
                        
                        st.markdown("---")
            
            if st.button("❌ Close Schema"):
                st.session_state.show_schema = False
                st.rerun()
    
    # Chat interface
    st.markdown("### 💬 Ask Questions About Your Database")
    
    # Display chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="message-user">👤 **You:** {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="message-assistant">🤖 **Assistant:**</div>', unsafe_allow_html=True)
            display_query_result(msg["content"])
    
    # Chat input
    user_input = st.chat_input("Type your question here... (e.g., 'How many users?')")
    
    # Handle example click
    if st.session_state.example_clicked:
        user_input = st.session_state.example_clicked
        st.session_state.example_clicked = None
    
    # Process input
    if user_input:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Show thinking
        with st.spinner("🤔 Thinking..."):
            # Call API
            auto_execute = st.session_state.get("auto_execute", True)
            response = send_chat_message(user_input, execute=auto_execute)
            
            if response:
                # Add assistant response
                st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Rerun to display new messages
        st.rerun()
    
    # Clear chat button
    if st.session_state.messages:
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🗑️ Clear Chat"):
                st.session_state.messages = []
                st.rerun()


if __name__ == "__main__":
    main()
