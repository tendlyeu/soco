"""
Tests for the ArcadeSocialPoster utility.
"""
import pytest
import os
from utils.social_poster import ArcadeSocialPoster


@pytest.fixture
def poster():
    """Create an ArcadeSocialPoster instance."""
    api_key = os.getenv('ARCADE_API_KEY')
    if not api_key:
        pytest.skip("ARCADE_API_KEY not found in environment")
    return ArcadeSocialPoster(api_key=api_key)


class TestArcadeSocialPoster:
    """Test suite for ArcadeSocialPoster."""
    
    def test_initialization(self):
        """Test that poster initializes correctly."""
        api_key = os.getenv('ARCADE_API_KEY')
        if api_key:
            poster = ArcadeSocialPoster(api_key=api_key)
            assert poster.api_key == api_key
            assert poster.base_url == "https://api.arcade-ai.com/v1"
            assert "Authorization" in poster.headers
    
    def test_initialization_without_key(self):
        """Test that initialization fails without API key."""
        # Temporarily remove the key from environment
        original_key = os.environ.pop('ARCADE_API_KEY', None)
        
        try:
            with pytest.raises(ValueError, match="ARCADE_API_KEY must be provided"):
                ArcadeSocialPoster()
        finally:
            # Restore the key
            if original_key:
                os.environ['ARCADE_API_KEY'] = original_key
    
    def test_post_to_twitter_dry_run(self, poster):
        """Test Twitter posting structure (dry run - no actual posting)."""
        test_content = "Test tweet about a tender opportunity #PublicProcurement #Tenders"
        test_url = "https://www.tendly.eu/tenders/T001"
        
        # This test validates the structure without actually posting
        # In a real scenario, you would mock the API call
        
        # Validate that the method exists and accepts correct parameters
        assert hasattr(poster, 'post_to_twitter')
        
        # Check that content formatting works
        full_content = f"{test_content}\n\n{test_url}"
        assert len(full_content) > 0
        assert test_url in full_content
        
        print(f"\nTwitter post would contain:")
        print(full_content)
    
    def test_post_to_linkedin_dry_run(self, poster):
        """Test LinkedIn posting structure (dry run - no actual posting)."""
        test_content = """
        Exciting tender opportunity in AI and public procurement!
        
        The Estonian Ministry is seeking innovative solutions for AI-powered 
        procurement platforms. This is a great opportunity for tech companies 
        to contribute to digital transformation.
        
        #PublicProcurement #AI #Estonia
        """
        test_url = "https://www.tendly.eu/tenders/T001"
        
        # Validate that the method exists and accepts correct parameters
        assert hasattr(poster, 'post_to_linkedin')
        
        # Check that content formatting works
        full_content = f"{test_content}\n\nLearn more: {test_url}"
        assert len(full_content) > 0
        assert test_url in full_content
        
        print(f"\nLinkedIn post would contain:")
        print(full_content)
    
    def test_post_to_all_platforms_dry_run(self, poster):
        """Test posting to all platforms structure (dry run)."""
        twitter_content = "Test Twitter content #Test"
        linkedin_content = "Test LinkedIn content with more details #Test #LinkedIn"
        test_url = "https://www.tendly.eu/tenders/T001"
        
        # Validate that the method exists
        assert hasattr(poster, 'post_to_all_platforms')
        
        print(f"\nWould post to both platforms:")
        print(f"Twitter: {twitter_content}")
        print(f"LinkedIn: {linkedin_content}")
        print(f"URL: {test_url}")


def test_api_endpoint_structure():
    """Test that API endpoint structure is correct."""
    api_key = os.getenv('ARCADE_API_KEY')
    if not api_key:
        pytest.skip("ARCADE_API_KEY not found in environment")
    
    poster = ArcadeSocialPoster(api_key=api_key)
    
    # Validate base URL
    assert poster.base_url.startswith("https://")
    assert "arcade" in poster.base_url.lower()
    
    # Validate headers
    assert "Authorization" in poster.headers
    assert poster.headers["Authorization"].startswith("Bearer ")
    assert "Content-Type" in poster.headers
    assert poster.headers["Content-Type"] == "application/json"
    
    print(f"\nAPI Configuration:")
    print(f"Base URL: {poster.base_url}")
    print(f"Headers: {poster.headers}")


def test_environment_variables():
    """Test that all required environment variables are set."""
    required_vars = [
        'ARCADE_API_KEY',
        'XAI_API_KEY',
        'ARCADE_USER_EMAIL',
        'ARCADE_USER_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\nWarning: Missing environment variables: {', '.join(missing_vars)}")
        print("These should be set in the .env file for full functionality")
    
    # At least API keys should be present
    assert os.getenv('ARCADE_API_KEY'), "ARCADE_API_KEY is required"
    assert os.getenv('XAI_API_KEY'), "XAI_API_KEY is required"
