"""
Tendly Social - Automated Social Media Posting Agent
Streamlit application for posting tender summaries to social media.
"""
import streamlit as st
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from utils.summarizer import TenderSummarizer
from utils.social_poster import ArcadeSocialPoster

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Tendly Social - Automated Posting Agent",
    page_icon="📢",
    layout="wide"
)

# Title and description
st.title("📢 Tendly Social - Automated Posting Agent")
st.markdown("""
This application helps you automatically generate and post tender summaries to social media platforms 
(Twitter/X and LinkedIn) using AI-powered content generation and Arcade AI for posting.
""")

# Initialize session state
if 'posted_tenders' not in st.session_state:
    st.session_state.posted_tenders = []

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

# API Key status
st.sidebar.subheader("API Keys Status")
xai_key = os.getenv('XAI_API_KEY')
arcade_key = os.getenv('ARCADE_API_KEY')

st.sidebar.write(f"XAI API Key: {'✅ Configured' if xai_key else '❌ Missing'}")
st.sidebar.write(f"Arcade API Key: {'✅ Configured' if arcade_key else '❌ Missing'}")

# Platform selection
st.sidebar.subheader("Posting Platforms")
post_to_twitter = st.sidebar.checkbox("Post to Twitter/X", value=True)
post_to_linkedin = st.sidebar.checkbox("Post to LinkedIn", value=True)

# LinkedIn page configuration
linkedin_page = st.sidebar.text_input(
    "LinkedIn Page URL",
    value=os.getenv('LINKEDIN_PAGE', 'https://www.linkedin.com/company/tendly-eu/'),
    help="Company page URL for LinkedIn posting"
)

# Main content area
tab1, tab2, tab3 = st.tabs(["📋 Select Tender", "✍️ Generate Content", "📤 Post to Social Media"])

# Tab 1: Select Tender
with tab1:
    st.header("Select a Tender to Post")
    
    # Load sample tenders
    tenders_file = Path(__file__).parent / "sample_tenders.json"
    
    if tenders_file.exists():
        with open(tenders_file, 'r') as f:
            tenders = json.load(f)
        
        # Display tenders in a grid
        for i, tender in enumerate(tenders):
            with st.expander(f"🔖 {tender['title']}", expanded=(i == 0)):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Organization:** {tender['organization']}")
                    st.write(f"**Category:** {tender['category']}")
                    st.write(f"**Description:** {tender['description']}")
                
                with col2:
                    st.write(f"**Budget:** {tender['budget']}")
                    st.write(f"**Deadline:** {tender['deadline']}")
                    st.write(f"**CPV Codes:** {', '.join(tender.get('cpv_codes', []))}")
                
                if st.button(f"Select This Tender", key=f"select_{tender['id']}"):
                    st.session_state.selected_tender = tender
                    st.success(f"✅ Selected: {tender['title']}")
                    st.rerun()
    else:
        st.error("Sample tenders file not found!")

# Tab 2: Generate Content
with tab2:
    st.header("Generate Social Media Content")
    
    if 'selected_tender' in st.session_state:
        tender = st.session_state.selected_tender
        
        st.info(f"**Selected Tender:** {tender['title']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🐦 Twitter/X Content")
            if st.button("Generate Twitter Summary", key="gen_twitter"):
                with st.spinner("Generating Twitter content..."):
                    try:
                        summarizer = TenderSummarizer()
                        twitter_summary = summarizer.summarize_for_twitter(tender)
                        hashtags = summarizer.create_hashtags(tender)
                        
                        # Combine summary with hashtags
                        full_twitter = f"{twitter_summary}\n\n{' '.join(hashtags[:3])}"
                        
                        st.session_state.twitter_content = full_twitter
                        st.success("✅ Twitter content generated!")
                    except Exception as e:
                        st.error(f"Error generating Twitter content: {str(e)}")
            
            if 'twitter_content' in st.session_state:
                twitter_content = st.text_area(
                    "Twitter Post (280 chars max)",
                    value=st.session_state.twitter_content,
                    height=150,
                    max_chars=280,
                    key="twitter_edit"
                )
                st.session_state.twitter_content = twitter_content
                st.write(f"Character count: {len(twitter_content)}/280")
        
        with col2:
            st.subheader("💼 LinkedIn Content")
            if st.button("Generate LinkedIn Summary", key="gen_linkedin"):
                with st.spinner("Generating LinkedIn content..."):
                    try:
                        summarizer = TenderSummarizer()
                        linkedin_summary = summarizer.summarize_for_linkedin(tender)
                        hashtags = summarizer.create_hashtags(tender)
                        
                        # Combine summary with hashtags
                        full_linkedin = f"{linkedin_summary}\n\n{' '.join(hashtags)}"
                        
                        st.session_state.linkedin_content = full_linkedin
                        st.success("✅ LinkedIn content generated!")
                    except Exception as e:
                        st.error(f"Error generating LinkedIn content: {str(e)}")
            
            if 'linkedin_content' in st.session_state:
                linkedin_content = st.text_area(
                    "LinkedIn Post",
                    value=st.session_state.linkedin_content,
                    height=250,
                    key="linkedin_edit"
                )
                st.session_state.linkedin_content = linkedin_content
                st.write(f"Character count: {len(linkedin_content)}")
        
        # Add tender URL
        st.subheader("🔗 Tender URL")
        tender_url = st.text_input(
            "Tender URL (optional)",
            value=tender.get('url', ''),
            key="tender_url"
        )
        
    else:
        st.warning("⚠️ Please select a tender from the first tab.")

