"""
Tenders Analytics - New Tenders Charts with CPV/Sector Filtering
Streamlit page displaying new tenders charts with filtering options.
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
    page_title="Tenders Analytics",
    page_icon="📋",
    layout="wide"
)

# Title
st.title("📋 Tenders Analytics")
st.markdown("New tenders metrics with CPV code and sector filtering")

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

# Get unique CPV codes
@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_cpv_codes():
    """Get unique CPV codes and names."""
    engine = get_db_engine()
    query = text("""
        SELECT DISTINCT 
            main_cpv_id,
            main_cpv_name
        FROM estonian_tenders
        WHERE main_cpv_id IS NOT NULL 
          AND main_cpv_name IS NOT NULL
        ORDER BY main_cpv_name
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    return df

# Get new tenders data with filters
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_new_tenders(start_date=None, end_date=None, cpv_id=None, cpv_name=None):
    """
    Get new tenders data with optional filters.
    
    Args:
        start_date: Start date filter (datetime or None)
        end_date: End date filter (datetime or None)
        cpv_id: CPV ID filter (int or None)
        cpv_name: CPV name filter (str or None)
    """
    engine = get_db_engine()
    
    # Build WHERE clause
    where_conditions = ["created_at IS NOT NULL"]
    
    if start_date:
        where_conditions.append(f"DATE(created_at) >= '{start_date}'")
    
    if end_date:
        where_conditions.append(f"DATE(created_at) <= '{end_date}'")
    
    if cpv_id:
        where_conditions.append(f"main_cpv_id = {cpv_id}")
    
    if cpv_name:
        where_conditions.append(f"main_cpv_name ILIKE '%{cpv_name}%'")
    
    where_clause = " AND ".join(where_conditions)
    
    query = text(f"""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as new_tenders,
            main_cpv_id,
            main_cpv_name
        FROM estonian_tenders
        WHERE {where_clause}
        GROUP BY DATE(created_at), main_cpv_id, main_cpv_name
        ORDER BY date, main_cpv_name
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    return df

# Get cumulative new tenders
@st.cache_data(ttl=300)
def get_cumulative_tenders(start_date=None, end_date=None, cpv_id=None, cpv_name=None):
    """Get cumulative new tenders count."""
    engine = get_db_engine()
    
    where_conditions = ["created_at IS NOT NULL"]
    
    if start_date:
        where_conditions.append(f"DATE(created_at) >= '{start_date}'")
    
    if end_date:
        where_conditions.append(f"DATE(created_at) <= '{end_date}'")
    
    if cpv_id:
        where_conditions.append(f"main_cpv_id = {cpv_id}")
    
    if cpv_name:
        where_conditions.append(f"main_cpv_name ILIKE '%{cpv_name}%'")
    
    where_clause = " AND ".join(where_conditions)
    
    query = text(f"""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) OVER (ORDER BY DATE(created_at)) as cumulative_tenders
        FROM estonian_tenders
        WHERE {where_clause}
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    return df

