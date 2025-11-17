"""
Tests for the TenderSummarizer utility.
"""
import pytest
import json
import os
from pathlib import Path
from utils.summarizer import TenderSummarizer


# Load sample tenders for testing
@pytest.fixture
def sample_tender():
    """Load a sample tender for testing."""
    tenders_file = Path(__file__).parent.parent / "sample_tenders.json"
    with open(tenders_file, 'r') as f:
        tenders = json.load(f)
    return tenders[0]  # Return first tender


@pytest.fixture
def summarizer():
    """Create a TenderSummarizer instance."""
    # Check if XAI_API_KEY is available
    api_key = os.getenv('XAI_API_KEY')
    if not api_key:
        pytest.skip("XAI_API_KEY not found in environment")
    return TenderSummarizer(api_key=api_key)


class TestTenderSummarizer:
    """Test suite for TenderSummarizer."""
    
    def test_initialization(self):
        """Test that summarizer initializes correctly."""
        api_key = os.getenv('XAI_API_KEY')
        if api_key:
            summarizer = TenderSummarizer(api_key=api_key)
            assert summarizer.api_key == api_key
            assert summarizer.client is not None
    
    def test_initialization_without_key(self):
        """Test that initialization fails without API key."""
        # Temporarily remove the key from environment
        original_key = os.environ.pop('XAI_API_KEY', None)
        
        try:
            with pytest.raises(ValueError, match="XAI_API_KEY must be provided"):
                TenderSummarizer()
        finally:
            # Restore the key
            if original_key:
                os.environ['XAI_API_KEY'] = original_key
    
    def test_summarize_for_twitter(self, summarizer, sample_tender):
        """Test Twitter summary generation."""
        summary = summarizer.summarize_for_twitter(sample_tender)
        
        # Check that summary is not empty
        assert summary, "Twitter summary should not be empty"
        
        # Check length constraint (280 characters for Twitter)
        assert len(summary) <= 280, f"Twitter summary too long: {len(summary)} chars"
        
        # Check that it contains some key information
        # (This is a loose check as AI-generated content varies)
        assert len(summary) > 50, "Twitter summary seems too short"
        
        print(f"\nTwitter Summary ({len(summary)} chars):")
        print(summary)
    
    def test_summarize_for_linkedin(self, summarizer, sample_tender):
        """Test LinkedIn summary generation."""
        summary = summarizer.summarize_for_linkedin(sample_tender)
        
        # Check that summary is not empty
        assert summary, "LinkedIn summary should not be empty"
        
        # LinkedIn posts can be longer
        assert len(summary) <= 3000, f"LinkedIn summary too long: {len(summary)} chars"
        
        # Should be more detailed than Twitter
        assert len(summary) > 100, "LinkedIn summary seems too short"
        
        print(f"\nLinkedIn Summary ({len(summary)} chars):")
        print(summary)
    
    def test_create_hashtags(self, summarizer, sample_tender):
        """Test hashtag generation."""
        hashtags = summarizer.create_hashtags(sample_tender)
        
        # Check that hashtags are returned
        assert isinstance(hashtags, list), "Hashtags should be a list"
        assert len(hashtags) > 0, "Should generate at least one hashtag"
        
        # Check that all hashtags start with #
        for tag in hashtags:
            assert tag.startswith('#'), f"Hashtag should start with #: {tag}"
        
        # Check for base hashtags
        assert '#PublicProcurement' in hashtags or '#Tenders' in hashtags
        
        print(f"\nGenerated Hashtags:")
        print(', '.join(hashtags))
    
    def test_category_specific_hashtags(self, summarizer):
        """Test that category-specific hashtags are generated correctly."""
        # Test IT category
        it_tender = {
            "title": "Software Development",
            "category": "IT & Software Development",
            "organization": "Test Org",
            "budget": "€100,000",
            "deadline": "2025-12-31",
            "description": "Test description"
        }
        
        hashtags = summarizer.create_hashtags(it_tender)
        assert any('IT' in tag or 'Software' in tag for tag in hashtags), \
            "Should include IT-related hashtags"
        
        # Test Construction category
        construction_tender = {
            "title": "Building Construction",
            "category": "Construction & Infrastructure",
            "organization": "Test Org",
            "budget": "€100,000",
            "deadline": "2025-12-31",
            "description": "Test description"
        }
        
        hashtags = summarizer.create_hashtags(construction_tender)
        assert any('Construction' in tag or 'Infrastructure' in tag for tag in hashtags), \
            "Should include construction-related hashtags"


def test_all_sample_tenders():
    """Test summarization for all sample tenders."""
    # Check if XAI_API_KEY is available
    api_key = os.getenv('XAI_API_KEY')
    if not api_key:
        pytest.skip("XAI_API_KEY not found in environment")
    
    summarizer = TenderSummarizer(api_key=api_key)
    
    # Load all sample tenders
    tenders_file = Path(__file__).parent.parent / "sample_tenders.json"
    with open(tenders_file, 'r') as f:
        tenders = json.load(f)
    
    results = []
    
    for tender in tenders:
        print(f"\n{'='*80}")
        print(f"Testing Tender: {tender['title']}")
        print(f"{'='*80}")
        
        # Generate Twitter summary
        twitter_summary = summarizer.summarize_for_twitter(tender)
        
        # Generate LinkedIn summary
        linkedin_summary = summarizer.summarize_for_linkedin(tender)
        
        # Generate hashtags
        hashtags = summarizer.create_hashtags(tender)
        
        result = {
            'tender_id': tender['id'],
            'tender_title': tender['title'],
            'twitter_summary': twitter_summary,
            'twitter_length': len(twitter_summary),
            'linkedin_summary': linkedin_summary,
            'linkedin_length': len(linkedin_summary),
            'hashtags': hashtags
        }
        
        results.append(result)
        
        print(f"\nTwitter ({len(twitter_summary)} chars):")
        print(twitter_summary)
        print(f"\nLinkedIn ({len(linkedin_summary)} chars):")
        print(linkedin_summary)
        print(f"\nHashtags: {', '.join(hashtags)}")
    
    # Save results to test-results directory
    output_dir = Path(__file__).parent.parent / "test-results"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "summarizer_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"Results saved to: {output_file}")
    print(f"{'='*80}")
    
    assert len(results) == len(tenders), "Should process all tenders"
