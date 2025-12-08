import csv
import json
import os
import pickle
import quopri
import re
import sys
import time
import traceback
from datetime import datetime
from email.header import decode_header
from urllib.parse import quote, urlencode

import requests
from bs4 import BeautifulSoup
from seleniumbase import SB

# File paths
COOKIE_FILE = "browser_cookies.pkl"
REQUESTS_SESSION_FILE = "requests_session.pkl"
PROGRESS_FILE = "progress_tracker.json"
INPUT_CSV = "input.csv"
OUTPUT_CSV = "final_output.csv"
OUTPUT_JSON = "final_output.json"

MAX_RETRIES = 3
RETRY_DELAY = 2


def log_step(step_name, status="INFO", message=""):
    """Log step execution with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️",
        "RETRY": "🔄",
    }
    icon = status_icons.get(status, "🔸")
    print(f"{timestamp} {icon} [{status}] {step_name}: {message}")


def save_cookies(sb):
    """Save all cookies to a file"""
    try:
        cookies = sb.driver.get_cookies()
        with open(COOKIE_FILE, "wb") as file:
            pickle.dump(cookies, file)
        log_step(
            "Save Cookies",
            "SUCCESS",
            f"Cookies saved to {COOKIE_FILE} ({len(cookies)} cookies)",
        )
        return True
    except Exception as e:
        log_step("Save Cookies", "ERROR", f"Error saving cookies: {e}")
        return False


def convert_cookies_to_requests_session():
    """Convert Selenium cookies to requests session"""
    try:
        if not os.path.exists(COOKIE_FILE):
            log_step("Convert Cookies", "ERROR", "No cookie file found")
            return None

        with open(COOKIE_FILE, "rb") as file:
            selenium_cookies = pickle.load(file)

        session = requests.Session()

        # Set common headers to mimic a real browser
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }
        )

        # Add all cookies to the session
        for cookie in selenium_cookies:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        log_step(
            "Convert Cookies",
            "SUCCESS",
            f"Converted {len(selenium_cookies)} cookies to requests session",
        )
        return session

    except Exception as e:
        log_step("Convert Cookies", "ERROR", f"Error converting cookies: {e}")
        return None


def save_requests_session(session):
    """Save requests session to file"""
    try:
        with open(REQUESTS_SESSION_FILE, "wb") as file:
            pickle.dump(session, file)
        log_step(
            "Save Requests Session",
            "SUCCESS",
            f"Session saved to {REQUESTS_SESSION_FILE}",
        )
        return True
    except Exception as e:
        log_step("Save Requests Session", "ERROR", f"Error saving session: {e}")
        return False


def load_requests_session():
    """Load requests session from file"""
    try:
        if not os.path.exists(REQUESTS_SESSION_FILE):
            log_step(
                "Load Requests Session",
                "INFO",
                "No existing session file found",
            )
            return None

        with open(REQUESTS_SESSION_FILE, "rb") as file:
            session = pickle.load(file)

        log_step(
            "Load Requests Session",
            "SUCCESS",
            "Requests session loaded successfully",
        )
        return session
    except Exception as e:
        log_step(
            "Load Requests Session", "ERROR", f"Error loading session: {e}"
        )
        return None


def wait_for_manual_authentication(sb, email_address, website_url):
    """Wait for user to manually complete authentication"""
    log_step(
        "Manual Authentication",
        "INFO",
        "Starting manual authentication process...",
    )

    print("\n" + "=" * 70)
    print("MANUAL AUTHENTICATION REQUIRED")
    print("=" * 70)
    print("Please complete the following steps in the browser:")
    print("1. Solve the Cloudflare challenge (if present)")
    print("2. Solve the CAPTCHA in the disclaimer modal")
    print("3. Complete OTP verification if required")
    print("4. Wait until you reach the main search page")
    print("5. The browser should show the search form")
    print("6. Then return here and press Enter to continue")
    print("=" * 70)

    # Open the website
    log_step("Manual Authentication", "INFO", "Opening website...")
    sb.uc_open_with_reconnect(website_url, 3)

    print(
        "\n🖥️  Browser is now open. Please complete the authentication steps..."
    )
    print(
        "⏳ Waiting for you to complete Cloudflare, CAPTCHA, and OTP verification..."
    )

    # Wait for user to complete authentication
    input("\nPress Enter AFTER you have completed all authentication steps...")

    # Verify we're on the right page
    log_step("Manual Authentication", "INFO", "Verifying authentication...")

    # Check if we're on the search page
    current_url = sb.get_current_url()
    page_title = sb.get_title()

    log_step("Manual Authentication", "INFO", f"Current URL: {current_url}")
    log_step("Manual Authentication", "INFO", f"Page Title: {page_title}")

    # Check for success indicators
    success_indicators = [
        'input[name*="search"]',
        'input[type*="search"]',
        "#Search",
        ".search",
        "#employerName",
        "#coverageDate",
    ]

    authenticated = False
    for indicator in success_indicators:
        if sb.is_element_visible(indicator):
            log_step(
                "Manual Authentication",
                "SUCCESS",
                f"Found search element: {indicator}",
            )
            authenticated = True
            break

    if not authenticated:
        # Check if we're still on authentication pages
        page_source = sb.get_page_source().lower()
        if any(
            word in page_source
            for word in ["cloudflare", "challenge", "verifying", "checking"]
        ):
            log_step(
                "Manual Authentication", "ERROR", "Still on Cloudflare page"
            )
            return False
        elif any(word in page_source for word in ["disclaimer", "captcha"]):
            log_step(
                "Manual Authentication",
                "ERROR",
                "Still on disclaimer/CAPTCHA page",
            )
            return False
        elif any(word in page_source for word in ["one time passcode", "otp"]):
            log_step("Manual Authentication", "ERROR", "Still on OTP page")
            return False
        else:
            log_step(
                "Manual Authentication",
                "WARNING",
                "Not on expected search page, but continuing...",
            )
            authenticated = True

    if authenticated:
        # Save cookies for future use
        log_step(
            "Manual Authentication", "INFO", "Saving authentication cookies..."
        )
        save_cookies(sb)

        # Take screenshot
        sb.save_screenshot("manual_authentication_complete.png")
        log_step(
            "Manual Authentication",
            "SUCCESS",
            "Manual authentication completed successfully",
        )
        return True
    else:
        log_step(
            "Manual Authentication", "ERROR", "Manual authentication failed"
        )
        return False


def convert_date_format(date_str):
    """Convert date from mm/dd/yyyy to yyyy-mm-dd for API requests"""
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError as e:
        log_step("Date Conversion", "ERROR", f"Date conversion error: {e}")
        return date_str


def search_policy_holders(session, employer_name, coverage_date, zip_code):
    """Search for policy holders using requests session with detailed logging"""
    log_step("API Search", "INFO", f"Starting search for: {employer_name}")

    try:
        # Convert coverage date format
        coverage_date_api = convert_date_format(coverage_date)

        # Prepare search parameters
        params = {
            "handler": "SearchPolicyHolders",
            "CoverageDate": coverage_date_api,
            "Fein": "",
            "EmployerName": employer_name,
            "StreetAddress": "",
            "City": "",
            "State": "",
            "ZipCode": zip_code,
        }

        url = "https://www.caworkcompcoverage.com/Search"

        log_step("API Search", "DEBUG", f"Request URL: {url}")
        log_step("API Search", "DEBUG", f"Request params: {params}")

        # Make the search request
        response = session.get(url, params=params)

        log_step(
            "API Search", "DEBUG", f"Response status: {response.status_code}"
        )
        log_step("API Search", "DEBUG", f"Response headers: {response.headers}")

        # Log response content snippet to avoid huge logs
        snippet = (
            response.text[:500] + "..."
            if len(response.text) > 500
            else response.text
        )
        log_step("API Search", "DEBUG", f"Response content snippet: {snippet}")

        if response.status_code != 200:
            log_step(
                "API Search",
                "ERROR",
                f"Search failed with status: {response.status_code}",
            )
            return None

        # Parse the HTML response
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract search results
        results = []

        # Find result rows
        result_rows = soup.find_all(
            "tr", class_=["result-row", "text-primary", "link-cursor"]
        )

        for row in result_rows:
            employer_data = row.get("data-employer")
            city_data = row.get("data-city")
            state_data = row.get("data-state")

            if employer_data:
                result = {
                    "employer_name": employer_data,
                    "city": city_data or "",
                    "state": state_data or "",
                    "row_html": str(row),
                }
                results.append(result)

        # Fallback extraction from table cells
        if not results:
            result_rows = soup.select("tr[data-employer]")
            for row in result_rows:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    result = {
                        "employer_name": cells[0].get_text(strip=True),
                        "city": cells[1].get_text(strip=True),
                        "state": cells[2].get_text(strip=True),
                        "row_html": str(row),
                    }
                    results.append(result)

        log_step("API Search", "SUCCESS", f"Found {len(results)} results")
        log_step("API Search", "DEBUG", f"Results: {results}")

        return results

    except Exception as e:
        log_step(
            "API Search", "ERROR", f"Exception occurred: {e}", exc_info=True
        )
        return None


def get_policy_details(session, employer, coverage_date):
    """Get detailed policy information for a specific employer"""
    log_step(
        "API Details",
        "INFO",
        f"Getting details for: {employer['employer_name']}",
    )

    try:
        # Convert coverage date format
        coverage_date_api = convert_date_format(coverage_date)

        # Prepare details parameters
        params = {
            "handler": "PolicyHolderDetails",
            "CoverageDate": coverage_date_api,
            "EmployerName": employer["employer_name"],
            "City": employer["city"],
            "State": employer["state"],
        }

        url = "https://www.caworkcompcoverage.com/Search"

        # Make the details request
        response = session.get(url, params=params)

        if response.status_code != 200:
            log_step(
                "API Details",
                "ERROR",
                f"Details request failed with status: {response.status_code}",
            )
            return None

        # Parse the HTML response
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract policy details from the table
        policy_data = {}

        # Find the details table
        details_table = soup.find(
            "table", class_=["table-borderless", "table", "border"]
        )

        if details_table:
            # Find the detail rows
            detail_rows = details_table.find_all("tr", class_="detail-row")

            for row in detail_rows:
                cells = row.find_all("td")
                if len(cells) >= 7:
                    policy_data = {
                        "employer_name": cells[0].get_text(strip=True),
                        "street_address": cells[1].get_text(strip=True),
                        "city": cells[2].get_text(strip=True),
                        "state": cells[3].get_text(strip=True),
                        "zip_code": cells[4].get_text(strip=True),
                        "insurer_name": cells[5].get_text(strip=True),
                        "fein": cells[6].get_text(strip=True),
                        "extracted_at": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                    }
                    break

        if policy_data:
            log_step(
                "API Details",
                "SUCCESS",
                f"Extracted details for: {employer['employer_name']}",
            )
        else:
            log_step(
                "API Details",
                "WARNING",
                f"No details found for: {employer['employer_name']}",
            )

        return policy_data

    except Exception as e:
        log_step("API Details", "ERROR", f"Error getting policy details: {e}")
        return None


def read_input_csv(file_path):
    """Read the input CSV file with employer data"""
    try:
        employers = []

        # First, let's detect the delimiter
        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            sample = csvfile.read(1024)
            csvfile.seek(0)

            # Try to detect delimiter
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter

            log_step("Read Input", "INFO", f"Detected delimiter: '{delimiter}'")

            # Read the CSV with detected delimiter
            reader = csv.DictReader(csvfile, delimiter=delimiter)

            for row in reader:
                # Clean up column names (remove BOM and extra spaces)
                cleaned_row = {
                    key.strip().replace("\ufeff", ""): value.strip()
                    for key, value in row.items()
                }

                employers.append(
                    {
                        "bureau_number": cleaned_row.get("Bureau Number", ""),
                        "employer_name": cleaned_row.get("Employer Name", ""),
                        "zip_code": cleaned_row.get("Zip Code", ""),
                        "coverage_date": cleaned_row.get("Coverage Date", ""),
                    }
                )

        log_step(
            "Read Input",
            "SUCCESS",
            f"Read {len(employers)} employers from {file_path}",
        )
        return employers
    except Exception as e:
        log_step("Read Input", "ERROR", f"Error reading input CSV: {e}")
        # Create a sample input file for the user
        create_sample_input()
        return []


def create_sample_input():
    """Create a sample input CSV file if none exists or there's an error"""
    sample_data = """Bureau Number,Employer Name,Zip Code,Coverage Date
42,BAXTER AUTO,97217,11/1/2025
270,MOORE TWININ,93716,11/1/2025
637,MORRIS SHAND,90021,11/1/2025
723,COTATI FOOD,94931,11/1/2025
1407,AV BATTERY M,90650,11/1/2025"""

    try:
        with open("sample_input.csv", "w", newline="", encoding="utf-8") as f:
            f.write(sample_data)
        log_step(
            "Create Sample",
            "INFO",
            "Created sample_input.csv with example data",
        )
    except Exception as e:
        log_step("Create Sample", "ERROR", f"Could not create sample file: {e}")


