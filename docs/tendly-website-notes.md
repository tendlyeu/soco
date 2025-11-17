# Tendly Website Exploration Notes

## Website Structure

### Tenders Page (https://www.tendly.eu/tenders)
- **Status**: Requires login to access tender listings
- **Language**: Estonian (🇪🇪)
- **Features**: 
  - Login required to view tender data
  - Google authentication available
  - Email/password authentication available

### Insights Page (https://www.tendly.eu/insights)
- **Status**: Publicly accessible but limited content
- **Title**: "Ettevõtete analüütika" (Company Analytics)
- **Description**: "Otsi ja analüüsi Eesti ettevõtete riigihangete tulemusi" (Search and analyze Estonian companies' public procurement results)
- **Features**:
  - Company search by name or registration code
  - Shows "Most searched companies":
    - Nortal AS
    - Aktsiaselts Merko Ehitus Eesti
    - AS TREV-2 Grupp

## Data Access Strategy

Since both pages require authentication or have limited public content, we'll need to:

1. **Create sample tender data** for testing the social media posting functionality
2. **Use the XAI API** to generate realistic tender summaries
3. **Implement authentication** if we need to access real tender data in the future

## Sample Tender Topics (for testing)

Based on the Estonian public procurement context, we can create sample tenders in categories like:
- IT and software development
- Construction and infrastructure
- Healthcare services
- Education and training
- Environmental services
- Transportation and logistics