# Tab 3: Post to Social Media
with tab3:
    st.header("Post to Social Media")
    
    if 'selected_tender' in st.session_state and \
       ('twitter_content' in st.session_state or 'linkedin_content' in st.session_state):
        
        tender = st.session_state.selected_tender
        
        st.info(f"**Ready to post:** {tender['title']}")
        
        # Preview section
        col1, col2 = st.columns(2)
        
        with col1:
            if post_to_twitter and 'twitter_content' in st.session_state:
                st.subheader("🐦 Twitter Preview")
                st.markdown(f"```\n{st.session_state.twitter_content}\n```")
                if tender.get('url'):
                    st.write(f"🔗 {tender.get('url')}")
        
        with col2:
            if post_to_linkedin and 'linkedin_content' in st.session_state:
                st.subheader("💼 LinkedIn Preview")
                st.markdown(f"```\n{st.session_state.linkedin_content}\n```")
                if tender.get('url'):
                    st.write(f"🔗 {tender.get('url')}")
        
        st.divider()
        
        # Post button
        if st.button("🚀 Post to Selected Platforms", type="primary", use_container_width=True):
            with st.spinner("Posting to social media..."):
                try:
                    poster = ArcadeSocialPoster()
                    results = []
                    
                    tender_url = tender.get('url', '')
                    
                    # Post to Twitter
                    if post_to_twitter and 'twitter_content' in st.session_state:
                        st.write("📤 Posting to Twitter/X...")
                        twitter_result = poster.post_to_twitter(
                            st.session_state.twitter_content,
                            tender_url
                        )
                        results.append(twitter_result)
                    
                    # Post to LinkedIn
                    if post_to_linkedin and 'linkedin_content' in st.session_state:
                        st.write("📤 Posting to LinkedIn...")
                        linkedin_result = poster.post_to_linkedin(
                            st.session_state.linkedin_content,
                            tender_url
                        )
                        results.append(linkedin_result)
                    
                    # Display results
                    st.divider()
                    st.subheader("📊 Posting Results")
                    
                    for result in results:
                        platform = result['platform'].title()
                        if result['success']:
                            st.success(f"✅ Successfully posted to {platform}!")
                            with st.expander(f"View {platform} Response"):
                                st.json(result['response'])
                        else:
                            st.error(f"❌ Failed to post to {platform}")
                            st.error(f"Error: {result.get('error', 'Unknown error')}")
                    
                    # Save to posted history
                    post_record = {
                        'tender': tender,
                        'timestamp': datetime.now().isoformat(),
                        'platforms': [r['platform'] for r in results if r['success']],
                        'results': results
                    }
                    st.session_state.posted_tenders.append(post_record)
                    
                except Exception as e:
                    st.error(f"Error posting to social media: {str(e)}")
                    st.exception(e)
        
        # Posting history
        if st.session_state.posted_tenders:
            st.divider()
            st.subheader("📜 Posting History")
            
            for i, record in enumerate(reversed(st.session_state.posted_tenders)):
                with st.expander(f"{record['tender']['title']} - {record['timestamp'][:19]}"):
                    st.write(f"**Platforms:** {', '.join(record['platforms'])}")
                    st.json(record['results'])
    
    else:
        st.warning("⚠️ Please select a tender and generate content first.")

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>Tendly Social - Automated Social Media Posting Agent</p>
    <p>Powered by XAI (Grok) for content generation and Arcade AI for social media posting</p>
</div>
""", unsafe_allow_html=True)
