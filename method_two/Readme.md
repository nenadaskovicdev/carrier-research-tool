# Employer Data Extractor for CA Work Comp Coverage

A robust Python tool for automating the extraction of employer and policy holder information from the California Workers' Compensation Insurance Coverage website. This tool handles authentication, bulk processing, and data export with comprehensive error handling and progress tracking.

## 🚀 Features

- **Dual Authentication Methods**: Manual browser-based authentication with automatic cookie capture
- **Bulk Processing**: Process hundreds of employers from a CSV input file
- **Progress Tracking**: Resume interrupted jobs without losing data
- **Comprehensive Data Extraction**: Extract employer details, policy information, and insurer data
- **Multiple Output Formats**: Export data in both CSV (tab-delimited) and JSON formats
- **Error Resilience**: Built-in retry logic and graceful error handling
- **Detailed Logging**: Step-by-step execution logging with visual indicators

## 📋 Prerequisites

### System Requirements
- Python 3.7 or higher
- Google Chrome browser (latest version)
- 4GB RAM minimum, 8GB recommended for large datasets

### Python Dependencies
Create a `requirements.txt` file with:
```txt
seleniumbase>=4.25.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pandas>=2.0.0
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## 📁 File Structure

```
employer_data_extractor/
├── employer_extractor.py          # Main script
├── input.csv                      # Input file with employer data (created if missing)
├── sample_input.csv               # Sample input file (auto-generated)
├── final_output.csv               # Output data (CSV format)
├── final_output.json              # Output data (JSON format)
├── progress_tracker.json          # Progress tracking file
├── browser_cookies.pkl            # Saved browser cookies
├── requests_session.pkl           # Saved requests session
└── README.md                      # This documentation
```

## 🔧 Installation

1. Clone or download the script files
2. Install dependencies:
   ```bash
   pip install seleniumbase requests beautifulsoup4 pandas
   ```
3. Ensure all Python modules are in the same directory

## 📝 Input File Format

Create an `input.csv` file with the following columns (case-sensitive):

| Column | Description | Format | Example |
|--------|-------------|--------|---------|
| **Bureau Number** | Unique identifier for employer | String | "42" |
| **Employer Name** | Company name to search | String | "BAXTER AUTO" |
| **Zip Code** | Location ZIP code | 5-digit string | "97217" |
| **Coverage Date** | Policy coverage date | MM/DD/YYYY | "11/01/2025" |

### Sample Input
```csv
Bureau Number,Employer Name,Zip Code,Coverage Date
42,BAXTER AUTO,97217,11/1/2025
270,MOORE TWININ,93716,11/1/2025
637,MORRIS SHAND,90021,11/1/2025
```

## 🚀 Usage

### Basic Execution
```bash
python employer_extractor.py
```

### First Run Workflow

1. **Authentication Phase**:
   ```
   ======================================================================
   MANUAL AUTHENTICATION REQUIRED
   ======================================================================
   Please complete the following steps in the browser:
   1. Solve the Cloudflare challenge (if present)
   2. Solve the CAPTCHA in the disclaimer modal
   3. Complete OTP verification if required
   4. Wait until you reach the main search page
   5. The browser should show the search form
   6. Then return here and press Enter to continue
   ======================================================================
   ```

2. **Processing Phase**:
   - Script processes each employer from input.csv
   - Shows real-time progress
   - Saves results incrementally
   - Handles network errors with retries

3. **Completion**:
   - Results saved to `final_output.csv` and `final_output.json`
   - Progress saved for potential resume

### Resuming Interrupted Jobs
If the script stops unexpectedly, simply run it again. It will:
- Load previous progress
- Skip already processed employers
- Continue from where it left off

## 📊 Output Format

### CSV Output (`final_output.csv`)
Tab-delimited CSV with the following columns:

| Column | Description |
|--------|-------------|
| **Bureau Number** | Original bureau number from input |
| **Employer Name** | Full employer name found |
| **Street Address** | Company street address |
| **City** | City location |
| **State** | State abbreviation |
| **Zip Code** | Postal code |
| **Insurer Name** | Insurance provider name |
| **LookupStatus** | Result status (Found/Not Found/Details Not Found) |

### JSON Output (`final_output.json`)
Structured JSON array with detailed records including:
- All CSV fields
- Additional metadata (FEIN, extraction timestamp)
- Raw data for debugging

## ⚙️ Configuration

Edit the `CONFIG` dictionary in the `main()` function to customize:

```python
CONFIG = {
    "email_address": "your-email@example.com",  # For reference only
    "website_url": "https://www.caworkcompcoverage.com/Search",
}
```

### Adjustable Parameters
- `MAX_RETRIES`: Number of retry attempts for failed requests (default: 3)
- `RETRY_DELAY`: Delay between retries in seconds (default: 2)

## 🔒 Security Features

- **Session Persistence**: Cookies encrypted and stored locally
- **No Password Storage**: Only session cookies saved, no credentials
- **Local Storage**: All data remains on your machine
- **Clean Logging**: No sensitive data in logs

## 🐛 Troubleshooting

### Common Issues

**1. Authentication Fails**
```
Solution: Delete browser_cookies.pkl and requests_session.pkl, then restart
```

**2. Chrome Driver Issues**
```
Solution: Ensure Chrome is updated, run: webdriver-manager install --user
```

**3. No Results Found**
```
Check: 
- Input data accuracy
- Authentication still valid
- Website accessibility
```

**4. Memory Issues with Large Files**
```
Solution: Process in smaller batches by splitting input.csv
```

### Log Levels
The script provides detailed logging with emoji indicators:
- ✅ Success: Operation completed successfully
- 🔄 Retry: Operation being retried
- ⚠️ Warning: Non-critical issue
- ❌ Error: Critical failure
- ℹ️ Info: General information

## 📈 Performance Tips

1. **Batch Size**: Process 100-200 employers per session
2. **Network Stability**: Use a stable internet connection
3. **Regular Saves**: Progress is saved after each employer
4. **Monitor Resources**: Large datasets may require more RAM

## ⚠️ Important Notes

### Legal Compliance
- Use only for legitimate business purposes
- Comply with website terms of service
- Respect rate limits and access policies
- Do not use for unauthorized data collection

### Limitations
- Requires manual authentication due to CAPTCHA/Cloudflare
- Dependent on website structure (may break if site updates)
- Rate-limited to prevent server overload

### Data Accuracy
- Verify extracted data against source
- Some fields may be empty if not available
- Status field indicates confidence level

## 🔄 Maintenance

### Regular Updates
- Monitor for website changes
- Update dependencies regularly
- Test with sample data before large runs

### Error Recovery
1. Check `progress_tracker.json` for last processed item
2. Review logs for specific errors
3. Remove problematic entries from input.csv if needed
4. Restart script


