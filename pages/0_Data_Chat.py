"""
Data Chat - Natural Language SQL Query Interface
Streamlit page for querying the database using natural language.
"""
import streamlit as st
import pandas as pd
import json
import os
import re
import uuid
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from utils.langchain_sql import LangChainSQLAgent

# Load environment variables
load_dotenv()

# Logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Page configuration
st.set_page_config(
    page_title="Data Chat - SQL Query Interface",
    page_icon="💬",
    layout="wide"
)

# Title
st.title("💬 Data Chat - Natural Language SQL Query")
st.markdown("""
Ask questions about your database in natural language. The AI will generate SQL queries and return results as dataframes.
""")

# Sample questions (first 3 from test file, plus 3 more)
SAMPLE_QUESTIONS = [
    "how many tenders are there total",
    "show me the user count over time",
    "show me the tenders and cpv codes / sectors with highest value",
    "show me users grouped by country",
    "how many active subscriptions are there",
    "what are the most common tender categories"
]

# Initialize session state
if 'sql_agent' not in st.session_state:
    st.session_state.sql_agent = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'session_id' not in st.session_state:
    # Generate a unique session ID
    st.session_state.session_id = str(uuid.uuid4())


def get_sql_agent():
    """Get or create SQL agent instance."""
    try:
        # Create fresh instance - don't cache to avoid stale code
        return LangChainSQLAgent(verbose=False)
    except Exception as e:
        st.error(f"Failed to initialize SQL agent: {str(e)}")
        st.info("Please ensure EE_DB_URL and XAI_API_KEY are set in your .env file")
        return None


