"""
Chat History - View and explore chat history from logs
Streamlit page for viewing saved chat history grouped by session.
"""
import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Page configuration
st.set_page_config(
    page_title="Chat History - View Past Queries",
    page_icon="📜",
    layout="wide"
)

# Logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"

# Title
st.title("📜 Chat History")
st.markdown("""
View and explore chat history from saved log files. Browse queries by session or date.
""")

# Initialize session state
if 'selected_session' not in st.session_state:
    st.session_state.selected_session = None
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = None


def load_log_files():
    """Load all log files from the logs directory."""
    log_files = sorted(LOGS_DIR.glob("chat_history_*.json"), reverse=True)
    return log_files


def load_logs_from_file(log_filepath: Path):
    """Load logs from a specific file."""
    try:
        with open(log_filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        st.error(f"Error reading log file {log_filepath.name}: {str(e)}")
        return []


def get_all_logs():
    """Load all logs from all log files."""
    log_files = load_log_files()
    all_logs = []
    
    for log_file in log_files:
        logs = load_logs_from_file(log_file)
        all_logs.extend(logs)
    
    return all_logs


def group_logs_by_session(logs):
    """Group logs by session ID."""
    sessions = defaultdict(list)
    for log in logs:
        session_id = log.get('session_id', 'unknown')
        sessions[session_id].append(log)
    
    # Sort each session's logs by timestamp
    for session_id in sessions:
        sessions[session_id].sort(key=lambda x: x.get('timestamp', ''))
    
    return dict(sessions)


def group_logs_by_date(logs):
    """Group logs by date."""
    dates = defaultdict(list)
    for log in logs:
        timestamp = log.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
                dates[date_str].append(log)
            except:
                pass
    
    # Sort each date's logs by timestamp
    for date_str in dates:
        dates[date_str].sort(key=lambda x: x.get('timestamp', ''))
    
    return dict(dates)


# Load all logs
all_logs = get_all_logs()

if not all_logs:
    st.info("📭 No chat history found. Start asking questions in the Data Chat page to create history.")
else:
    st.success(f"📊 Found {len(all_logs)} total queries across all sessions")
    
    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Filters")
        
        # Group by session
        sessions = group_logs_by_session(all_logs)
        session_options = ["All Sessions"] + list(sessions.keys())
        
        selected_session = st.selectbox(
            "Filter by Session",
            session_options,
            index=0,
            key="session_filter"
        )
        
        # Group by date
        dates = group_logs_by_date(all_logs)
        date_options = ["All Dates"] + sorted(dates.keys(), reverse=True)
        
        selected_date = st.selectbox(
            "Filter by Date",
            date_options,
            index=0,
            key="date_filter"
        )
        
        st.divider()
        st.metric("Total Sessions", len(sessions))
        st.metric("Total Dates", len(dates))
    
    # Filter logs based on selections
    filtered_logs = all_logs
    
    if selected_session != "All Sessions":
        filtered_logs = [log for log in filtered_logs if log.get('session_id') == selected_session]
    
    if selected_date != "All Dates":
        filtered_logs = [
            log for log in filtered_logs
            if log.get('timestamp', '').startswith(selected_date)
        ]
    
    # Sort by timestamp (newest first)
    filtered_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    st.divider()
    st.subheader(f"📋 Showing {len(filtered_logs)} queries")
    
    if not filtered_logs:
        st.info("No queries match the selected filters.")
    else:
        # Display logs grouped by session
        if selected_session == "All Sessions":
            # Group filtered logs by session
            filtered_sessions = group_logs_by_session(filtered_logs)
            
            for session_id, session_logs in sorted(filtered_sessions.items(), key=lambda x: x[1][0].get('timestamp', ''), reverse=True):
                # Get first timestamp for session
                first_timestamp = session_logs[0].get('timestamp', '')
                try:
                    dt = datetime.fromisoformat(first_timestamp.replace('Z', '+00:00'))
                    session_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    session_date = first_timestamp
                
                with st.expander(
                    f"🔹 Session: {session_id[:8]}... ({len(session_logs)} queries) - Started: {session_date}",
                    expanded=False
                ):
                    for i, log in enumerate(session_logs):
                        timestamp = log.get('timestamp', '')
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            display_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            display_time = timestamp
                        
                        st.markdown(f"**Query {i+1}:** {log.get('question', 'N/A')}")
                        st.caption(f"⏰ {display_time}")
                        
                        # Show SQL query
                        sql_query = log.get('sql_query')
                        if sql_query:
                            with st.expander("🔍 View SQL Query", expanded=False):
                                st.code(sql_query, language="sql")
                        
                        # Show results
                        if log.get('has_dataframe') and log.get('dataframe_records'):
                            df = pd.DataFrame(log.get('dataframe_records', []))
                            st.dataframe(df, use_container_width=True)
                            st.caption(f"📈 {log.get('row_count', 0)} rows returned")
                        elif log.get('answer'):
                            st.info(log.get('answer'))
                        
                        if log.get('error'):
                            st.error(f"❌ Error: {log.get('error')}")
                        
                        if i < len(session_logs) - 1:
                            st.divider()
        else:
            # Show single session
            session_logs = filtered_logs
            
            st.subheader(f"Session: {selected_session[:8]}...")
            
            for i, log in enumerate(session_logs):
                timestamp = log.get('timestamp', '')
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    display_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    display_time = timestamp
                
                with st.expander(
                    f"❓ Query {i+1}: {log.get('question', 'N/A')[:50]}... - {display_time}",
                    expanded=False
                ):
                    st.caption(f"⏰ {display_time}")
                    
                    # Show SQL query
                    sql_query = log.get('sql_query')
                    if sql_query:
                        with st.expander("🔍 View SQL Query", expanded=False):
                            st.code(sql_query, language="sql")
                    
                    # Show results
                    if log.get('has_dataframe') and log.get('dataframe_records'):
                        df = pd.DataFrame(log.get('dataframe_records', []))
                        st.dataframe(df, use_container_width=True)
                        st.caption(f"📈 {log.get('row_count', 0)} rows returned")
                        
                        # Download button
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Results as CSV",
                            data=csv,
                            file_name=f"query_{i+1}_{selected_session[:8]}_{display_time.replace(':', '-')}.csv",
                            mime="text/csv",
                            key=f"download_{i}_{selected_session}"
                        )
                    elif log.get('answer'):
                        st.info(log.get('answer'))
                    
                    if log.get('error'):
                        st.error(f"❌ Error: {log.get('error')}")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>📜 Chat History - Browse past queries and results</p>
    <p>Logs are saved automatically when queries are executed</p>
</div>
""", unsafe_allow_html=True)

