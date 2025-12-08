import concurrent.futures
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
from threading import Lock
from urllib.parse import quote, urlencode

import requests
from bs4 import BeautifulSoup
from seleniumbase import SB

# File paths
COOKIE_FILE = "browser_cookies_fast.pkl"
REQUESTS_SESSION_FILE = "requests_session_fast.pkl"
PROGRESS_FILE = "progress_tracker_fast.json"
INPUT_CSV = "input_fast.csv"
OUTPUT_CSV = "final_output_fast.csv"
OUTPUT_JSON = "final_output_fast.json"

MAX_RETRIES = 2  # Reduced for speed
RETRY_DELAY = 1  # Reduced for speed

# Thread safety
progress_lock = Lock()


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
    """Convert Selenium cookies to requests session with optimizations"""
    try:
        if not os.path.exists(COOKIE_FILE):
            log_step("Convert Cookies", "ERROR", "No cookie file found")
            return None

        with open(COOKIE_FILE, "rb") as file:
            selenium_cookies = pickle.load(file)

        # Create session with connection pooling and timeouts
        session = requests.Session()

        # Optimized connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,  # Increase connection pool
            pool_maxsize=20,  # Increase max connections
            max_retries=2,  # Fewer retries for speed
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Optimized headers for speed
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
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


def automated_authentication(sb, website_url):
    """Fully automated authentication without manual intervention"""
    log_step(
        "Automated Authentication",
        "INFO",
        "Starting fully automated authentication...",
    )

    try:
        # Open the website with Undetectable Chrome
        log_step(
            "Automated Authentication",
            "INFO",
            "Opening website with stealth mode...",
        )
        sb.uc_open_with_reconnect(website_url, 5)

        # Wait for page to load
        sb.sleep(3)

        # Check if we're already on the search page (cookies might still be valid)
        current_url = sb.get_current_url()
        # if "Search" in current_url:
        #     log_step(
        #         "Automated Authentication",
        #         "SUCCESS",
        #         "Already authenticated with existing session",
        #     )
        #     return True

        # Handle Cloudflare challenge if present
        log_step(
            "Automated Authentication",
            "INFO",
            "Checking for Cloudflare challenge...",
        )
        page_source = sb.get_page_source().lower()

        if "cloudflare" in page_source or "challenge" in page_source:
            log_step(
                "Automated Authentication",
                "INFO",
                "Cloudflare detected, waiting for automatic bypass...",
            )
            # Wait for Cloudflare to be bypassed automatically by undetectable-chromedriver
            sb.sleep(10)

            # Check if we're still on challenge page
            current_url = sb.get_current_url()
            if "challenge" in current_url.lower():
                log_step(
                    "Automated Authentication",
                    "WARNING",
                    "Cloudflare challenge may need manual intervention",
                )
                # Try to reload and wait longer
                sb.driver.refresh()
                sb.sleep(15)

        # Check for disclaimer modal and accept it
        log_step(
            "Automated Authentication",
            "INFO",
            "Checking for disclaimer modal...",
        )
        try:
            # Try multiple possible selectors for the accept button
            accept_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:contains('Accept')",
                "button:contains('Agree')",
                "input[value='Accept']",
                "input[value='Agree']",
                ".btn-primary",
                ".btn-success",
                "button.btn",
            ]

            for selector in accept_selectors:
                if sb.is_element_visible(selector):
                    sb.click(selector)
                    log_step(
                        "Automated Authentication",
                        "SUCCESS",
                        f"Accepted disclaimer using selector: {selector}",
                    )
                    sb.sleep(2)
                    break
        except Exception as e:
            log_step(
                "Automated Authentication",
                "INFO",
                f"No disclaimer found or already accepted: {e}",
            )

        # Handle OTP page if it appears
        log_step(
            "Automated Authentication",
            "INFO",
            "Checking for OTP verification...",
        )
        page_source = sb.get_page_source().lower()

        if "one time passcode" in page_source or "otp" in page_source:
            log_step(
                "Automated Authentication",
                "INFO",
                "OTP page detected, attempting to handle...",
            )

            # Look for email input and submit (assuming email is pre-filled or not required)
            try:
                # Try to find and click submit/continue button
                submit_selectors = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button:contains('Submit')",
                    "button:contains('Continue')",
                    "button:contains('Send')",
                    ".btn-primary",
                    ".btn-success",
                ]

                for selector in submit_selectors:
                    if sb.is_element_visible(selector):
                        sb.click(selector)
                        log_step(
                            "Automated Authentication",
                            "SUCCESS",
                            f"Submitted OTP form using: {selector}",
                        )
                        sb.sleep(3)
                        break
            except Exception as e:
                log_step(
                    "Automated Authentication",
                    "WARNING",
                    f"Could not auto-submit OTP: {e}",
                )

        # Wait for final search page
        log_step(
            "Automated Authentication", "INFO", "Waiting for search page..."
        )

        # Wait for search elements to appear
        search_indicators = [
            "#employerName",
            "#coverageDate",
            'input[name*="search"]',
            'input[type*="search"]',
            "#Search",
        ]

        authenticated = False
        max_wait_time = 30
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            for indicator in search_indicators:
                if sb.is_element_visible(indicator):
                    log_step(
                        "Automated Authentication",
                        "SUCCESS",
                        f"Found search element: {indicator}",
                    )
                    authenticated = True
                    break
            if authenticated:
                break
            sb.sleep(2)

        if authenticated:
            # Save cookies for future use
            save_cookies(sb)
            log_step(
                "Automated Authentication",
                "SUCCESS",
                "Automated authentication completed successfully",
            )
            return True
        else:
            log_step(
                "Automated Authentication",
                "ERROR",
                "Could not reach search page after automated authentication",
            )
            return False

    except Exception as e:
        log_step(
            "Automated Authentication",
            "ERROR",
            f"Error during automated authentication: {e}",
        )
        # Try to save cookies anyway in case we got some useful ones
        try:
            save_cookies(sb)
        except:
            pass
        return False