def save_to_log(session_id: str, question: str, df: pd.DataFrame, sql_query: str, result: dict):
    """
    Save query and results to log file.
    
    Args:
        session_id: Session ID
        question: User's question
        df: Result dataframe (can be None)
        sql_query: Generated SQL query (can be None)
        result: Full result dictionary
    """
    try:
        timestamp = datetime.now()
        
        # Handle None dataframe
        if df is None:
            row_count = 0
            has_dataframe = False
            dataframe_columns = []
            dataframe_records = []
        else:
            # Convert Timestamp and datetime objects to strings for JSON serialization
            df_copy = df.copy()
            for col in df_copy.columns:
                if df_copy[col].dtype == 'datetime64[ns]' or 'datetime' in str(df_copy[col].dtype):
                    df_copy[col] = df_copy[col].astype(str)
                elif df_copy[col].dtype == 'object':
                    # Check if column contains datetime objects
                    try:
                        df_copy[col] = df_copy[col].apply(lambda x: str(x) if hasattr(x, 'isoformat') else x)
                    except:
                        pass
            
            row_count = len(df)
            has_dataframe = not df.empty
            dataframe_columns = list(df.columns) if has_dataframe else []
            dataframe_records = df_copy.to_dict('records') if has_dataframe else []
        
        log_entry = {
            "session_id": session_id,
            "timestamp": timestamp.isoformat(),
            "question": question,
            "sql_query": sql_query,
            "row_count": row_count,
            "has_dataframe": has_dataframe,
            "dataframe_columns": dataframe_columns,
            "dataframe_records": dataframe_records,
            "answer": result.get('answer', '') if result else '',
            "error": result.get('error') if result else None
        }
        
        # Save to daily log file
        log_filename = f"chat_history_{timestamp.strftime('%Y%m%d')}.json"
        log_filepath = LOGS_DIR / log_filename
        
        # Read existing logs or create new list
        if log_filepath.exists():
            try:
                with open(log_filepath, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                logs = []
        else:
            logs = []
        
        # Append new log entry
        logs.append(log_entry)
        
        # Write back to file
        with open(log_filepath, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        # Don't fail the app if logging fails
        st.warning(f"⚠️ Failed to save log: {str(e)}")


def execute_query(question: str):
    """Execute a query and return results as dataframe."""
    if not st.session_state.sql_agent:
        st.error("SQL agent not initialized. Please check your environment variables.")
        error_df = pd.DataFrame({'Error': ['SQL agent not initialized']})
        return error_df, None, {'error': 'SQL agent not initialized'}
    
    with st.spinner("🤔 Thinking..."):
        try:
            # Use the new query_to_dataframe method
            if not hasattr(st.session_state.sql_agent, 'query_to_dataframe'):
                st.error("❌ Agent doesn't have query_to_dataframe method - please restart Streamlit")
                error_df = pd.DataFrame({'Error': ['Agent method missing - restart Streamlit']})
                return error_df, None, {'error': 'Agent method missing'}
            
            result = st.session_state.sql_agent.query_to_dataframe(question)
            
            # Get dataframe - query_to_dataframe ALWAYS returns a DataFrame
            df = result.get('dataframe')
            sql_query = result.get('sql_query')
            error = result.get('error')
            
            # Debug: Check what we got
            if df is None:
                # This shouldn't happen - query_to_dataframe always returns a DataFrame
                st.error("❌ Internal Error: DataFrame is None")
                df = pd.DataFrame({'Error': ['No results returned - DataFrame was None']})
            elif df.empty and error is None:
                # Empty result but no error - might be valid
                pass
            elif df.empty and error:
                # Error case - will be handled below
                pass
            
            # Ensure we have a dataframe (should always be the case now)
            if df is None:
                df = pd.DataFrame({'Error': ['No results returned']})
            
            # Note: Don't show success/error here - let the main code handle it
            # This ensures consistent messaging
            
            # Save to log (handle errors gracefully - don't break query execution)
            try:
                save_to_log(
                    st.session_state.session_id,
                    question,
                    df,
                    sql_query,
                    result
                )
            except Exception as log_error:
                # Don't fail the query if logging fails
                import traceback
                # Only show warning if it's not a serialization issue we can handle
                if 'not JSON serializable' not in str(log_error):
                    st.warning(f"⚠️ Failed to save log: {str(log_error)}")
            
            return df, sql_query, result
            
        except Exception as e:
            st.error(f"Query failed: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            # Return error DataFrame instead of None
            error_df = pd.DataFrame({'Error': [str(e)]})
            return error_df, None, {'error': str(e)}


# Initialize agent - always get fresh instance
# Clear cache if needed by restarting Streamlit
if st.session_state.sql_agent is None:
    with st.spinner("Initializing SQL agent..."):
        agent = get_sql_agent()
        if agent:
            st.session_state.sql_agent = agent
        else:
            st.error("Failed to initialize SQL agent. Please check your environment variables.")
            st.stop()

# Sidebar with session info
with st.sidebar:
    st.header("ℹ️ Session Info")
    st.caption(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
    st.caption(f"**Total Queries:** {len(st.session_state.chat_history)}")

# Main chat interface
st.divider()

# Sample questions buttons above chat input
st.subheader("📋 Sample Questions")
st.markdown("Click a question below to try it:")

# Display questions in a grid (3 columns, 2 rows)
for i in range(0, len(SAMPLE_QUESTIONS), 3):
    cols = st.columns(3)
    for j, col in enumerate(cols):
        idx = i + j
        if idx < len(SAMPLE_QUESTIONS):
            with col:
                if st.button(
                    SAMPLE_QUESTIONS[idx],
                    key=f"sample_{idx}",
                    use_container_width=True
                ):
                    st.session_state.current_question = SAMPLE_QUESTIONS[idx]
                    st.rerun()

st.divider()

# Chat input
question = st.text_input(
    "💬 Ask a question about your database:",
    value=st.session_state.get('current_question', ''),
    key="question_input",
    placeholder="e.g., How many users are there?"
)

# Clear button
col1, col2 = st.columns([1, 10])
with col1:
    if st.button("Clear", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.current_question = ""
        st.rerun()

# Process question
if question and question.strip():
    # Add to chat history
    st.session_state.chat_history.append({
        "question": question,
        "timestamp": pd.Timestamp.now()
    })
    
    # Execute query
    df, sql_query, result = execute_query(question)
    
    # Display results - df should always be present now (query_to_dataframe always returns a DataFrame)
    if df is not None:
        # Check if this is an error DataFrame
        is_error = 'Error' in df.columns and len(df) > 0
        
        # Show success/error message
        if is_error:
            error_msg = df.iloc[0]['Error'] if len(df) > 0 else 'Unknown error'
            st.error(f"❌ Error: {error_msg}")
        else:
            st.success("✅ Query executed successfully!")
        
        # Display dataframe
        st.subheader("📊 Results")
        st.dataframe(df, use_container_width=True)
        
        # Show row count
        st.caption(f"📈 {len(df)} rows returned")
        
        # Download button (only if not error)
        if not is_error:
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name=f"query_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        # SQL query expander - ALWAYS show SQL if available
        with st.expander("🔍 View Generated SQL Query", expanded=False):
            if sql_query:
                st.code(sql_query, language="sql")
                st.caption("💡 Copy this SQL query to use in your SQL client")
            else:
                st.warning("⚠️ SQL query could not be extracted from the agent response.")
                # Try to extract from result
                if result:
                    # Check if SQL is in the result dict
                    if isinstance(result, dict):
                        # Try to get SQL from nested result
                        nested_result = result.get('result', {})
                        if isinstance(nested_result, dict):
                            output = nested_result.get('output', '')
                            if output:
                                # Try to find SQL in output
                                import re
                                sql_patterns = [
                                    r'(SELECT[\s\S]*?)(?:;|\n\n|\Z)',  # SELECT statement
                                    r'```sql\s*(SELECT[\s\S]*?)\s*```',  # Markdown SQL
                                ]
                                for pattern in sql_patterns:
                                    sql_match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
                                    if sql_match:
                                        extracted_sql = sql_match.group(1).strip()
                                        st.code(extracted_sql, language="sql")
                                        st.caption("💡 SQL extracted from response")
                                        break
                                else:
                                    st.json(nested_result)
                            else:
                                st.json(nested_result)
                    else:
                        st.json(result)
        
        # Add result to chat history
        st.session_state.chat_history[-1]['result'] = {
            'dataframe': df.to_dict('records'),
            'sql_query': sql_query,
            'row_count': len(df)
        }
    else:
        st.warning("⚠️ Could not generate results. Check the error messages above.")
    
    # Clear current question
    st.session_state.current_question = ""

# Chat history
if st.session_state.chat_history:
    st.divider()
    st.subheader("📜 Chat History")
    
    for i, chat in enumerate(reversed(st.session_state.chat_history[-10:])):  # Show last 10
        with st.expander(f"❓ {chat['question']}", expanded=False):
            if 'result' in chat:
                result_data = chat['result']
                if result_data.get('dataframe'):
                    st.dataframe(pd.DataFrame(result_data['dataframe']), use_container_width=True)
                    st.caption(f"📈 {result_data.get('row_count', 0)} rows")
                
                if result_data.get('sql_query'):
                    st.code(result_data['sql_query'], language="sql")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>💬 Data Chat - Powered by LangChain and XAI (Grok)</p>
    <p>Ask questions in natural language and get instant SQL results</p>
</div>
""", unsafe_allow_html=True)