def load_progress():
    """Load progress tracking data"""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
            log_step(
                "Load Progress",
                "SUCCESS",
                f"Loaded progress: {len(progress.get('completed', []))} completed",
            )
            return progress
        else:
            log_step(
                "Load Progress",
                "INFO",
                "No progress file found, starting fresh",
            )
            return {"completed": [], "results": []}
    except Exception as e:
        log_step("Load Progress", "ERROR", f"Error loading progress: {e}")
        return {"completed": [], "results": []}


def save_progress(progress):
    """Save progress tracking data"""
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        log_step(
            "Save Progress",
            "SUCCESS",
            f"Progress saved: {len(progress.get('completed', []))} completed",
        )
        return True
    except Exception as e:
        log_step("Save Progress", "ERROR", f"Error saving progress: {e}")
        return False


def save_final_output(results, csv_file=OUTPUT_CSV, json_file=OUTPUT_JSON):
    """Save final results in CSV and JSON formats"""
    try:
        # Save CSV
        with open(csv_file, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "Bureau Number",
                "Employer Name",
                "Street Address",
                "City",
                "State",
                "Zip Code",
                "Insurer Name",
                "LookupStatus",
            ]
            writer = csv.DictWriter(
                csvfile, fieldnames=fieldnames, delimiter="\t"
            )
            writer.writeheader()
            for result in results:
                writer.writerow(
                    {
                        "Bureau Number": result["bureau_number"],
                        "Employer Name": result["employer_name"],
                        "Street Address": result["street_address"],
                        "City": result["city"],
                        "State": result["state"],
                        "Zip Code": result["zip_code"],
                        "Insurer Name": result["insurer_name"],
                        "LookupStatus": result["lookup_status"],
                    }
                )

        # Save JSON
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        log_step(
            "Save Output",
            "SUCCESS",
            f"Final output saved to {csv_file} and {json_file}",
        )
        return True
    except Exception as e:
        log_step("Save Output", "ERROR", f"Error saving final output: {e}")
        return False