def convert_date_format(date_str):
    """Convert date from mm/dd/yyyy to yyyy-mm-dd for API requests"""
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError as e:
        log_step("Date Conversion", "ERROR", f"Date conversion error: {e}")
        return date_str


def search_policy_holders_optimized(
    session, employer_name, coverage_date, zip_code, timeout=10
):
    """Optimized search for policy holders with timeout and faster parsing"""
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

        # Make the search request with timeout
        response = session.get(url, params=params, timeout=timeout)

        if response.status_code != 200:
            log_step(
                "API Search",
                "ERROR",
                f"Search failed with status: {response.status_code}",
            )
            return None

        # Parse the HTML response with lxml for speed
        soup = BeautifulSoup(response.text, "lxml")

        # Extract search results
        results = []

        # Find result rows
        result_rows = soup.find_all(
            "tr",
            class_=lambda x: x
            and any(
                cls in x
                for cls in ["result-row", "text-primary", "link-cursor"]
            ),
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
                    }
                    results.append(result)

        log_step("API Search", "SUCCESS", f"Found {len(results)} results")
        return results

    except requests.exceptions.Timeout:
        log_step(
            "API Search", "ERROR", f"Timeout searching for: {employer_name}"
        )
        return None
    except Exception as e:
        log_step("API Search", "ERROR", f"Exception occurred: {e}")
        return None


