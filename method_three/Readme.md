# Workers' Compensation Coverage Scraper

## Overview

This Python script is a comprehensive web scraping tool designed to extract workers' compensation insurance coverage data from the California Workers' Compensation Insurance Rating Bureau (WCIRB) website. The tool features browser automation, proxy rotation, session management, and Firebase integration for distributed processing.

## Key Features

1. **Browser Automation**: Uses Selenium with Undetected ChromeDriver for automated navigation
2. **Proxy Rotation**: Supports multiple proxy services (Bright Data, Proxy Manager) to avoid IP blocking
3. **Session Management**: Maintains persistent sessions with automatic recovery
4. **OTP Automation**: Automatically retrieves and enters one-time passcodes from Gmail
5. **Disclaimer Handling**: Records and replays mouse movements for disclaimer acceptance
6. **Distributed Processing**: Firebase integration for multi-instance coordination
7. **Error Recovery**: Comprehensive retry logic and session recovery mechanisms
8. **Progress Tracking**: Saves progress to resume interrupted operations
9. **Detailed Logging**: Comprehensive debug logs and request/response tracking

## Architecture

### Core Components

#### 1. **Browser Management**
- Initializes Chrome browser with proxy configuration
- Handles authentication flow including CAPTCHA and OTP
- Manages cookie persistence and session conversion

#### 2. **Proxy Management**
- Rotates proxies to prevent detection
- Tracks proxy performance and success rates
- Supports multiple proxy integration methods

#### 3. **Authentication System**
- **Disclaimer Handler**: Manages "CAT CHAT" disclaimer with mouse recording/replay
- **OTP Automation**: Retrieves passcodes from Gmail API and auto-fills forms
- **Session Validation**: Continuously monitors session status

#### 4. **Data Processing**
- Searches for employers by name, zip code, and coverage date
- Extracts detailed policy information including insurer data
- Handles multiple results per employer

#### 5. **Firebase Coordination** (Distributed Mode)
- Uploads CSV data to Firebase for job distribution
- Coordinates multiple worker instances
- Tracks job status and results centrally

## Setup Instructions

### Prerequisites

1. **Python 3.8+**
2. **Chrome Browser** installed
3. **Gmail Account** for OTP retrieval
4. **Proxy Service** (Bright Data or similar, optional but recommended)

### Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install seleniumbase requests beautifulsoup4 firebase-admin pyautogui pynput google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

3. For browser automation:
```bash
pip install seleniumbase
```

### Configuration Files

#### 1. **Gmail API Setup**
- Create a project in Google Cloud Console
- Enable Gmail API
- Download `credentials.json` and place in project root
- First run will create `token.pickle` for authentication

#### 2. **Firebase Setup** (Optional)
- Create a Firebase project
- Generate service account key as `firebase_service_account.json`
- Set `FIREBASE_DB_URL` to your Realtime Database URL

#### 3. **Proxy Configuration**
Edit the proxy settings in the CONFIG section:
```python
PROXY_INTEGRATION_METHOD = "PROXY_GATEWAY"  # or "PROXY_MANAGER"
BRIGHT_DATA_USERNAME = "your_username"
BRIGHT_DATA_PASSWORD = "your_password"
```

#### 4. **Input CSV Format**
Create `input_fast.csv` with columns:
- Bureau Number
- Employer Name  
- Zip Code
- Coverage Date (MM/DD/YYYY)

## Usage

### Single Instance Mode

Run the script normally:
```bash
python scraper.py
```

This will:
1. Launch a Chrome browser with proxy
2. Handle disclaimer (may require manual interaction first time)
3. Automatically retrieve and enter OTP
4. Process all employers in the input CSV
5. Save results to `final_output_fast_1.csv`

### Distributed Mode (Firebase)

1. Ensure Firebase is configured
2. Set `UPLOAD_CSV_TO_FIREBASE = True`
3. Run multiple instances:
```bash
python scraper.py
```

Each instance will:
1. Claim pending jobs from Firebase
2. Process them independently
3. Upload results back to Firebase
4. Continue until all jobs are complete

### Mouse Recording for Disclaimer

First time running, the script will prompt to record mouse movements for the disclaimer. Options:
1. **Record movements**: Move mouse to "Accept" button and click, then press F10
2. **Handle manually**: Accept disclaimer manually
3. **Record while handling**: System records your actions for future automation

Recorded actions are saved to `disclaimer_mouse_record.json` for automatic replay in subsequent runs.

## Configuration Options

### Proxy Methods
- **PROXY_GATEWAY**: Uses Bright Data residential proxies
- **PROXY_MANAGER**: Uses local proxy manager (port 24000)

### Performance Settings
- `MAX_RETRIES`: Number of retry attempts (default: 100)
- `RETRY_DELAY`: Delay between retries in seconds (default: 2)
- `PROXY_MAX_RETRIES`: Proxy-specific retries (default: 100)

### File Paths
- `INPUT_CSV`: Input data file
- `OUTPUT_CSV`: Results output
- `COOKIE_FILE`: Browser cookies storage
- `PROGRESS_FILE`: Progress tracking

## Error Handling & Recovery

The script includes multiple recovery mechanisms:

### Session Recovery
1. **Browser Refresh**: Attempts to refresh browser session
2. **Full Re-authentication**: Repeats entire authentication flow
3. **Proxy Rotation**: Switches to different proxy on failures

### Error Types Handled
- Session expiration
- Proxy failures
- OTP timeouts
- Network errors
- Rate limiting

### Progress Persistence
- Automatically saves progress every 5 records
- Can resume from interruption
- Prevents duplicate processing

## Output Format

Results are saved in both CSV and JSON formats:

### CSV Columns:
- Bureau Number
- Employer Name
- Street Address
- City
- State
- Zip Code
- Insurer Name
- LookupStatus (Found/Not Found/Details Not Found)

### JSON Structure:
```json
{
  "bureau_number": "12345",
  "employer_name": "Company Name",
  "street_address": "123 Main St",
  "city": "Los Angeles",
  "state": "CA",
  "zip_code": "90001",
  "insurer_name": "Insurance Co",
  "fein": "123456789",
  "lookup_status": "Found",
  "extracted_at": "2024-01-01 12:00:00"
}
```

## Debugging

### Log Files
- `debug_logs/execution_log.txt`: Step-by-step execution log
- `debug_logs/*.html`: Saved page sources for errors
- `debug_logs/*.png`: Screenshots for visual debugging
- `request_logs_1.jsonl`: Detailed HTTP request/response logs

### Common Issues

1. **OTP Not Received**
   - Check Gmail API credentials
   - Verify email address in configuration
   - Check spam folder

2. **Proxy Connection Failed**
   - Verify proxy credentials
   - Check network connectivity
   - Try different proxy method

3. **Browser Detection**
   - Update ChromeDriver
   - Try different proxy
   - Adjust wait times

4. **Firebase Connection**
   - Verify service account JSON
   - Check database rules
   - Verify network access

## Performance Tips

1. **Use Residential Proxies**: Better success rates
2. **Adjust Retry Delays**: Increase for unstable connections
3. **Monitor Rate Limits**: Stay within provider limits
4. **Use Distributed Mode**: For large datasets
5. **Regular Cookie Refresh**: Maintains session validity

## Legal & Ethical Considerations

1. **Terms of Service**: Review target website's ToS
2. **Rate Limiting**: Implement respectful crawling delays
3. **Data Usage**: Use extracted data responsibly
4. **Compliance**: Adhere to relevant data protection laws
