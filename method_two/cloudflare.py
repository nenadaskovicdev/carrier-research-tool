import base64
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
from threading import Lock
from urllib.parse import quote, urlencode

import requests
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

# ==========================================================
# CONFIG
# ==========================================================
EMAIL_ADDRESS = "zubetsko@gmail.com"
URL = "https://www.caworkcompcoverage.com/Search"
CREDENTIALS_FILE = "credentials.json"
TOKEN_PICKLE = "token.pickle"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
INPUT_CSV = "input_fast.csv"
OUTPUT_CSV = "final_output_fast_1.csv"
OUTPUT_JSON = "final_output_fast_1.json"
COOKIE_FILE = "browser_cookies_fast_1.pkl"
REQUESTS_SESSION_FILE = "requests_session_fast_1.pkl"
PROGRESS_FILE = "progress_tracker_fast_1.json"
REQUEST_LOG_FILE = "request_logs_1.jsonl"
DEBUG_DIR = "debug_logs"
MAX_RETRIES = 3
RETRY_DELAY = 2

# Thread safety
progress_lock = Lock()
log_lock = Lock()

# Global driver instance
driver_instance = None
driver_lock = Lock()

# Create debug directory
os.makedirs(DEBUG_DIR, exist_ok=True)


# ==========================================================
# LOGGING FUNCTIONS
# ==========================================================
def log_step(step_name, status="INFO", message=""):
    """Log step execution with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status_icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️",
        "RETRY": "🔄",
        "DEBUG": "🔍",
    }
    icon = status_icons.get(status, "🔸")
    log_message = f"{timestamp} {icon} [{status}] {step_name}: {message}"
    print(log_message)
    
    # Also write to a log file
    with open(os.path.join(DEBUG_DIR, "execution_log.txt"), "a", encoding="utf-8") as f:
        f.write(log_message + "\n")


def log_request_response(session_id, request_type, url, params=None, 
                        status_code=None, response_text=None, error=None):
    """Log HTTP requests and responses for debugging"""
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "session_id": session_id,
        "type": request_type,
        "url": url,
        "params": params,
        "status_code": status_code,
        "response_length": len(response_text) if response_text else 0,
        "error": str(error) if error else None,
        "has_otp_modal": "one-time passcode" in (response_text or "").lower(),
        "has_session_error": any(indicator in (response_text or "").lower() 
                                for indicator in ["invalid session", "session expired", "login"]),
    }
    
    # Save response text to separate file if it contains useful data
    if response_text and (status_code != 200 or "one-time passcode" in response_text.lower()):
        filename = f"{timestamp.replace(':', '-').replace('.', '-')}_{request_type}_{status_code}.html"
        with open(os.path.join(DEBUG_DIR, filename), "w", encoding="utf-8") as f:
            f.write(response_text)
        log_entry["response_file"] = filename
    
    # Write to JSONL file
    with log_lock:
        with open(REQUEST_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    # Also log to console if it's interesting
    if status_code == 400 or error or "one-time passcode" in (response_text or "").lower():
        log_step(f"HTTP {request_type}", "DEBUG", 
                f"URL: {url}, Status: {status_code}, "
                f"Params: {params}, Error: {error}")


# ==========================================================
# IMPROVED GMAIL API OTP FUNCTIONS
# ==========================================================
def gmail_service():
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE, "wb") as token:
            pickle.dump(creds, token)
    return build("gmail", "v1", credentials=creds)


def decode_email_body(data):
    """Decode email body from base64 or quoted-printable"""
    if not data:
        return ""

    try:
        # Try base64 decode first
        decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8")
        return decoded
    except:
        try:
            # Try quoted-printable decode
            decoded = quopri.decodestring(data).decode("utf-8")
            return decoded
        except:
            # Return as-is
            return data


def extract_otp_from_email(payload):
    """Extract text content from email payload and find OTP"""
    text_content = ""

    # Process the payload
    if "parts" in payload:
        for part in payload["parts"]:
            if (
                part["mimeType"] == "text/plain"
                or part["mimeType"] == "text/html"
            ):
                if "body" in part and "data" in part["body"]:
                    body_data = part["body"]["data"]
                    decoded = decode_email_body(body_data)
                    text_content += decoded + "\n"
    elif "body" in payload and "data" in payload["body"]:
        # Single part email
        body_data = payload["body"]["data"]
        decoded = decode_email_body(body_data)
        text_content = decoded

    # Clean up the text content
    text_content = text_content.replace("\r\n", "\n").replace("\r", "\n")

    # Debug: Save the email content to a file
    email_debug_file = os.path.join(DEBUG_DIR, f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(email_debug_file, "w", encoding="utf-8") as f:
        f.write(text_content)

    log_step("OTP Extraction", "DEBUG", f"Email saved to {email_debug_file}")

    # Try multiple patterns to find OTP
    patterns = [
        r"Your One-Time Passcode is:\s*(\d{6})",
        r"One-Time Passcode:\s*(\d{6})",
        r"passcode.*?:\s*(\d{6})",
        r"Passcode.*?:\s*(\d{6})",
        r"code.*?:\s*(\d{6})",
        r"OTP.*?:\s*(\d{6})",
        r"\b(\d{6})\b(?!.*\d)",  # Any 6-digit number at the end
    ]

    for pattern in patterns:
        match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
        if match:
            otp = match.group(1)
            log_step("OTP Extraction", "SUCCESS", f"Found OTP using pattern '{pattern}': {otp}")
            return otp

    # If no pattern matched, look for any 6-digit number
    all_numbers = re.findall(r"\b(\d{6})\b", text_content)
    if all_numbers:
        # Take the last 6-digit number (often the OTP is at the end)
        otp = all_numbers[-1]
        log_step("OTP Extraction", "WARNING", f"Found potential OTP (last 6-digit number): {otp}")
        return otp

    log_step("OTP Extraction", "ERROR", "No OTP found in email content")
    return None


def get_latest_otp():
    """Get the latest OTP from WCIRB emails"""
    service = gmail_service()

    start_time = time.time()
    max_wait_time = 300  # 5 minutes

    log_step("OTP Retrieval", "INFO", "Starting to search for OTP emails...")

    while time.time() - start_time < max_wait_time:
        try:
            # Search for WCIRB emails
            query = f"from:caworkcompcoverage@wcirb.com to:{EMAIL_ADDRESS} subject:Here's the one-time passcode you requested for Workers' Compensation Coverage Inquiry"
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=5)
                .execute()
            )

            messages = results.get("messages", [])

            if not messages:
                log_step("OTP Retrieval", "INFO", 
                        f"No OTP emails found yet, waiting... ({int(max_wait_time - (time.time() - start_time))}s remaining)")
                time.sleep(10)
                continue

            # Get the latest message
            latest_msg_id = messages[0]["id"]
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=latest_msg_id, format="full")
                .execute()
            )

            # Check if email is recent (within last 5 minutes)
            msg_date = int(msg["internalDate"]) / 1000  # Convert to seconds
            current_time = time.time()

            if current_time - msg_date > 300:  # Older than 5 minutes
                log_step("OTP Retrieval", "INFO", 
                        f"Email is too old ({int(current_time - msg_date)}s), waiting for new one...")
                time.sleep(5)
                continue

            # Extract OTP from email
            otp = extract_otp_from_email(msg["payload"])

            if otp:
                # Verify it's a valid 6-digit number
                if re.match(r"^\d{6}$", otp):
                    log_step("OTP Retrieval", "SUCCESS", f"Valid OTP found: {otp}")
                    return otp
                else:
                    log_step("OTP Retrieval", "ERROR", f"Invalid OTP format: {otp}")

            time.sleep(5)

        except Exception as e:
            log_step("OTP Retrieval", "ERROR", f"Error searching for OTP: {e}")
            traceback.print_exc()
            time.sleep(5)

    log_step("OTP Retrieval", "ERROR", "Timeout waiting for OTP")
    return None


# ==========================================================
# OTP AUTOMATION FUNCTIONS
# ==========================================================
def find_and_click_element(driver, selectors, by=By.CSS_SELECTOR, timeout=10, description=""):
    """Find and click an element from a list of selectors"""
    for selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            if element.is_displayed() and element.is_enabled():
                element.click()
                log_step("Element Click", "DEBUG", f"Clicked {description}: {selector}")
                return True
        except Exception as e:
            continue
    log_step("Element Click", "WARNING", f"Could not click {description} with any selector")
    return False


def find_and_fill_element(
    driver, selectors, text, by=By.CSS_SELECTOR, timeout=10, description=""
):
    """Find an element and fill it with text"""
    for selector in selectors:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            if element.is_displayed() and element.is_enabled():
                element.clear()
                element.send_keys(text)
                log_step("Element Fill", "DEBUG", f"Filled {text} in {description}: {selector}")
                return True
        except Exception as e:
            continue
    log_step("Element Fill", "WARNING", f"Could not fill {description} with any selector")
    return False


def handle_otp_modal_automatically(driver):
    """
    Automatically handles the OTP modal with improved error handling and debugging
    """
    log_step("OTP Automation", "INFO", "Starting automatic OTP handling...")

    try:
        # First, save the current page source for debugging
        debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        page_source_file = os.path.join(DEBUG_DIR, f"page_before_otp_{debug_timestamp}.html")
        with open(page_source_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # Take a screenshot
        screenshot_file = os.path.join(DEBUG_DIR, f"before_otp_modal_{debug_timestamp}.png")
        driver.save_screenshot(screenshot_file)
        
        log_step("OTP Automation", "DEBUG", f"Saved page source to {page_source_file}")
        log_step("OTP Automation", "DEBUG", f"Saved screenshot to {screenshot_file}")
        
        # Check page source for OTP indicators
        page_source = driver.page_source.lower()
        log_step("OTP Automation", "DEBUG", f"Page source length: {len(page_source)} chars")
        
        otp_indicators = [
            "one-time passcode",
            "otp",
            "passcode",
            "verification code",
            "verification",
            "enter code",
            "enter the code"
        ]
        
        found_indicators = []
        for indicator in otp_indicators:
            if indicator in page_source:
                found_indicators.append(indicator)
        
        if not found_indicators:
            log_step("OTP Automation", "INFO", "No OTP indicators found in page source")
            # Check if we're already logged in
            if "search" in driver.current_url.lower():
                log_step("OTP Automation", "SUCCESS", "Already on search page, OTP not needed")
                return True
            else:
                log_step("OTP Automation", "WARNING", "Not on search page but no OTP indicators found")
                return False
        
        log_step("OTP Automation", "INFO", f"OTP modal detected with indicators: {found_indicators}")
        
        # Try multiple approaches to find the email field
        log_step("OTP Automation", "DEBUG", "Looking for email field...")
        
        email_selectors = [
            "#emailAddress",
            "input[type='email']",
            "input[name='email']",
            "input[placeholder*='email']",
            "input[placeholder*='Email']",
            "input[id*='email']",
            "input[name*='email']",
        ]
        
        email_field = None
        for selector in email_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        email_field = element
                        log_step("OTP Automation", "DEBUG", f"Found email field: {selector}")
                        break
                if email_field:
                    break
            except:
                continue
        
        if email_field:
            try:
                # Clear and fill email
                current_value = email_field.get_attribute("value")
                if current_value and current_value.strip():
                    log_step("OTP Automation", "DEBUG", f"Email field already has value: {current_value}")
                else:
                    email_field.clear()
                    email_field.send_keys(EMAIL_ADDRESS)
                    log_step("OTP Automation", "DEBUG", f"Filled email: {EMAIL_ADDRESS}")
                time.sleep(1)
            except Exception as e:
                log_step("OTP Automation", "ERROR", f"Error filling email: {e}")
        else:
            log_step("OTP Automation", "WARNING", "Could not find email field, might already be filled")
        
        # Look for request OTP button
        log_step("OTP Automation", "DEBUG", "Looking for request OTP button...")
        
        request_btn_selectors = [
            "#btnRequestOTP",
            "button[type='submit']",
            "input[type='submit']",
            ".btn-primary",
            "button.btn",
            "button:contains('Request')",
            "button:contains('Send')",
            "button:contains('Get Code')",
            "button:contains('Get OTP')",
            "button:contains('Request OTP')",
        ]
        
        otp_requested = False
        for selector in request_btn_selectors:
            if "contains" in selector:
                # Handle text-based search
                try:
                    text_to_find = selector.split('contains(')[1].split(')')[0].lower()
                    elements = driver.find_elements(By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text_to_find}')]")
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            log_step("OTP Automation", "DEBUG", f"Clicking request button (text): {text_to_find}")
                            element.click()
                            otp_requested = True
                            time.sleep(3)  # Wait for OTP to be sent
                            break
                    if otp_requested:
                        break
                except:
                    continue
            else:
                # Handle CSS selector
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            log_step("OTP Automation", "DEBUG", f"Clicking request button: {selector}")
                            element.click()
                            otp_requested = True
                            time.sleep(3)  # Wait for OTP to be sent
                            break
                    if otp_requested:
                        break
                except:
                    continue
        
        if not otp_requested:
            log_step("OTP Automation", "ERROR", "Could not find/click request OTP button")
            # Save screenshot for debugging
            driver.save_screenshot(os.path.join(DEBUG_DIR, "no_request_button.png"))
            return False
        
        # Wait for OTP input to appear
        log_step("OTP Automation", "DEBUG", "Waiting for OTP input field...")
        time.sleep(5)  # Wait longer for email to be sent
        
        # Find OTP input field
        otp_input_selectors = [
            "#oneTimePasscode",
            "input[name='oneTimePasscode']",
            "input[name='otp']",
            "input[type='text'][placeholder*='code']",
            "input[placeholder*='OTP']",
            "input[placeholder*='Passcode']",
            "input[placeholder*='Verification']",
            "input[type='tel']",
            "input[inputmode='numeric']",
        ]
        
        otp_input = None
        for selector in otp_input_selectors:
            try:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if element.is_displayed() and element.is_enabled():
                    otp_input = element
                    log_step("OTP Automation", "DEBUG", f"Found OTP input: {selector}")
                    break
            except:
                continue
        
        if not otp_input:
            log_step("OTP Automation", "ERROR", "Could not find OTP input field after waiting")
            # Take screenshot for debugging
            driver.save_screenshot(os.path.join(DEBUG_DIR, "otp_input_error.png"))
            # Save page source
            with open(os.path.join(DEBUG_DIR, "page_no_otp_input.html"), "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False
        
        # Get OTP from Gmail
        log_step("OTP Automation", "INFO", "Retrieving OTP from Gmail...")
        otp = get_latest_otp()
        
        if not otp:
            log_step("OTP Automation", "ERROR", "Failed to retrieve OTP from Gmail")
            # Try to manually extract OTP from email content
            try:
                email_files = [f for f in os.listdir(DEBUG_DIR) if f.startswith("email_")]
                if email_files:
                    latest_email = max(email_files)
                    with open(os.path.join(DEBUG_DIR, latest_email), "r", encoding="utf-8") as f:
                        email_content = f.read()
                    # Look for 6-digit number
                    numbers = re.findall(r'\b\d{6}\b', email_content)
                    if numbers:
                        otp = numbers[-1]
                        log_step("OTP Automation", "WARNING", f"Found OTP in saved email: {otp}")
                    else:
                        log_step("OTP Automation", "ERROR", "No 6-digit number found in saved email")
                        return False
                else:
                    log_step("OTP Automation", "ERROR", "No saved email files found")
                    return False
            except Exception as e:
                log_step("OTP Automation", "ERROR", f"Could not read saved email file: {e}")
                return False
        
        # Fill OTP
        try:
            otp_input.clear()
            otp_input.send_keys(otp)
            log_step("OTP Automation", "DEBUG", f"Filled OTP: {otp}")
            time.sleep(1)
        except Exception as e:
            log_step("OTP Automation", "ERROR", f"Error filling OTP: {e}")
            return False
        
        # Click submit button
        log_step("OTP Automation", "DEBUG", "Looking for submit button...")
        
        submit_btn_selectors = [
            "#btnSubmitOTP",
            "button[type='submit']",
            "input[type='submit']",
            ".btn-success",
            "button.btn-primary",
            "button:contains('Submit')",
            "button:contains('Verify')",
            "button:contains('Continue')",
            "button:contains('Confirm')",
        ]
        
        submit_clicked = False
        for selector in submit_btn_selectors:
            if "contains" in selector:
                # Handle text-based search
                try:
                    text_to_find = selector.split('contains(')[1].split(')')[0].lower()
                    elements = driver.find_elements(By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text_to_find}')]")
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            log_step("OTP Automation", "DEBUG", f"Clicking submit button (text): {text_to_find}")
                            element.click()
                            submit_clicked = True
                            break
                    if submit_clicked:
                        break
                except:
                    continue
            else:
                # Handle CSS selector
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            log_step("OTP Automation", "DEBUG", f"Clicking submit button: {selector}")
                            element.click()
                            submit_clicked = True
                            break
                    if submit_clicked:
                        break
                except:
                    continue
        
        if not submit_clicked:
            log_step("OTP Automation", "WARNING", "Could not find submit button, trying to submit form")
            # Try pressing Enter in OTP field
            try:
                otp_input.send_keys(Keys.RETURN)
                log_step("OTP Automation", "DEBUG", "Pressed Enter in OTP field")
                submit_clicked = True
            except:
                log_step("OTP Automation", "ERROR", "Could not press Enter")
        
        # Wait for submission to complete
        log_step("OTP Automation", "DEBUG", "Waiting for OTP verification...")
        time.sleep(5)
        
        # Check if we're redirected to search page
        current_url = driver.current_url.lower()
        if "search" in current_url:
            log_step("OTP Automation", "SUCCESS", "Successfully redirected to search page")
            return True
        
        # Check if modal is gone
        try:
            WebDriverWait(driver, 10).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, ".modal-content")
                )
            )
            log_step("OTP Automation", "SUCCESS", "OTP modal closed successfully")
            return True
        except:
            log_step("OTP Automation", "WARNING", "Modal might still be visible")
        
        # Check for error messages
        error_selectors = [
            ".text-danger",
            ".error-message",
            ".alert-danger",
            "[class*='error']",
            "[class*='danger']",
        ]
        
        for selector in error_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        error_text = element.text
                        if error_text:
                            log_step("OTP Automation", "ERROR", f"Error message: {error_text}")
                            break
            except:
                continue
        
        # Final check - if we see search form elements, we're good
        search_indicators = [
            "input[name='EmployerName']",
            "input[placeholder*='Employer']",
            "#searchForm",
            "form[action*='Search']",
        ]
        
        for selector in search_indicators:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    log_step("OTP Automation", "SUCCESS", f"Found search element: {selector}, OTP successful")
                    return True
            except:
                continue
        
        log_step("OTP Automation", "WARNING", "OTP verification status uncertain")
        # Save final state for debugging
        driver.save_screenshot(os.path.join(DEBUG_DIR, "after_otp_attempt.png"))
        with open(os.path.join(DEBUG_DIR, "page_after_otp.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        return False  # Assume failure

    except Exception as e:
        log_step("OTP Automation", "ERROR", f"Exception in OTP automation: {str(e)}")
        traceback.print_exc()
        # Take screenshot
        driver.save_screenshot(os.path.join(DEBUG_DIR, "otp_automation_error.png"))
        # Save page source
        with open(os.path.join(DEBUG_DIR, "page_otp_error.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return False


def handle_cat_chat_disclaimer(driver):
    """
    Wait for user to manually handle Cat Chat/Disclaimer
    """
    log_step("Disclaimer", "WARNING", "CAT CHAT / DISCLAIMER DETECTED!")
    
    # Save the disclaimer page for debugging
    with open(os.path.join(DEBUG_DIR, "disclaimer_page.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    driver.save_screenshot(os.path.join(DEBUG_DIR, "disclaimer_page.png"))
    
    log_step("Disclaimer", "INFO", "Please manually:")
    log_step("Disclaimer", "INFO", "1. Read and accept the disclaimer/Cat Chat")
    log_step("Disclaimer", "INFO", "2. Complete any CAPTCHA if required")
    log_step("Disclaimer", "INFO", "3. Click 'Accept', 'Agree', or similar button")
    
    # Wait for user to complete
    input("\nPress ENTER after you've completed the CAPTCHA and accepted the disclaimer...")
    
    # Wait a moment for page to update
    time.sleep(3)
    
    log_step("Disclaimer", "SUCCESS", "Disclaimer handled manually")
    return True


# ==========================================================
# SIMPLIFIED BROWSER MANAGEMENT
# ==========================================================
def create_browser_instance():
    """Create a new browser instance"""
    log_step("Browser", "INFO", "Creating new browser instance...")
    try:
        driver = Driver(
            uc=True, 
            headless=False,
            chromium_arg="--ozone-platform=x11"
            # Add more options to mimic real browser
        )
        return driver
    except Exception as e:
        log_step("Browser", "ERROR", f"Failed to create browser instance: {str(e)}")
        traceback.print_exc()
        return None


def perform_full_authentication(driver):
    """Perform full authentication process"""
    log_step("Authentication", "INFO", "Starting authentication...")
    
    try:
        # Navigate to the URL
        driver.get(URL)
        
        # Wait for page load
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        log_step("Authentication", "INFO", "Page loaded, checking for disclaimer...")
        
        # Check for disclaimer
        page_source = driver.page_source.lower()
        
        # Always check for and handle disclaimer first
        disclaimer_keywords = ["disclaimer", "cat chat", "terms of use", "please read", "by clicking"]
        has_disclaimer = any(keyword in page_source for keyword in disclaimer_keywords)
        
        if has_disclaimer:
            log_step("Authentication", "INFO", "Disclaimer detected, waiting for user...")
            handle_cat_chat_disclaimer(driver)
        else:
            log_step("Authentication", "DEBUG", "No disclaimer found")
        
        # Now check for OTP
        log_step("Authentication", "INFO", "Checking for OTP modal...")
        time.sleep(3)
        
        # Try to handle OTP automatically
        otp_success = handle_otp_modal_automatically(driver)
        
        if otp_success:
            log_step("Authentication", "SUCCESS", "Authentication completed successfully")
            # Wait a bit for session to stabilize
            time.sleep(3)
            return True
        else:
            # Check if we're on search page anyway
            current_url = driver.current_url.lower()
            if "search" in current_url:
                log_step("Authentication", "SUCCESS", "Already on search page")
                return True
            log_step("Authentication", "WARNING", "OTP handling may have failed")
            return False
            
    except Exception as e:
        log_step("Authentication", "ERROR", f"Authentication failed: {str(e)}")
        traceback.print_exc()
        return False


def initialize_browser():
    """Initialize browser with authentication"""
    global driver_instance

    with driver_lock:
        if driver_instance is None:
            log_step("Browser", "INFO", "Initializing browser...")
            
            # Create new browser instance
            driver_instance = create_browser_instance()
            if not driver_instance:
                log_step("Browser", "ERROR", "Failed to create browser instance")
                return None
            
            # Perform authentication
            auth_success = perform_full_authentication(driver_instance)
            
            if auth_success:
                # Save cookies
                save_cookies(driver_instance)
                log_step("Browser", "SUCCESS", "Browser initialized successfully")
            else:
                log_step("Browser", "WARNING", "Authentication had issues")

        return driver_instance


def save_cookies(driver):
    """Save browser cookies to file"""
    try:
        cookies = driver.get_cookies()
        with open(COOKIE_FILE, "wb") as file:
            pickle.dump(cookies, file)
        log_step("Save Cookies", "SUCCESS", f"Saved {len(cookies)} cookies")
        return True
    except Exception as e:
        log_step("Save Cookies", "ERROR", f"Error saving cookies: {e}")
        return False


def convert_cookies_to_requests_session():
    """Convert Selenium cookies to requests session with proper headers"""
    try:
        if not os.path.exists(COOKIE_FILE):
            log_step("Convert Cookies", "ERROR", "No cookie file found")
            return None

        with open(COOKIE_FILE, "rb") as file:
            selenium_cookies = pickle.load(file)

        session = requests.Session()
        
        # Add proper headers to mimic a real browser
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        })

        # Add cookies
        for cookie in selenium_cookies:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        log_step("Convert Cookies", "SUCCESS", f"Converted {len(selenium_cookies)} cookies")
        return session

    except Exception as e:
        log_step("Convert Cookies", "ERROR", f"Error converting cookies: {e}")
        return None


def save_requests_session(session):
    """Save requests session to file"""
    try:
        with open(REQUESTS_SESSION_FILE, "wb") as file:
            pickle.dump(session, file)
        log_step("Save Requests Session", "SUCCESS", "Session saved")
        return True
    except Exception as e:
        log_step("Save Requests Session", "ERROR", f"Error saving session: {e}")
        return False


def load_requests_session():
    """Load requests session from file"""
    try:
        if not os.path.exists(REQUESTS_SESSION_FILE):
            return None

        with open(REQUESTS_SESSION_FILE, "rb") as file:
            session = pickle.load(file)

        log_step("Load Requests Session", "SUCCESS", "Session loaded")
        return session
    except Exception as e:
        log_step("Load Requests Session", "ERROR", f"Error loading session: {e}")
        return None


def check_session_valid(session):
    """Simplified session check - just make a request and see if we get valid response"""
    try:
        # Use a simple test request that should work if session is valid
        test_url = "https://www.caworkcompcoverage.com/Search"
        
        # Make a simple GET request without parameters
        response = session.get(test_url, timeout=10)
        
        # Log the response for debugging
        log_step("Session Check", "DEBUG", f"Status: {response.status_code}, Length: {len(response.text)}")
        
        # Simple check - if we get a 200 and the page doesn't contain login/otp indicators
        if response.status_code == 200:
            content_lower = response.text.lower()
            
            # Check for indicators that session is NOT valid
            invalid_indicators = [
                'one-time passcode',
                'otp',
                'log in',
                'sign in',
                'session expired',
                'invalid session'
            ]
            
            for indicator in invalid_indicators:
                if indicator in content_lower:
                    log_step("Session Check", "DEBUG", f"Found invalid indicator: {indicator}")
                    return False
            
            # If we get here and no invalid indicators, assume it's valid
            log_step("Session Check", "DEBUG", "Session appears valid")
            return True
        
        return False
        
    except Exception as e:
        log_step("Session Check", "ERROR", f"Error checking session: {e}")
        return False


def analyze_400_error(response_text):
    """Analyze 400 error response"""
    if not response_text:
        return "UNKNOWN_ERROR"
    
    text_lower = response_text.lower()
    
    # Check for session expired indicators
    session_indicators = [
        'invalidsession',
    ]
    
    for indicator in session_indicators:
        if indicator in text_lower:
            return "SESSION_EXPIRED"
    
    # Check for not found indicators
    not_found_indicators = [
        'not found',
        'no results',
        'no matching',
        'could not find',
        'data not found'
    ]
    
    for indicator in not_found_indicators:
        if indicator in text_lower:
            return "NOT_FOUND"
    
    return "UNKNOWN_ERROR"


def recover_session():
    """Recover session by re-authenticating"""
    global driver_instance
    
    log_step("Session Recovery", "INFO", "Starting session recovery...")
    
    with driver_lock:
        if not driver_instance:
            log_step("Session Recovery", "WARNING", "No driver instance, creating new one...")
            driver_instance = create_browser_instance()
            if not driver_instance:
                log_step("Session Recovery", "ERROR", "Failed to create browser")
                return None
        
        try:
            # Save current state
            debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            driver_instance.save_screenshot(os.path.join(DEBUG_DIR, f"recovery_start_{debug_timestamp}.png"))
            
            # Try to re-authenticate
            log_step("Session Recovery", "INFO", "Attempting re-authentication...")
            
            # Navigate to search page first
            driver_instance.get(URL)
            time.sleep(3)
            
            # Handle any disclaimer
            page_source = driver_instance.page_source.lower()
            if "disclaimer" in page_source or "cat chat" in page_source:
                log_step("Session Recovery", "INFO", "Disclaimer found, waiting for user...")
                handle_cat_chat_disclaimer(driver_instance)
            
            # Handle OTP
            otp_success = handle_otp_modal_automatically(driver_instance)
            
            if otp_success:
                # Save new cookies
                save_cookies(driver_instance)
                
                # Convert to session
                session = convert_cookies_to_requests_session()
                if session:
                    save_requests_session(session)
                    log_step("Session Recovery", "SUCCESS", "Session recovered")
                    return session
                else:
                    log_step("Session Recovery", "ERROR", "Failed to convert cookies")
            else:
                log_step("Session Recovery", "ERROR", "Failed to handle OTP")
            
            return None
            
        except Exception as e:
            log_step("Session Recovery", "ERROR", f"Recovery failed: {str(e)}")
            traceback.print_exc()
            return None


# ==========================================================
# SIMPLIFIED API FUNCTIONS
# ==========================================================
def convert_date_format(date_str):
    """Convert date from mm/dd/yyyy to yyyy-mm-dd"""
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError as e:
        log_step("Date Conversion", "ERROR", f"Date conversion error: {e}")
        return date_str


def search_policy_holders_with_recovery(
    session, employer_name, coverage_date, zip_code, max_retries=3
):
    """Search with automatic session recovery"""
    session_id = id(session)
    
    for attempt in range(max_retries):
        try:
            # Convert date
            coverage_date_api = convert_date_format(coverage_date)

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
            
            log_step("Search", "DEBUG", 
                    f"Searching for {employer_name} on {coverage_date} in {zip_code}")
            
            response = session.get(url, params=params, timeout=15)
            
            # Log the response
            log_request_response(session_id, "SEARCH", url, params, 
                               response.status_code, response.text)

            # Handle different status codes
            if response.status_code == 400:
                error_type = analyze_400_error(response.text)
                
                if error_type == 'SESSION_EXPIRED':
                    log_step("Search", "WARNING", 
                            f"Session expired (attempt {attempt + 1}/{max_retries})")
                    
                    # Try to recover session
                    new_session = recover_session()
                    if new_session:
                        session = new_session
                        session_id = id(session)
                        
                        if attempt < max_retries - 1:
                            time.sleep(RETRY_DELAY)
                            continue
                        else:
                            # Try one more search with new session
                            response = session.get(url, params=params, timeout=15)
                            if response.status_code == 200:
                                # Continue parsing
                                pass
                            else:
                                return None, session
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(RETRY_DELAY)
                            continue
                        else:
                            return None, session
                
                elif error_type == 'NOT_FOUND':
                    log_step("Search", "INFO", f"No results found for {employer_name}")
                    return [], session
                
                else:
                    log_step("Search", "WARNING", f"Unknown 400 error for {employer_name}")
                    return [], session

            elif response.status_code != 200:
                log_step("Search", "ERROR", f"Search failed with status: {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    return None, session

            # Parse results
            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Try multiple ways to find results
            # Method 1: Look for data-employer attributes
            result_rows = soup.find_all("tr", attrs={"data-employer": True})
            
            for row in result_rows:
                employer_data = row.get("data-employer")
                city_data = row.get("data-city", "")
                state_data = row.get("data-state", "")
                
                if employer_data:
                    result = {
                        "employer_name": employer_data,
                        "city": city_data,
                        "state": state_data,
                    }
                    results.append(result)

            # Method 2: Look for specific classes
            if not results:
                result_rows = soup.find_all("tr", class_=lambda x: x and "result-row" in x)
                for row in result_rows:
                    cells = row.find_all("td")
                    if len(cells) >= 3:
                        result = {
                            "employer_name": cells[0].get_text(strip=True),
                            "city": cells[1].get_text(strip=True),
                            "state": cells[2].get_text(strip=True),
                        }
                        results.append(result)

            log_step("Search", "DEBUG", f"Found {len(results)} results for {employer_name}")
            return results, session

        except Exception as e:
            log_step("Search", "ERROR", 
                    f"Search exception (attempt {attempt + 1}/{max_retries}): {str(e)}")
            traceback.print_exc()
            
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)
                continue

    return None, session


def get_policy_details_with_recovery(
    session, employer, coverage_date, max_retries=3
):
    """Get details with automatic session recovery"""
    session_id = id(session)
    
    for attempt in range(max_retries):
        try:
            # Convert date
            coverage_date_api = convert_date_format(coverage_date)

            params = {
                "handler": "PolicyHolderDetails",
                "CoverageDate": coverage_date_api,
                "EmployerName": employer["employer_name"],
                "City": employer["city"],
                "State": employer["state"],
            }

            url = "https://www.caworkcompcoverage.com/Search"
            
            log_step("Details", "DEBUG", 
                    f"Getting details for {employer['employer_name']}")
            
            response = session.get(url, params=params, timeout=15)
            
            # Log the response
            log_request_response(session_id, "DETAILS", url, params,
                               response.status_code, response.text)

            # Handle 400 errors
            if response.status_code == 400:
                error_type = analyze_400_error(response.text)
                
                if error_type == 'SESSION_EXPIRED':
                    log_step("Details", "WARNING", 
                            f"Session expired (attempt {attempt + 1}/{max_retries})")
                    
                    if attempt < max_retries - 1:
                        new_session = recover_session()
                        if new_session:
                            session = new_session
                            session_id = id(session)
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        return None, session
                
                elif error_type == 'NOT_FOUND':
                    log_step("Details", "INFO", f"Details not found for {employer['employer_name']}")
                    return {}, session
                
                else:
                    log_step("Details", "WARNING", f"Unknown 400 error for {employer['employer_name']}")
                    return {}, session

            if response.status_code != 200:
                log_step("Details", "ERROR", f"Details request failed: {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    return None, session

            # Parse details
            soup = BeautifulSoup(response.text, "html.parser")
            policy_data = {}

            # Look for detail rows
            detail_rows = soup.find_all("tr", class_="detail-row")
            
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
                        "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    log_step("Details", "SUCCESS", 
                            f"Found details for {policy_data['employer_name']}")
                    break

            return policy_data, session

        except Exception as e:
            log_step("Details", "ERROR", 
                    f"Details exception (attempt {attempt + 1}/{max_retries}): {str(e)}")
            traceback.print_exc()
            
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)
                continue

    return None, session


# ==========================================================
# DATA PROCESSING FUNCTIONS
# ==========================================================
def read_input_csv(file_path):
    """Read the input CSV file"""
    try:
        employers = []

        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            sample = csvfile.read(1024)
            csvfile.seek(0)

            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter

            log_step("Read Input", "INFO", f"Detected delimiter: '{delimiter}'")

            reader = csv.DictReader(csvfile, delimiter=delimiter)

            for row in reader:
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

        log_step("Read Input", "SUCCESS", f"Read {len(employers)} employers")
        return employers
    except Exception as e:
        log_step("Read Input", "ERROR", f"Error reading input CSV: {e}")
        return []


def load_progress():
    """Load progress tracking data"""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
            log_step(
                "Load Progress",
                "SUCCESS",
                f"Loaded progress: {len(progress.get('completed', []))} completed, {len(progress.get('results', []))} results",
            )
            return progress
        else:
            log_step("Load Progress", "INFO", "No progress file found")
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
            f"Progress saved: {len(progress.get('completed', []))} completed, {len(progress.get('results', []))} results",
        )
        return True
    except Exception as e:
        log_step("Save Progress", "ERROR", f"Error saving progress: {e}")
        return False


def save_final_output(results, csv_file=OUTPUT_CSV, json_file=OUTPUT_JSON):
    """Save final results"""
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
            f"Output saved to {csv_file} and {json_file}",
        )
        return True
    except Exception as e:
        log_step("Save Output", "ERROR", f"Error saving output: {e}")
        return False


# ==========================================================
# MAIN PROCESSING
# ==========================================================
def process_employer(session, employer_data, progress):
    """Process a single employer"""
    bureau_number = employer_data["bureau_number"]
    employer_name = employer_data["employer_name"]
    zip_code = employer_data["zip_code"]
    coverage_date = employer_data["coverage_date"]

    log_step("Processing", "INFO", 
            f"Processing Bureau #{bureau_number}: {employer_name}")

    # Search for policy holders
    search_results, session = search_policy_holders_with_recovery(
        session, employer_name, coverage_date, zip_code
    )

    if search_results is None:
        # Error occurred
        result = {
            "bureau_number": bureau_number,
            "employer_name": employer_name,
            "street_address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "insurer_name": "",
            "fein": "",
            "lookup_status": "Error",
            "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        log_step("Processing", "ERROR", f"Search failed for {employer_name}")
        return [result], session

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
        log_step("Processing", "INFO", f"No results found for {employer_name}")
        return [result], session

    # Get details for each search result
    all_results = []
    for search_result in search_results:
        details, session = get_policy_details_with_recovery(
            session, search_result, coverage_date
        )

        if details is None:
            # Error occurred
            result = {
                "bureau_number": bureau_number,
                "employer_name": search_result["employer_name"],
                "street_address": "",
                "city": search_result["city"],
                "state": search_result["state"],
                "zip_code": "",
                "insurer_name": "",
                "fein": "",
                "lookup_status": "Error",
                "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            log_step("Processing", "ERROR", 
                    f"Details retrieval failed for {search_result['employer_name']}")
        elif details:  # Non-empty dict
            # Found details
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
            log_step("Processing", "SUCCESS", 
                    f"Found details for {details['employer_name']}")
        else:
            # Empty dict - not found
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
            log_step("Processing", "WARNING", 
                    f"Details not found for {search_result['employer_name']}")
        
        all_results.append(result)

    log_step("Processing", "SUCCESS", 
            f"Completed processing for {employer_name}: {len(all_results)} results")
    return all_results, session


def main():
    """Main execution function"""
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", "🚀 WORKERS COMP COVERAGE SCRAPER")
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", "Workflow:")
    log_step("Main", "INFO", "1. Browser will open - handle CAPTCHA/disclaimer")
    log_step("Main", "INFO", "2. System will handle OTP automatically")
    log_step("Main", "INFO", "3. Processing will continue automatically")
    log_step("Main", "INFO", "=" * 60)

    # Check input file
    if not os.path.exists(INPUT_CSV):
        log_step("Main", "ERROR", f"Input file {INPUT_CSV} not found!")
        return

    # Initialize browser
    log_step("Main", "INFO", "Launching browser...")
    driver = initialize_browser()
    if not driver:
        log_step("Main", "ERROR", "Failed to initialize browser")
        return

    # Load or create session
    session = load_requests_session()
    if not session:
        session = convert_cookies_to_requests_session()
        if session:
            save_requests_session(session)
        else:
            log_step("Main", "ERROR", "Failed to create session")
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
        save_final_output(progress["results"])
        return

    log_step("Main", "INFO", f"Starting with {len(pending_employers)} employers pending")

    # Process employers
    total_processed = 0
    start_time = time.time()

    for employer in pending_employers:
        # Process employer
        results, session = process_employer(session, employer, progress)

        if results:
            with progress_lock:
                progress["results"].extend(results)
                progress["completed"].append(employer["bureau_number"])
                save_progress(progress)

            total_processed += 1

            # Save session periodically
            if total_processed % 5 == 0:
                save_requests_session(session)

            # Calculate progress
            percentage = (total_processed / len(pending_employers)) * 100
            elapsed_time = time.time() - start_time
            avg_time = elapsed_time / total_processed if total_processed > 0 else 0
            remaining = avg_time * (len(pending_employers) - total_processed)
            
            log_step("Progress", "INFO", 
                    f"Completed {total_processed}/{len(pending_employers)} "
                    f"({percentage:.1f}%) - "
                    f"Elapsed: {elapsed_time:.0f}s, "
                    f"ETA: {remaining:.0f}s")

            # Small delay
            if total_processed < len(pending_employers):
                time.sleep(1)

    # Save final output
    save_final_output(progress["results"])

    # Print summary
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", "📊 PROCESSING COMPLETE!")
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", f"Total Employers Processed: {total_processed}")
    log_step("Main", "INFO", f"Total Time: {time.time() - start_time:.2f} seconds")
    log_step("Main", "INFO", f"Total Records Found: {len(progress['results'])}")
    log_step("Main", "INFO", "=" * 60)

    # Keep browser open
    log_step("Main", "INFO", "Browser will remain open. Press Ctrl+C to exit.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_step("Main", "INFO", "\nExiting...")


# ==========================================================
# ENTRY POINT
# ==========================================================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_step("Main", "WARNING", "Script interrupted by user")
    except Exception as e:
        log_step("Main", "ERROR", f"Critical error: {str(e)}")
        traceback.print_exc()
    finally:
        # Clean up
        if driver_instance:
            try:
                driver_instance.quit()
            except:
                pass
        log_step("Main", "INFO", "Script ended.")