# WCIRB Automation Tool

A Python tool for automating authentication and worker search on the WCIRB (Workers' Compensation Insurance Rating Bureau) website.

## Features

- **Dual Authentication Methods**:
  - Selenium-based authentication (recommended, opens browser)
  - Browser cookies authentication (uses existing Chrome session)
- **OTP Management**:
  - Automatic OTP retrieval from email
  - Manual OTP entry option
- **Search Functionality**: Automated worker detail searches
- **Export Options**: Save results in both JSON and Excel formats

## Prerequisites

### System Requirements
- Python 3.7+
- Google Chrome browser
- ChromeDriver (automatically managed by Selenium)

### Python Dependencies
Install required packages:
```bash
pip install selenium browser-cookie3 pandas openpyxl
```

### Email Setup (for auto-OTP)
To use automatic OTP retrieval, you need:
1. Email app password for Gmail (or other supported email providers)
2. IMAP enabled in your email account

## Installation

1. Clone or download the project files
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Ensure all required modules are in the same directory:
   - `auth.py`
   - `browser_cookie_auth.py`
   - `selenium_auth.py`
   - `client.py`
   - `email_reader.py`
   - `search.py`
   - `storage.py`

## Usage

Run the main script:
```bash
python main.py
```

### First Run (Authentication)

1. **Choose Authentication Method**:
   ```
   === WCIRB Automation ===
   Choose authentication method:
   1. Selenium (recommended - will open browser)
   2. Browser cookies (requires Chrome with logged-in session)
   ```

2. **Selenium Method (Option 1)**:
   - A Chrome browser will open
   - You'll be prompted to log in manually
   - The system will wait for OTP request

3. **Browser Cookies Method (Option 2)**:
   - Requires an already logged-in Chrome session
   - No browser window opens (headless)

4. **OTP Entry**:
   - Enter email app password for automatic OTP retrieval
   - Or press Enter to enter OTP manually
   - OTP will be submitted automatically

### Search Execution

After successful authentication, the tool performs a sample search:
- Employer: "BAXTER AUTO PARTS, INC"
- City: "PORTLAND"
- State: "OR"
- Coverage Date: "11/01/2025"
- Zip Code: "97217"

Results are automatically saved to:
- `output.json` (JSON format)
- `output.xlsx` (Excel format)

## Customizing Searches

To modify the search criteria, edit the `search_data` dictionary in `main.py`:

```python
search_data = {
    "EmployerName": "YOUR_EMPLOYER_NAME",
    "City": "CITY_NAME",
    "State": "STATE_ABBREVIATION",
    "CoverageDate": "MM/DD/YYYY",
    "ZipCode": "ZIP_CODE",
}
```

## File Structure

```
wcib_automation/
├── main.py              # Main script
├── auth.py              # Authentication state management
├── browser_cookie_auth.py  # Browser cookies authentication
├── selenium_auth.py     # Selenium-based authentication
├── client.py            # HTTP client setup
├── email_reader.py      # Email OTP retrieval
├── search.py            # Search functionality
├── storage.py           # Data export (JSON/Excel)
├── output.json          # Generated output (after run)
├── output.xlsx          # Generated output (after run)
└── README.md           # This file
```

## Important Notes

### Security
- Email app passwords are not stored; used only for OTP retrieval
- Authentication tokens are stored locally in `auth_state.json`
- Never commit `auth_state.json` to version control

### Limitations
- Browser cookies method requires an active WCIRB session in Chrome
- Email OTP retrieval currently supports Gmail by default
- Rate limiting: Respect WCIRB's terms of service

### Troubleshooting

**Selenium Issues:**
- Ensure Chrome and ChromeDriver versions match
- Update ChromeDriver: `webdriver-manager install --user`

**Authentication Failures:**
- Clear `auth_state.json` to restart authentication
- Ensure correct email credentials for auto-OTP
- Check internet connection

**Search Errors:**
- Verify search parameters match WCIRB format
- Check if authenticated session is still valid