# Main content
try:
    engine = get_db_engine()
    schema = load_schema()
    
    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Filters")
        
        # Date range filter
        st.subheader("Date Range")
        date_col1, date_col2 = st.columns(2)
        
        with date_col1:
            start_date = st.date_input("Start Date", value=None)
        
        with date_col2:
            end_date = st.date_input("End Date", value=None)
        
        # CPV filter
        st.subheader("CPV Code / Sector")
        
        # Get CPV codes
        with st.spinner("Loading CPV codes..."):
            cpv_df = get_cpv_codes()
        
        if not cpv_df.empty:
            # CPV selection
            cpv_options = ["All"] + [f"{row['main_cpv_id']} - {row['main_cpv_name']}" 
                                     for _, row in cpv_df.iterrows()]
            
            selected_cpv = st.selectbox(
                "Select CPV Code",
                options=cpv_options,
                index=0
            )
            
            if selected_cpv != "All":
                cpv_id = int(selected_cpv.split(" - ")[0])
                cpv_name = selected_cpv.split(" - ", 1)[1]
            else:
                cpv_id = None
                cpv_name = None
        else:
            cpv_id = None
            cpv_name = None
            st.warning("No CPV codes found")
        
        # Clear filters button
        if st.button("🔄 Clear All Filters"):
            st.rerun()
    
    # Get data with filters
    with st.spinner("Loading tenders data..."):
        tenders_df = get_new_tenders(
            start_date=start_date,
            end_date=end_date,
            cpv_id=cpv_id,
            cpv_name=cpv_name
        )
        
        cumulative_df = get_cumulative_tenders(
            start_date=start_date,
            end_date=end_date,
            cpv_id=cpv_id,
            cpv_name=cpv_name
        )
    
    if tenders_df.empty or cumulative_df.empty:
        st.warning("⚠️ No tenders data found for the selected filters")
        st.stop()
    
    # Convert date column to datetime
    tenders_df['date'] = pd.to_datetime(tenders_df['date'])
    cumulative_df['date'] = pd.to_datetime(cumulative_df['date'])
    
    # Aggregate daily new tenders (sum across CPV codes if multiple selected)
    daily_tenders = tenders_df.groupby('date')['new_tenders'].sum().reset_index()
    daily_tenders.columns = ['date', 'new_tenders']
    
    # Display summary stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_tenders = cumulative_df['cumulative_tenders'].iloc[-1] if not cumulative_df.empty else 0
        st.metric("Total New Tenders", f"{total_tenders:,}")
    
    with col2:
        total_new_today = daily_tenders['new_tenders'].iloc[-1] if not daily_tenders.empty else 0
        st.metric("New Tenders Today", f"{total_new_today:,}")
    
    with col3:
        avg_daily = daily_tenders['new_tenders'].mean() if not daily_tenders.empty else 0
        st.metric("Avg Daily New Tenders", f"{avg_daily:.1f}")
    
    with col4:
        max_daily = daily_tenders['new_tenders'].max() if not daily_tenders.empty else 0
        st.metric("Max Daily New Tenders", f"{max_daily:,}")
    
    # Show active filters
    if start_date or end_date or cpv_id:
        filter_info = []
        if start_date:
            filter_info.append(f"Start: {start_date}")
        if end_date:
            filter_info.append(f"End: {end_date}")
        if cpv_id:
            filter_info.append(f"CPV: {cpv_id} - {cpv_name}")
        
        st.info(f"🔍 Active Filters: {', '.join(filter_info)}")
    
    st.divider()
    
    # Chart 1: Cumulative New Tenders Over Time
    st.subheader("📈 Cumulative New Tenders Over Time")
    
    fig_cumulative = go.Figure()
    fig_cumulative.add_trace(go.Scatter(
        x=cumulative_df['date'],
        y=cumulative_df['cumulative_tenders'],
        mode='lines',
        fill='tozeroy',
        name='Cumulative New Tenders',
        line=dict(color='#ff7f0e', width=2),
        fillcolor='rgba(255, 127, 14, 0.3)'
    ))
    
    fig_cumulative.update_layout(
        title="Cumulative New Tenders Growth",
        xaxis_title="Date",
        yaxis_title="Cumulative New Tenders",
        hovermode='x unified',
        height=400,
        template='plotly_white'
    )
    
    st.plotly_chart(fig_cumulative, use_container_width=True)
    
    st.divider()
    
    # Chart 2: Daily New Tenders
    st.subheader("📊 Daily New Tenders (Incremental)")
    
    fig_daily = go.Figure()
    fig_daily.add_trace(go.Scatter(
        x=daily_tenders['date'],
        y=daily_tenders['new_tenders'],
        mode='lines',
        fill='tozeroy',
        name='Daily New Tenders',
        line=dict(color='#d62728', width=2),
        fillcolor='rgba(214, 39, 40, 0.3)'
    ))
    
    fig_daily.update_layout(
        title="Daily New Tenders",
        xaxis_title="Date",
        yaxis_title="New Tenders",
        hovermode='x unified',
        height=400,
        template='plotly_white'
    )
    
    st.plotly_chart(fig_daily, use_container_width=True)
    
    # Chart 3: New Tenders by CPV Code (if no CPV filter applied)
    if not cpv_id:
        st.divider()
        st.subheader("📊 New Tenders by CPV Code / Sector")
        
        # Aggregate by CPV
        cpv_summary = tenders_df.groupby(['main_cpv_id', 'main_cpv_name'])['new_tenders'].sum().reset_index()
        cpv_summary = cpv_summary.sort_values('new_tenders', ascending=False).head(20)  # Top 20
        
        fig_cpv = px.bar(
            cpv_summary,
            x='new_tenders',
            y='main_cpv_name',
            orientation='h',
            title="Top 20 CPV Codes by New Tenders Count",
            labels={'new_tenders': 'Total New Tenders', 'main_cpv_name': 'CPV Code / Sector'},
            color='new_tenders',
            color_continuous_scale='Reds'
        )
        
        fig_cpv.update_layout(
            height=600,
            yaxis={'categoryorder': 'total ascending'},
            template='plotly_white'
        )
        
        st.plotly_chart(fig_cpv, use_container_width=True)
    
    # Data tables (collapsible)
    with st.expander("📋 View Raw Data"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Cumulative Tenders Data**")
            st.dataframe(cumulative_df, use_container_width=True)
        
        with col2:
            st.write("**Daily New Tenders Data**")
            st.dataframe(daily_tenders, use_container_width=True)
        
        if not cpv_id:
            st.write("**Tenders by CPV Code**")
            st.dataframe(tenders_df, use_container_width=True)
    
except Exception as e:
    st.error(f"❌ Error loading tenders data: {str(e)}")
    import traceback
    with st.expander("🔍 Error Details"):
        st.code(traceback.format_exc())