def process_employer(session, employer_data, progress):
    """Process a single employer and return results"""
    bureau_number = employer_data["bureau_number"]
    employer_name = employer_data["employer_name"]
    zip_code = employer_data["zip_code"]
    coverage_date = employer_data["coverage_date"]

    log_step(
        "Process Employer",
        "INFO",
        f"Processing Bureau #{bureau_number}: {employer_name}",
    )

    # Search for policy holders
    search_results = search_policy_holders(
        session, employer_name, coverage_date, zip_code
    )

    if not search_results:
        # No results found
        result = {
            "bureau_number": bureau_number,
            "employer_name": employer_name,
            "street_address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "insurer_name": "",
            "fein": "",
            "lookup_status": "Not Found",
            "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return [result]

    # Get details for each search result
    all_results = []
    for search_result in search_results:
        details = get_policy_details(session, search_result, coverage_date)

        if details:
            result = {
                "bureau_number": bureau_number,
                "employer_name": details["employer_name"],
                "street_address": details["street_address"],
                "city": details["city"],
                "state": details["state"],
                "zip_code": details["zip_code"],
                "insurer_name": details["insurer_name"],
                "fein": details["fein"],
                "lookup_status": "Found",
                "extracted_at": details["extracted_at"],
            }
            all_results.append(result)
        else:
            # Found in search but couldn't get details
            result = {
                "bureau_number": bureau_number,
                "employer_name": search_result["employer_name"],
                "street_address": "",
                "city": search_result["city"],
                "state": search_result["state"],
                "zip_code": "",
                "insurer_name": "",
                "fein": "",
                "lookup_status": "Details Not Found",
                "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            all_results.append(result)

    return all_results


def execute_with_retry(
    step_name, step_function, max_retries=MAX_RETRIES, *args, **kwargs
):
    """Execute a step with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            log_step(step_name, "INFO", f"Attempt {attempt}/{max_retries}")
            result = step_function(*args, **kwargs)

            if result:
                log_step(
                    step_name,
                    "SUCCESS",
                    f"Completed successfully on attempt {attempt}",
                )
                return result
            else:
                log_step(step_name, "WARNING", f"Failed on attempt {attempt}")

        except Exception as e:
            log_step(step_name, "ERROR", f"Exception on attempt {attempt}: {e}")
            traceback.print_exc()

        if attempt < max_retries:
            log_step(
                step_name, "RETRY", f"Retrying in {RETRY_DELAY} seconds..."
            )
            time.sleep(RETRY_DELAY)

    log_step(step_name, "ERROR", f"Failed after {max_retries} attempts")
    return False


def main():
    # Configuration
    CONFIG = {
        "email_address": "abeselomsolomongetahun@gmail.com",
        "website_url": "https://www.caworkcompcoverage.com/Search",
    }

    # Check if input file exists
    if not os.path.exists(INPUT_CSV):
        log_step("Main", "ERROR", f"Input file {INPUT_CSV} not found!")
        create_sample_input()
        log_step(
            "Main",
            "INFO",
            "Created sample_input.csv. Please update it with your data and rename to input.csv",
        )
        return

    # Load progress and input data
    progress = load_progress()
    employers = read_input_csv(INPUT_CSV)

    if not employers:
        log_step("Main", "ERROR", "No employers to process")
        return

    # Filter out already completed employers
    pending_employers = [
        e for e in employers if e["bureau_number"] not in progress["completed"]
    ]

    if not pending_employers:
        log_step("Main", "SUCCESS", "All employers already processed!")
        # Still save final output with existing results
        save_final_output(progress["results"])
        return

    log_step(
        "Main",
        "INFO",
        f"Processing {len(pending_employers)} pending employers out of {len(employers)} total",
    )

    # Get authenticated session
    session = load_requests_session()

    if not session:
        log_step(
            "Session",
            "INFO",
            "No valid session found, starting manual authentication...",
        )

        # Use Selenium for manual authentication
        with SB(uc=True, headless=False) as sb:
            try:
                # Wait for user to manually complete authentication
                auth_success = wait_for_manual_authentication(
                    sb, CONFIG["email_address"], CONFIG["website_url"]
                )

                if auth_success:
                    # Convert cookies to requests session
                    session = convert_cookies_to_requests_session()
                    if session:
                        save_requests_session(session)
                        log_step(
                            "Session",
                            "SUCCESS",
                            "Session created from manual authentication",
                        )
                    else:
                        log_step(
                            "Session",
                            "ERROR",
                            "Failed to convert cookies to session",
                        )
                        return
                else:
                    log_step("Session", "ERROR", "Manual authentication failed")
                    return

            except Exception as e:
                log_step(
                    "Session",
                    "ERROR",
                    f"Error during manual authentication: {e}",
                )
                return

    if not session:
        log_step(
            "Session", "ERROR", "Failed to establish authenticated session"
        )
        return

    # Process pending employers
    total_processed = 0
    for employer in pending_employers:
        try:
            # Process employer
            employer_results = process_employer(session, employer, progress)

            # Add results to progress
            progress["results"].extend(employer_results)
            progress["completed"].append(employer["bureau_number"])

            # Save progress after each employer
            save_progress(progress)

            total_processed += 1

            # Print current status
            print(
                f"\n📊 Progress: {total_processed}/{len(pending_employers)} employers processed"
            )
            print(
                f"🏢 Bureau #{employer['bureau_number']}: {len(employer_results)} records found"
            )

            # Small delay to be respectful to the server
            time.sleep(1)

        except Exception as e:
            log_step(
                "Process Employer",
                "ERROR",
                f"Failed to process Bureau #{employer['bureau_number']}: {e}",
            )
            # Continue with next employer even if one fails

    # Save final output
    save_final_output(progress["results"])

    # Print final summary
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(
        f"📋 Total Employers Processed: {len(progress['completed'])}/{len(employers)}"
    )
    print(f"📄 Total Records Found: {len(progress['results'])}")
    print(f"💾 Output Files:")
    print(f"   - CSV: {OUTPUT_CSV}")
    print(f"   - JSON: {OUTPUT_JSON}")
    print(f"   - Progress: {PROGRESS_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    log_step("SCRIPT START", "INFO", "Starting employer data extraction...")
    main()
    log_step("SCRIPT END", "SUCCESS", "Extraction process completed!")
