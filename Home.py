"""
Tendly Social - Automated Social Media Posting Agent
Streamlit application for posting tender summaries to social media.
"""
import streamlit as st
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from utils.summarizer import TenderSummarizer
from utils.social_poster import ArcadeSocialPoster

# Load environment variables
load_dotenv()

# Authentication credentials
AUTH_USERNAME = "info@tendly.eu"
AUTH_PASSWORD = "Hanked2$2"


def check_authentication():
    """Check if user is authenticated."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    return st.session_state.authenticated


def show_login_form():
    """Display login form."""
    st.title("🔐 Authentication Required")
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit_button = st.form_submit_button("Login", type="primary")
        
        if submit_button:
            if username == AUTH_USERNAME and password == AUTH_PASSWORD:
                st.session_state.authenticated = True
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password. Please try again.")
    
    return False

# Create summaries directory
SUMMARIES_DIR = Path(__file__).parent / "summaries"
SUMMARIES_DIR.mkdir(exist_ok=True)


def save_summary(tender_id: str, platform: str, content: str, metadata: dict = None):
    """Save summary to JSON file."""
    filename = f"{platform}_summary_{tender_id}.json"
    filepath = SUMMARIES_DIR / filename
    
    summary_data = {
        "tender_id": tender_id,
        "platform": platform,
        "content": content,
        "created_at": datetime.now().isoformat(),
        "metadata": metadata or {}
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    
    return filepath


def load_summary(tender_id: str, platform: str):
    """Load summary from JSON file if it exists."""
    filename = f"{platform}_summary_{tender_id}.json"
    filepath = SUMMARIES_DIR / filename
    
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def extract_post_url(response: dict, platform: str, linkedin_page: str = None):
    """Extract post URL from API response or construct it."""
    if not response:
        return None
    
    # Try to extract from response recursively
    def find_url_in_dict(obj, depth=0):
        """Recursively search for URLs in nested dict/list structures."""
        if depth > 5:  # Prevent infinite recursion
            return None
        
        if isinstance(obj, dict):
            # Check common URL field names
            for key in ['url', 'post_url', 'link', 'permalink', 'tweet_url', 'status_url']:
                if key in obj and isinstance(obj[key], str) and obj[key].startswith('http'):
                    return obj[key]
            
            # Recursively search values
            for value in obj.values():
                result = find_url_in_dict(value, depth + 1)
                if result:
                    return result
        
        elif isinstance(obj, list):
            for item in obj:
                result = find_url_in_dict(item, depth + 1)
                if result:
                    return result
        
        elif isinstance(obj, str) and obj.startswith('http'):
            # Check if it's a social media URL
            if platform == "twitter" and ('twitter.com' in obj or 'x.com' in obj):
                return obj
            elif platform == "linkedin" and 'linkedin.com' in obj:
                return obj
        
        return None
    
    # First try recursive search
    url = find_url_in_dict(response)
    if url:
        return url
    
    # Fallback: try regex patterns on string representation
    response_str = json.dumps(response)
    
    # Look for URL patterns in response
    url_patterns = [
        r'https://(?:twitter\.com|x\.com)/\w+/status/\d+',
        r'https://www\.linkedin\.com/feed/update/[a-zA-Z0-9_-]+',
        r'https://www\.linkedin\.com/posts/[a-zA-Z0-9_-]+',
    ]
    
    for pattern in url_patterns:
        match = re.search(pattern, response_str)
        if match:
            return match.group(0)
    
    # If not found, try to construct URLs from IDs
    if platform == "twitter":
        # Try to get tweet ID from response
        tweet_id_match = re.search(r'"id":\s*"?(\d{15,20})"?', response_str)
        if tweet_id_match:
            tweet_id = tweet_id_match.group(1)
            # Try to get username from response or use default
            username_match = re.search(r'"username":\s*"([^"]+)"', response_str)
            username = username_match.group(1) if username_match else "tendlyeu"
            return f"https://twitter.com/{username}/status/{tweet_id}"
    
    elif platform == "linkedin":
        # Try to get activity/post ID from response
        activity_match = re.search(r'"activity":\s*"?([a-zA-Z0-9_-]{10,})"?', response_str)
        if activity_match:
            activity_id = activity_match.group(1)
            return f"https://www.linkedin.com/feed/update/{activity_id}"
        
        # Try to find post ID
        post_id_match = re.search(r'"post_id":\s*"?([a-zA-Z0-9_-]+)"?', response_str)
        if post_id_match:
            post_id = post_id_match.group(1)
            return f"https://www.linkedin.com/posts/{post_id}"
        
        # Fallback: construct from LinkedIn page
        if linkedin_page:
            # Extract company name from LinkedIn page URL
            company_match = re.search(r'linkedin\.com/company/([^/]+)', linkedin_page)
            if company_match:
                company = company_match.group(1)
                return f"https://www.linkedin.com/company/{company}/"
    
    return None

# Page configuration
st.set_page_config(
    page_title="Tendly Social - Automated Posting Agent",
    page_icon="📢",
    layout="wide"
)

# Check authentication
if not check_authentication():
    show_login_form()
    st.stop()

# Title and description
st.title("📢 Tendly Social - Automated Posting Agent")
st.markdown("""
This application helps you automatically generate and post tender summaries to social media platforms 
(Twitter/X and LinkedIn) using AI-powered content generation and Arcade AI for posting.
""")

# Initialize session state
if 'posted_tenders' not in st.session_state:
    st.session_state.posted_tenders = []
if 'saved_summaries' not in st.session_state:
    st.session_state.saved_summaries = {}

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

# Logout button
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()

st.sidebar.divider()

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
            
            # Try to load saved summary
            tender_id = tender.get('id', 'unknown')
            saved_x_summary = load_summary(tender_id, 'x')
            
            if saved_x_summary:
                st.info("📄 Found saved summary - loading...")
                if 'twitter_content' not in st.session_state:
                    st.session_state.twitter_content = saved_x_summary['content']
            
            if st.button("Generate Twitter Summary", key="gen_twitter"):
                with st.spinner("Generating Twitter content..."):
                    try:
                        summarizer = TenderSummarizer()
                        twitter_summary = summarizer.summarize_for_twitter(tender)
                        hashtags = summarizer.create_hashtags(tender)
                        
                        # Combine summary with hashtags
                        full_twitter = f"{twitter_summary}\n\n{' '.join(hashtags[:3])}"
                        
                        st.session_state.twitter_content = full_twitter
                        
                        # Save to file
                        save_summary(tender_id, 'x', full_twitter, {
                            "hashtags": hashtags[:3],
                            "tender_title": tender.get('title', '')
                        })
                        st.session_state.saved_summaries[f'x_{tender_id}'] = full_twitter
                        
                        st.success("✅ Twitter content generated and saved!")
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
                
                # Save updated content
                if twitter_content != st.session_state.get('last_saved_twitter'):
                    save_summary(tender_id, 'x', twitter_content, {
                        "hashtags": [],
                        "tender_title": tender.get('title', ''),
                        "edited": True
                    })
                    st.session_state.last_saved_twitter = twitter_content
                
                st.write(f"Character count: {len(twitter_content)}/280")
        
        with col2:
            st.subheader("💼 LinkedIn Content")
            
            # Try to load saved summary
            tender_id = tender.get('id', 'unknown')
            saved_linkedin_summary = load_summary(tender_id, 'linkedin')
            
            if saved_linkedin_summary:
                st.info("📄 Found saved summary - loading...")
                if 'linkedin_content' not in st.session_state:
                    st.session_state.linkedin_content = saved_linkedin_summary['content']
            
            if st.button("Generate LinkedIn Summary", key="gen_linkedin"):
                with st.spinner("Generating LinkedIn content..."):
                    try:
                        summarizer = TenderSummarizer()
                        linkedin_summary = summarizer.summarize_for_linkedin(tender)
                        hashtags = summarizer.create_hashtags(tender)
                        
                        # Combine summary with hashtags
                        full_linkedin = f"{linkedin_summary}\n\n{' '.join(hashtags)}"
                        
                        st.session_state.linkedin_content = full_linkedin
                        
                        # Save to file
                        save_summary(tender_id, 'linkedin', full_linkedin, {
                            "hashtags": hashtags,
                            "tender_title": tender.get('title', '')
                        })
                        st.session_state.saved_summaries[f'linkedin_{tender_id}'] = full_linkedin
                        
                        st.success("✅ LinkedIn content generated and saved!")
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
                
                # Save updated content
                if linkedin_content != st.session_state.get('last_saved_linkedin'):
                    save_summary(tender_id, 'linkedin', linkedin_content, {
                        "hashtags": [],
                        "tender_title": tender.get('title', ''),
                        "edited": True
                    })
                    st.session_state.last_saved_linkedin = linkedin_content
                
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
    
    tender_id = None
    if 'selected_tender' in st.session_state:
        tender = st.session_state.selected_tender
        tender_id = tender.get('id', 'unknown')
        
        # Try to load saved summaries if not in session state
        if 'twitter_content' not in st.session_state:
            saved_x = load_summary(tender_id, 'x')
            if saved_x:
                st.session_state.twitter_content = saved_x['content']
        
        if 'linkedin_content' not in st.session_state:
            saved_linkedin = load_summary(tender_id, 'linkedin')
            if saved_linkedin:
                st.session_state.linkedin_content = saved_linkedin['content']
    
    if 'selected_tender' in st.session_state and \
       ('twitter_content' in st.session_state or 'linkedin_content' in st.session_state):
        
        tender = st.session_state.selected_tender
        
        st.info(f"**Ready to post:** {tender['title']}")
        
        # Show saved summary status
        if tender_id:
            saved_x = load_summary(tender_id, 'x')
            saved_linkedin = load_summary(tender_id, 'linkedin')
            if saved_x or saved_linkedin:
                status_msg = "📄 Saved summaries: "
                if saved_x:
                    status_msg += "✅ X/Twitter "
                if saved_linkedin:
                    status_msg += "✅ LinkedIn"
                st.caption(status_msg)
        
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
                    post_urls = {}
                    
                    tender_url = tender.get('url', '')
                    
                    # Post to Twitter
                    if post_to_twitter and 'twitter_content' in st.session_state:
                        st.write("📤 Posting to Twitter/X...")
                        twitter_result = poster.post_to_twitter(
                            st.session_state.twitter_content,
                            tender_url
                        )
                        results.append(twitter_result)
                        
                        # Try to extract post URL
                        if twitter_result['success']:
                            post_url = extract_post_url(twitter_result.get('response'), 'twitter')
                            if post_url:
                                post_urls['twitter'] = post_url
                    
                    # Post to LinkedIn
                    if post_to_linkedin and 'linkedin_content' in st.session_state:
                        st.write("📤 Posting to LinkedIn...")
                        linkedin_result = poster.post_to_linkedin(
                            st.session_state.linkedin_content,
                            tender_url
                        )
                        results.append(linkedin_result)
                        
                        # Try to extract post URL
                        if linkedin_result['success']:
                            post_url = extract_post_url(
                                linkedin_result.get('response'), 
                                'linkedin',
                                linkedin_page
                            )
                            if post_url:
                                post_urls['linkedin'] = post_url
                    
                    # Display results
                    st.divider()
                    st.subheader("📊 Posting Results")
                    
                    for result in results:
                        platform = result['platform'].title()
                        platform_key = result['platform']
                        
                        if result['success']:
                            st.success(f"✅ Successfully posted to {platform}!")
                            
                            # Show post URL if available
                            if platform_key in post_urls:
                                st.markdown(f"🔗 **View post:** [{platform} Post]({post_urls[platform_key]})")
                            else:
                                # Try to construct URL as fallback
                                if platform_key == 'twitter':
                                    st.info("💡 Check your Twitter/X profile for the new post")
                                elif platform_key == 'linkedin':
                                    st.info(f"💡 Check your [LinkedIn page]({linkedin_page}) for the new post")
                            
                            with st.expander(f"View {platform} API Response"):
                                st.json(result['response'])
                        else:
                            st.error(f"❌ Failed to post to {platform}")
                            st.error(f"Error: {result.get('error', 'Unknown error')}")
                    
                    # Save to posted history
                    post_record = {
                        'tender': tender,
                        'timestamp': datetime.now().isoformat(),
                        'platforms': [r['platform'] for r in results if r['success']],
                        'results': results,
                        'post_urls': post_urls
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
                    
                    # Show post URLs if available
                    if 'post_urls' in record and record['post_urls']:
                        st.write("**Post Links:**")
                        for platform, url in record['post_urls'].items():
                            st.markdown(f"- [{platform.title()}]({url})")
                    
                    with st.expander("View API Response Details"):
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
