"""
Users Analytics - User Growth Charts
Streamlit page displaying cumulative and daily new user charts.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from pathlib import Path
import json

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Users Analytics",
    page_icon="👥",
    layout="wide"
)

# Title
st.title("👥 Users Analytics")
st.markdown("User growth metrics over time")

# Database connection
@st.cache_resource
def get_db_engine():
    """Get database engine connection."""
    db_url = os.getenv('EE_DB_URL')
    if not db_url:
        st.error("❌ EE_DB_URL not found in environment variables")
        st.stop()
    return create_engine(db_url)

# Load schema
@st.cache_data
def load_schema():
    """Load database schema from JSON."""
    schema_path = Path(__file__).parent.parent / "sql" / "schema.json"
    if not schema_path.exists():
        st.error(f"❌ Schema file not found: {schema_path}")
        st.stop()
    with open(schema_path, 'r') as f:
        return json.load(f)

# Get cumulative users over time (monthly)
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cumulative_users():
    """Get cumulative user count over time by month."""
    engine = get_db_engine()
    query = text("""
        SELECT 
            DATE_TRUNC('month', created_at) AS month,
            COUNT(*) AS new_users,
            SUM(COUNT(*)) OVER (ORDER BY DATE_TRUNC('month', created_at)) AS cumulative_users
        FROM users
        WHERE created_at IS NOT NULL
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    return df

# Get weekly new users
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_weekly_new_users():
    """Get weekly new user registrations."""
    engine = get_db_engine()
    query = text("""
        SELECT 
            DATE_TRUNC('week', created_at)::date as week_start,
            COUNT(*) as new_users
        FROM users
        WHERE created_at IS NOT NULL
        GROUP BY DATE_TRUNC('week', created_at)
        ORDER BY week_start
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    return df

# Main content
try:
    engine = get_db_engine()
    schema = load_schema()
    
    # Get data
    with st.spinner("Loading user data..."):
        cumulative_df = get_cumulative_users()
        weekly_df = get_weekly_new_users()
    
    if cumulative_df.empty or weekly_df.empty:
        st.warning("⚠️ No user data found")
        st.stop()
    
    # Convert date columns to datetime
    cumulative_df['month'] = pd.to_datetime(cumulative_df['month'])
    weekly_df['week_start'] = pd.to_datetime(weekly_df['week_start'])
    
    # Display summary stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_users = cumulative_df['cumulative_users'].iloc[-1] if not cumulative_df.empty else 0
        st.metric("Total Users", f"{total_users:,}")
    
    with col2:
        total_new_this_week = weekly_df['new_users'].iloc[-1] if not weekly_df.empty else 0
        st.metric("New Users This Week", f"{total_new_this_week:,}")
    
    with col3:
        avg_weekly = weekly_df['new_users'].mean() if not weekly_df.empty else 0
        st.metric("Avg Weekly New Users", f"{avg_weekly:.1f}")
    
    with col4:
        max_weekly = weekly_df['new_users'].max() if not weekly_df.empty else 0
        st.metric("Max Weekly New Users", f"{max_weekly:,}")
    
    st.divider()
    
    # Chart 1: Cumulative Users Over Time (Monthly)
    st.subheader("📈 Cumulative Users Over Time")
    
    fig_cumulative = go.Figure()
    fig_cumulative.add_trace(go.Scatter(
        x=cumulative_df['month'],
        y=cumulative_df['cumulative_users'],
        mode='lines+markers',
        fill='tozeroy',
        name='Cumulative Users',
        line=dict(color='#1f77b4', width=2),
        fillcolor='rgba(31, 119, 180, 0.3)'
    ))
    
    fig_cumulative.update_layout(
        title="Cumulative User Growth (Monthly)",
        xaxis_title="Month",
        yaxis_title="Cumulative Users",
        hovermode='x unified',
        height=400,
        template='plotly_white'
    )
    
    st.plotly_chart(fig_cumulative, use_container_width=True)
    
    st.divider()
    
    # Chart 2: Weekly New Users (Bar Chart)
    st.subheader("📊 Weekly New Users")
    
    fig_weekly = go.Figure()
    fig_weekly.add_trace(go.Bar(
        x=weekly_df['week_start'],
        y=weekly_df['new_users'],
        name='Weekly New Users',
        marker_color='#2ca02c'
    ))
    
    fig_weekly.update_layout(
        title="Weekly New User Registrations",
        xaxis_title="Week Starting",
        yaxis_title="New Users",
        hovermode='x unified',
        height=400,
        template='plotly_white',
        bargap=0.2
    )
    
    st.plotly_chart(fig_weekly, use_container_width=True)
    
    # Data tables (collapsible)
    with st.expander("📋 View Raw Data"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Cumulative Users Data**")
            st.dataframe(cumulative_df, use_container_width=True)
        
        with col2:
            st.write("**Weekly New Users Data**")
            st.dataframe(weekly_df, use_container_width=True)
    
except Exception as e:
    st.error(f"❌ Error loading user data: {str(e)}")
    import traceback
    with st.expander("🔍 Error Details"):
        st.code(traceback.format_exc())