def get_policy_details_optimized(session, employer, coverage_date, timeout=10):
    """Optimized get detailed policy information with timeout"""
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

        # Make the details request with timeout
        response = session.get(url, params=params, timeout=timeout)

        if response.status_code != 200:
            log_step(
                "API Details",
                "ERROR",
                f"Details request failed with status: {response.status_code}",
            )
            return None

        # Parse the HTML response with lxml for speed
        soup = BeautifulSoup(response.text, "lxml")

        # Extract policy details from the table
        policy_data = {}

        # Find the details table
        details_table = soup.find(
            "table",
            class_=lambda x: x
            and any(
                cls in x for cls in ["table-borderless", "table", "border"]
            ),
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

    except requests.exceptions.Timeout:
        log_step(
            "API Details",
            "ERROR",
            f"Timeout getting details for: {employer['employer_name']}",
        )
        return None
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


def batch_save_progress(progress, force=False, batch_size=10):
    """Save progress less frequently to reduce I/O overhead"""
    if force or len(progress["completed"]) % batch_size == 0:
        return save_progress(progress)
    return True


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


def process_employer(session, employer_data):
    """Process a single employer and return results"""
    bureau_number = employer_data["bureau_number"]
    employer_name = employer_data["employer_name"]
    zip_code = employer_data["zip_code"]
    coverage_date = employer_data["coverage_date"]

    # Search for policy holders
    search_results = search_policy_holders_optimized(
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
        details = get_policy_details_optimized(
            session, search_result, coverage_date
        )

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


def process_employer_threadsafe(session, employer_data, progress):
    """Thread-safe version of process_employer"""
    try:
        employer_results = process_employer(session, employer_data)

        with progress_lock:
            progress["results"].extend(employer_results)
            progress["completed"].append(employer_data["bureau_number"])
            batch_save_progress(progress)

        return employer_results
    except Exception as e:
        log_step(
            "Process Employer",
            "ERROR",
            f"Thread error for Bureau #{employer_data['bureau_number']}: {e}",
        )
        return []


def process_employers_concurrent(session, employers, progress, max_workers=10):
    """Process multiple employers concurrently"""
    completed_count = 0
    total_employers = len(employers)

    log_step(
        "Concurrent Processing",
        "INFO",
        f"Starting {max_workers} workers for {total_employers} employers",
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers
    ) as executor:
        # Submit all tasks
        future_to_employer = {
            executor.submit(
                process_employer_threadsafe, session, employer, progress
            ): employer
            for employer in employers
        }

        # Process completed tasks as they finish
        for future in concurrent.futures.as_completed(future_to_employer):
            employer = future_to_employer[future]
            try:
                results = future.result()
                completed_count += 1
                log_step(
                    "Concurrent Processing",
                    "SUCCESS",
                    f"Progress: {completed_count}/{total_employers} - Bureau #{employer['bureau_number']}: {len(results)} records",
                )
            except Exception as e:
                completed_count += 1
                log_step(
                    "Concurrent Processing",
                    "ERROR",
                    f"Progress: {completed_count}/{total_employers} - Bureau #{employer['bureau_number']} failed: {e}",
                )

    return completed_count


def monitor_session_health(session):
    """Check if session is still valid"""
    try:
        test_url = "https://www.caworkcompcoverage.com/Search"
        response = session.get(test_url, timeout=5)
        return response.status_code == 200
    except:
        return False


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

        if attempt < max_retries:
            log_step(
                step_name, "RETRY", f"Retrying in {RETRY_DELAY} seconds..."
            )
            time.sleep(RETRY_DELAY)

    log_step(step_name, "ERROR", f"Failed after {max_retries} attempts")
    return False


def main():
    # Configuration with optimized settings
    CONFIG = {
        "website_url": "https://www.caworkcompcoverage.com/Search",
        "max_workers": 15,  # Adjust based on server tolerance
        "request_timeout": 10,
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
    pending_employers = read_input_csv(INPUT_CSV)

    # if not employers:
    #     log_step("Main", "ERROR", "No employers to process")
    #     return
    #
    # # Filter out already completed employers
    # pending_employers = [
    #     e for e in employers if e["bureau_number"] not in progress["completed"]
    # ]
    #
    if not pending_employers:
        log_step("Main", "SUCCESS", "All employers already processed!")
        # Still save final output with existing results
        save_final_output(progress["results"])
        return

    log_step(
        "Main",
        "INFO",
        f"Processing {len(pending_employers)} pending employers out of {len(pending_employers)} total",
    )

    # Try to load existing session first
    session = load_requests_session()

    if not session:
        log_step(
            "Session", "INFO", "No session file found, checking for cookies..."
        )

        # Check if we have cookies from previous authentication
        if os.path.exists(COOKIE_FILE):
            log_step(
                "Session",
                "INFO",
                "Found existing cookies, converting to session...",
            )
            session = convert_cookies_to_requests_session()
            if session:
                save_requests_session(session)
                log_step(
                    "Session",
                    "SUCCESS",
                    "Session created from existing cookies",
                )
            else:
                log_step(
                    "Session", "ERROR", "Failed to convert cookies to session"
                )
                # Continue to automated authentication

    # If still no session, try automated authentication
    if not session:
        log_step(
            "Session",
            "INFO",
            "No valid session found, starting automated authentication...",
        )

        # Use Selenium for automated authentication
        with SB(uc=True, headless=False) as sb:
            try:
                # Perform fully automated authentication
                auth_success = automated_authentication(
                    sb, CONFIG["website_url"]
                )

                if auth_success:
                    # Convert cookies to requests session
                    session = convert_cookies_to_requests_session()
                    if session:
                        save_requests_session(session)
                        log_step(
                            "Session",
                            "SUCCESS",
                            "Session created from automated authentication",
                        )
                    else:
                        log_step(
                            "Session",
                            "ERROR",
                            "Failed to convert cookies to session",
                        )
                        return
                else:
                    log_step(
                        "Session", "ERROR", "Automated authentication failed"
                    )
                    return

            except Exception as e:
                log_step(
                    "Session",
                    "ERROR",
                    f"Error during automated authentication: {e}",
                )
                return

    if not session:
        log_step(
            "Session", "ERROR", "Failed to establish authenticated session"
        )
        return

    # Check session health before starting
    if not monitor_session_health(session):
        log_step("Session", "ERROR", "Session is no longer valid")
        return

    # Start concurrent processing with timing
    start_time = time.time()

    completed_count = process_employers_concurrent(
        session, pending_employers, progress, max_workers=CONFIG["max_workers"]
    )

    end_time = time.time()
    total_time = end_time - start_time

    # Force final progress save
    batch_save_progress(progress, force=True)

    # Save final output
    save_final_output(progress["results"])

    # Print performance summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    print(
        f"📊 Total Employers Processed: {completed_count}/{len(pending_employers)}"
    )
    print(f"⏱️  Total Time: {total_time:.2f} seconds")
    print(
        f"🚀 Average Time per Employer: {total_time/max(completed_count, 1):.2f} seconds"
    )
    print(
        f"📈 Processing Rate: {completed_count/total_time*60:.2f} employers/minute"
    )
    print(f"💾 Total Records Found: {len(progress['results'])}")
    print(f"💾 Output Files:")
    print(f"   - CSV: {OUTPUT_CSV}")
    print(f"   - JSON: {OUTPUT_JSON}")
    print("=" * 60)


if __name__ == "__main__":
    log_step(
        "SCRIPT START",
        "INFO",
        "Starting fully automated employer data extraction...",
    )
    main()
    log_step("SCRIPT END", "SUCCESS", "Extraction process completed!")
