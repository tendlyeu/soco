# Tendly Social - Automated Social Media Posting Agent

An intelligent social media automation tool that generates and posts tender summaries from Tendly.eu to Twitter/X and LinkedIn using AI-powered content generation and Arcade AI for posting.

## Overview

Tendly Social streamlines the process of sharing public procurement opportunities on social media by automatically generating engaging, platform-optimized content using XAI's Grok-3 model and posting it through Arcade AI's social media integration.

## Features

### Core Functionality

- **AI-Powered Content Generation**: Leverages XAI Grok-3 to create engaging, professional summaries optimized for each platform
- **Multi-Platform Posting**: Automated posting to Twitter/X and LinkedIn with platform-specific formatting
- **Interactive Web Interface**: User-friendly Streamlit application for tender selection and content management
- **Content Customization**: Edit AI-generated content before posting
- **Hashtag Generation**: Automatic category-specific hashtag suggestions
- **Posting History**: Track all published posts with timestamps and platform details

### Technical Capabilities

- **Modular Architecture**: Separate utilities for summarization and social media posting
- **Comprehensive Testing**: Full test suite with pytest and HTML reporting
- **Environment Configuration**: Secure API key management through environment variables
- **Error Handling**: Robust error handling for API failures and rate limiting
- **Extensible Design**: Easy to add new platforms or content sources

## Project Structure

```
tendly-social/
├── app.py                          # Main Streamlit application
├── sample_tenders.json             # Sample tender data for testing
├── .env                            # Environment variables (API keys)
├── requirements.txt                # Python dependencies
├── pytest.ini                      # Pytest configuration
│
├── utils/                          # Utility modules
│   ├── __init__.py
│   ├── summarizer.py              # XAI-powered content generation
│   └── social_poster.py           # Arcade AI social media posting
│
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── test_summarizer.py         # Summarizer unit tests
│   └── test_social_poster.py      # Social poster unit tests
│
├── test-results/                   # Test outputs and reports
│   ├── report.html                # Pytest HTML report
│   ├── summarizer_test_results.json  # AI-generated summaries
│   ├── testing-commentary.md      # Detailed testing notes
│   └── streamlit-app-main.webp    # Application screenshot
│
└── docs/                           # Documentation
    ├── tendly-website-notes.md    # Website exploration notes
    ├── api-integration.md         # API integration guide
    ├── deployment.md              # Deployment instructions
    └── troubleshooting.md         # Common issues and solutions
```

## Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager
- Virtual environment (recommended)

### Setup Steps

1. **Clone the repository**

```bash
git clone https://github.com/tendlyeu/tendly-social.git
cd tendly-social
```

2. **Create and activate virtual environment**

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file in the project root with the following variables:

```env
# API Keys
ARCADE_API_KEY=your_arcade_api_key_here
XAI_API_KEY=your_xai_api_key_here

# Arcade User Credentials
ARCADE_USER_EMAIL=your_email@example.com
ARCADE_USER_PASSWORD=your_password

# Social Media Credentials
TWITTER_EMAIL=your_twitter_email@example.com
TWITTER_PASSWORD=your_twitter_password
LINKEDIN_PAGE=https://www.linkedin.com/company/your-company/
```

## Usage

### Running the Streamlit Application

```bash
streamlit run app.py
```

The application will be available at `http://localhost:8501`

### Application Workflow

1. **Select a Tender**
   - Browse available tenders in the "Select Tender" tab
   - Click "Select This Tender" to choose one for posting

2. **Generate Content**
   - Navigate to the "Generate Content" tab
   - Click "Generate Twitter Summary" for a 280-character post
   - Click "Generate LinkedIn Summary" for a detailed professional post
   - Edit the generated content if needed

3. **Post to Social Media**
   - Review the content preview in the "Post to Social Media" tab
   - Select target platforms (Twitter/X and/or LinkedIn)
   - Click "Post to Selected Platforms" to publish

### Running Tests

Execute the full test suite:

```bash
pytest tests/ -v --html=test-results/report.html --self-contained-html
```

Run specific test modules:

```bash
# Test summarizer only
pytest tests/test_summarizer.py -v

# Test social poster only
pytest tests/test_social_poster.py -v

# Run comprehensive summarizer test with all sample tenders
export $(cat .env | xargs)
pytest tests/test_summarizer.py::test_all_sample_tenders -v -s
```

## API Integration

### XAI (Grok) Integration

The application uses XAI's Grok-3 model for content generation:

- **Endpoint**: `https://api.x.ai/v1`
- **Model**: `grok-3`
- **Temperature**: 0.7 (balanced creativity and consistency)
- **Max Tokens**: 150 (Twitter), 500 (LinkedIn)

### Arcade AI Integration

Arcade AI handles social media posting through their unified API:

- **Endpoint**: `https://api.arcade-ai.com/v1`
- **Tools Used**:
  - `X.PostTweet` for Twitter/X posting
  - `LinkedIn.CreatePost` for LinkedIn posting

