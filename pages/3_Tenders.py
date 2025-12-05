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
from datetime import date, timedelta

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

# Get weekly new tenders data with filters
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_weekly_new_tenders(start_date=None, end_date=None, cpv_id=None, cpv_name=None):
    """
    Get weekly new tenders data with optional filters.
    
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
            DATE_TRUNC('week', created_at)::date as week_start,
            COUNT(*) as new_tenders,
            main_cpv_id,
            main_cpv_name
        FROM estonian_tenders
        WHERE {where_clause}
        GROUP BY DATE_TRUNC('week', created_at), main_cpv_id, main_cpv_name
        ORDER BY week_start, main_cpv_name
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    return df


# Get weekly tender amounts (EUR) with filters
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_weekly_tender_amounts(start_date=None, end_date=None, cpv_id=None, cpv_name=None):
    """
    Get weekly tender amounts in EUR with optional filters.
    Joins estonian_tenders with estonian_tender_details to get estimated_cost.
    Filters out NULL amounts.
    """
    engine = get_db_engine()
    
    # Build WHERE clause
    where_conditions = [
        "t.created_at IS NOT NULL",
        "d.estimated_cost IS NOT NULL"
    ]
    
    if start_date:
        where_conditions.append(f"DATE(t.created_at) >= '{start_date}'")
    
    if end_date:
        where_conditions.append(f"DATE(t.created_at) <= '{end_date}'")
    
    if cpv_id:
        where_conditions.append(f"t.main_cpv_id = {cpv_id}")
    
    if cpv_name:
        where_conditions.append(f"t.main_cpv_name ILIKE '%{cpv_name}%'")
    
    where_clause = " AND ".join(where_conditions)
    
    query = text(f"""
        SELECT 
            DATE_TRUNC('week', t.created_at)::date as week_start,
            SUM(d.estimated_cost) as total_amount_eur,
            COUNT(*) as tender_count
        FROM estonian_tenders t
        JOIN estonian_tender_details d ON t.procurement_id = d.procurement_id
        WHERE {where_clause}
        GROUP BY DATE_TRUNC('week', t.created_at)
        ORDER BY week_start
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
        
        # Date range filter (default to past 2 months)
        st.subheader("Date Range")
        default_start = date.today() - timedelta(days=60)
        
        date_col1, date_col2 = st.columns(2)
        
        with date_col1:
            start_date = st.date_input("Start Date", value=default_start)
        
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
        tenders_df = get_weekly_new_tenders(
            start_date=start_date,
            end_date=end_date,
            cpv_id=cpv_id,
            cpv_name=cpv_name
        )
        
        amounts_df = get_weekly_tender_amounts(
            start_date=start_date,
            end_date=end_date,
            cpv_id=cpv_id,
            cpv_name=cpv_name
        )
    
    if tenders_df.empty:
        st.warning("⚠️ No tenders data found for the selected filters")
        st.stop()
    
    # Convert date column to datetime
    tenders_df['week_start'] = pd.to_datetime(tenders_df['week_start'])
    
    # Aggregate weekly new tenders (sum across CPV codes if multiple selected)
    weekly_tenders = tenders_df.groupby('week_start')['new_tenders'].sum().reset_index()
    weekly_tenders.columns = ['week_start', 'new_tenders']
    
    # Display summary stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_tenders = weekly_tenders['new_tenders'].sum()
        st.metric("Total New Tenders", f"{total_tenders:,}")
    
    with col2:
        total_new_this_week = weekly_tenders['new_tenders'].iloc[-1] if not weekly_tenders.empty else 0
        st.metric("New Tenders This Week", f"{total_new_this_week:,}")
    
    with col3:
        avg_weekly = weekly_tenders['new_tenders'].mean() if not weekly_tenders.empty else 0
        st.metric("Avg Weekly New Tenders", f"{avg_weekly:.1f}")
    
    with col4:
        max_weekly = weekly_tenders['new_tenders'].max() if not weekly_tenders.empty else 0
        st.metric("Max Weekly New Tenders", f"{max_weekly:,}")
    
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
    
    # Chart: Weekly New Tenders (Bar Chart)
    st.subheader("📊 Weekly New Tenders")
    
    fig_weekly = go.Figure()
    fig_weekly.add_trace(go.Bar(
        x=weekly_tenders['week_start'],
        y=weekly_tenders['new_tenders'],
        name='Weekly New Tenders',
        marker_color='#d62728'
    ))
    
    fig_weekly.update_layout(
        title="Weekly New Tenders",
        xaxis_title="Week Starting",
        yaxis_title="New Tenders",
        hovermode='x unified',
        height=400,
        template='plotly_white',
        bargap=0.2
    )
    
    st.plotly_chart(fig_weekly, use_container_width=True)
    
    # Chart 2: Weekly Tender Amounts in EUR (Bar Chart)
    st.divider()
    st.subheader("💶 Weekly Tender Amounts (EUR)")
    st.caption(f"Debug: amounts_df has {len(amounts_df)} rows")
    
    if not amounts_df.empty:
        amounts_df['week_start'] = pd.to_datetime(amounts_df['week_start'])
        
        fig_amounts = go.Figure()
        fig_amounts.add_trace(go.Bar(
            x=amounts_df['week_start'],
            y=amounts_df['total_amount_eur'],
            name='Weekly Amount (EUR)',
            marker_color='#2ca02c',
            hovertemplate='Week: %{x}<br>Amount: €%{y:,.0f}<extra></extra>'
        ))
        
        fig_amounts.update_layout(
            title="Weekly Tender Amounts (EUR)",
            xaxis_title="Week Starting",
            yaxis_title="Total Amount (EUR)",
            hovermode='x unified',
            height=400,
            template='plotly_white',
            bargap=0.2,
            yaxis_tickformat=',.0f'
        )
        
        st.plotly_chart(fig_amounts, use_container_width=True)
        
        # Show summary stats for amounts
        col1, col2, col3 = st.columns(3)
        with col1:
            total_amount = amounts_df['total_amount_eur'].sum()
            st.metric("Total Amount (EUR)", f"€{total_amount:,.0f}")
        with col2:
            avg_weekly_amount = amounts_df['total_amount_eur'].mean()
            st.metric("Avg Weekly Amount", f"€{avg_weekly_amount:,.0f}")
        with col3:
            tenders_with_amounts = amounts_df['tender_count'].sum()
            st.metric("Tenders with Amounts", f"{tenders_with_amounts:,}")
    else:
        st.info("ℹ️ No tender amount data available for the selected filters")
    
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
        st.write("**Weekly New Tenders Data**")
        st.dataframe(weekly_tenders, use_container_width=True)
        
        if not amounts_df.empty:
            st.write("**Weekly Tender Amounts (EUR)**")
            st.dataframe(amounts_df, use_container_width=True)
        
        if not cpv_id:
            st.write("**Tenders by CPV Code**")
            st.dataframe(tenders_df, use_container_width=True)
    
except Exception as e:
    st.error(f"❌ Error loading tenders data: {str(e)}")
    import traceback
    with st.expander("🔍 Error Details"):
        st.code(traceback.format_exc())