## Configuration

### Platform Settings

Configure posting behavior in the Streamlit sidebar:

- **Post to Twitter/X**: Enable/disable Twitter posting
- **Post to LinkedIn**: Enable/disable LinkedIn posting
- **LinkedIn Page URL**: Specify company page for posting

### Content Generation Settings

Modify content generation parameters in `utils/summarizer.py`:

```python
# Twitter summary parameters
temperature=0.7
max_tokens=150

# LinkedIn summary parameters
temperature=0.7
max_tokens=500
```

## Sample Tenders

The application includes 5 sample tenders covering various categories:

1. **AI-Powered Public Procurement Platform** (€450,000)
2. **Green Energy Infrastructure** (€2,500,000)
3. **Digital Health Records Integration** (€850,000)
4. **Smart City Transportation Platform** (€680,000)
5. **Cybersecurity Assessment Services** (€320,000)

## Testing

### Test Coverage

- **Unit Tests**: Individual component testing for summarizer and social poster
- **Integration Tests**: End-to-end workflow validation
- **Dry Run Tests**: API structure validation without actual posting

### Test Results

All test results are saved to the `test-results/` directory:

- **HTML Report**: Interactive test execution report
- **JSON Results**: AI-generated summaries for all sample tenders
- **Screenshots**: Application interface captures
- **Commentary**: Detailed testing notes and observations

## Known Issues

### Issue 1: Arcade AI Live Posting

**Status**: Pending Validation

**Description**: The Arcade AI posting functionality is implemented but requires live testing with actual API calls.

**Workaround**: Use dry-run mode for testing content generation without posting.

**Next Steps**: Execute test posts to validate API integration and error handling.

### Issue 2: Tendly.eu Authentication

**Status**: Not Implemented

**Description**: The Tendly.eu website requires authentication to access full tender details.

**Workaround**: Using sample tender data for testing and development.

**Next Steps**: Implement authentication flow to access live tender data from Tendly.eu API.

### Issue 3: Rate Limiting

**Status**: Not Implemented

**Description**: No rate limiting implemented for API calls.

**Recommendation**: Add rate limiting to prevent API quota exhaustion, especially for batch operations.

**Next Steps**: Implement exponential backoff and request throttling.

## Next Steps

### Immediate Priorities

1. **Live Posting Validation**
   - Test actual posting to Twitter/X with Arcade AI
   - Validate LinkedIn company page posting
   - Verify error handling for API failures

2. **Tendly.eu Integration**
   - Implement authentication for Tendly.eu
   - Create API client for fetching live tender data
   - Add automatic tender discovery and filtering

3. **Error Handling Enhancement**
   - Add comprehensive try-catch blocks
   - Implement retry logic with exponential backoff
   - Create detailed error logging

### Future Enhancements

1. **Automation Features**
   - Scheduled posting with cron jobs
   - Batch processing for multiple tenders
   - Automatic tender monitoring and posting

2. **Content Optimization**
   - A/B testing for different content variations
   - Engagement analytics tracking
   - Image generation for social media posts

3. **Multi-language Support**
   - Estonian language content generation
   - Automatic language detection and translation
   - Localized hashtag suggestions

4. **Advanced Features**
   - Custom content templates
   - User role management
   - Analytics dashboard
   - Email notifications for posting status

## Deployment

### Local Deployment

The application is ready for local deployment. Simply follow the installation steps and run the Streamlit app.

### Production Deployment

For production deployment, consider:

1. **Hosting**: Deploy on Streamlit Cloud, Heroku, or AWS
2. **Security**: Implement user authentication and API key encryption
3. **Monitoring**: Add logging and error tracking (e.g., Sentry)
4. **Scaling**: Implement caching and database for tender storage
5. **Backup**: Regular backups of posting history and configuration

See `docs/deployment.md` for detailed deployment instructions.

## Troubleshooting

### Common Issues

**Problem**: "XAI_API_KEY must be provided or set in environment"

**Solution**: Ensure the `.env` file exists and contains the XAI_API_KEY variable. Load environment variables before running the app.

**Problem**: "Port 8501 is already in use"

**Solution**: Kill the existing Streamlit process or use a different port:
```bash
streamlit run app.py --server.port 8502
```

**Problem**: "Model grok-beta was deprecated"

**Solution**: The code has been updated to use `grok-3`. Ensure you're using the latest version of the code.

See `docs/troubleshooting.md` for more detailed troubleshooting guidance.

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software owned by Tendly. All rights reserved.

## Support

For questions, issues, or feature requests:

- **Email**: info@tendly.eu
- **Phone**: +372 509 2839
- **Website**: https://www.tendly.eu

## Acknowledgments

- **XAI (Grok)**: AI-powered content generation
- **Arcade AI**: Social media posting automation
- **Streamlit**: Interactive web application framework
- **Tendly Team**: Product vision and requirements

---

**Version**: 1.0.0  
**Last Updated**: November 16, 2025  
**Maintainer**: Tendly Development Team
