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
import pyautogui
import math
import threading
import random
from datetime import datetime
from threading import Lock
from urllib.parse import quote, urlencode
from pynput import mouse, keyboard

import requests
import urllib3
from bs4 import BeautifulSoup

# Disable SSL warnings when using proxies with SSL interception
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

# ==========================================================
# CONFIG - PROXY SETTINGS (NEW SECTION)
# ==========================================================
# Choose your Bright Data integration method:
# METHOD 1: PROXY GATEWAY (Simpler, good for requests library)
# METHOD 2: PROXY MANAGER (More control, required for Selenium browser)
PROXY_INTEGRATION_METHOD = "PROXY_GATEWAY"  # "PROXY_GATEWAY" or "PROXY_MANAGER"

# --- BRIGHT DATA CREDENTIALS ---
# Replace with your actual Bright Data credentials
BRIGHT_DATA_USERNAME = "brd-customer-hl_69e4a500-zone-residential_proxy1-country-ca"
BRIGHT_DATA_PASSWORD = "eylref00n3mb"

# --- PROXY GATEWAY SETTINGS (For METHOD 1) ---
# Using your residential proxy from curl example
BRIGHT_DATA_GATEWAY_HOST = "brd.superproxy.io"
BRIGHT_DATA_GATEWAY_PORT = "22225"  # From your curl example
# Construct the full gateway URL
PROXY_GATEWAY_URL = f"http://{BRIGHT_DATA_USERNAME}:{BRIGHT_DATA_PASSWORD}@{BRIGHT_DATA_GATEWAY_HOST}:{BRIGHT_DATA_GATEWAY_PORT}"

# --- PROXY MANAGER SETTINGS (For METHOD 2) ---
# The Proxy Manager runs locally and manages connections
PROXY_MANAGER_HOST = "127.0.0.1"  # Localhost if Proxy Manager is on same machine
PROXY_MANAGER_PORT = "24000"      # Default port, adjust based on your setup
PROXY_MANAGER_URL = f"http://{PROXY_MANAGER_HOST}:{PROXY_MANAGER_PORT}"

# --- PROXY ROTATION & MANAGEMENT SETTINGS ---
PROXY_MAX_RETRIES = 100          # Max retries with different proxies for a single request
PROXY_REQUEST_TIMEOUT = 30     # Timeout for requests when using proxies
PROXY_BACKOFF_FACTOR = 1.5     # Exponential backoff factor between retries
PROXY_STATUS_FILE = "proxy_status.json"  # File to track proxy performance

# ==========================================================
# ORIGINAL CONFIG (UPDATED WITH PROXY FILES)
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
MAX_RETRIES = 100
RETRY_DELAY = 2

# Mouse recording configuration
DISCLAIMER_RECORD_FILE = "disclaimer_mouse_record.json"
MIN_DIST = 2

# Thread safety
progress_lock = Lock()
log_lock = Lock()
mouse_lock = Lock()

# Global driver instance
driver_instance = None
driver_lock = Lock()

# Global mouse recording variables
recorded_events = []
stop_flag = False
mouse_start_time = None

# Session recovery tracking
session_recovery_count = 0
MAX_SESSION_RECOVERIES = 5

# Create debug directory
os.makedirs(DEBUG_DIR, exist_ok=True)

# ==========================================================
# PROXY MANAGER CLASS (NEW)
# ==========================================================
class ProxyManager:
    """Manages proxy rotation and failure handling for requests"""
    
    def __init__(self):
        self.proxy_status = self._load_proxy_status()
        self.request_count = 0
        
    def _load_proxy_status(self):
        """Load proxy performance tracking data"""
        try:
            if os.path.exists(PROXY_STATUS_FILE):
                with open(PROXY_STATUS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            log_step("Proxy Manager", "ERROR", f"Error loading proxy status: {e}")
        return {"proxies": {}, "total_requests": 0, "failed_requests": 0}
    
    def _save_proxy_status(self):
        """Save proxy performance tracking data"""
        try:
            with open(PROXY_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.proxy_status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_step("Proxy Manager", "ERROR", f"Error saving proxy status: {e}")
    
    def _get_proxy_config(self, proxy_url):
        """Create proxy configuration dictionary for requests library"""
        # PROXY_GATEWAY already contains full URL including credentials  
        if PROXY_INTEGRATION_METHOD == "PROXY_GATEWAY":
            return {
                'http': proxy_url,
                'https': proxy_url,
            }
        
        # PROXY_MANAGER uses proxy URL without credentials
        return {
            'http': proxy_url,
            'https': proxy_url,
        }

    def get_proxy_for_request(self):
        """Get a proxy configuration for a request with rotation logic"""
        self.request_count += 1
        
        # Choose proxy based on method
        if PROXY_INTEGRATION_METHOD == "PROXY_GATEWAY":
            proxy_url = PROXY_GATEWAY_URL
        else:  # PROXY_MANAGER
            proxy_url = PROXY_MANAGER_URL
        
        # Track usage
        if proxy_url not in self.proxy_status["proxies"]:
            self.proxy_status["proxies"][proxy_url] = {
                "success": 0,
                "failures": 0,
                "last_used": None
            }
        
        self.proxy_status["proxies"][proxy_url]["last_used"] = datetime.now().isoformat()
        self.proxy_status["total_requests"] = self.request_count
        
        log_step("Proxy Manager", "DEBUG", f"Using proxy: {proxy_url}")
        return self._get_proxy_config(proxy_url)
    
    def record_proxy_result(self, proxy_url, success=True):
        """Record the result of a proxy request"""
        if proxy_url in self.proxy_status["proxies"]:
            if success:
                self.proxy_status["proxies"][proxy_url]["success"] += 1
            else:
                self.proxy_status["proxies"][proxy_url]["failures"] += 1
                self.proxy_status["failed_requests"] += 1
            self._save_proxy_status()
    
    def get_stats(self):
        """Get proxy usage statistics"""
        total_success = sum(p["success"] for p in self.proxy_status["proxies"].values())
        total_failures = sum(p["failures"] for p in self.proxy_status["proxies"].values())
        
        return {
            "total_requests": self.proxy_status["total_requests"],
            "successful_requests": total_success,
            "failed_requests": total_failures,
            "success_rate": total_success / max(1, total_success + total_failures) * 100
        }

# Global proxy manager instance
proxy_manager = ProxyManager()

# ==========================================================
# LOGGING FUNCTIONS (UPDATED WITH PROXY LOGGING)
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
        "PROXY": "🔁",
    }
    icon = status_icons.get(status, "🔸")
    log_message = f"{timestamp} {icon} [{status}] {step_name}: {message}"
    print(log_message)
    
    with open(os.path.join(DEBUG_DIR, "execution_log.txt"), "a", encoding="utf-8") as f:
        f.write(log_message + "\n")


def log_request_response(session_id, request_type, url, params=None, 
                        status_code=None, response_text=None, error=None, proxy_used=None):
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
        "proxy_used": proxy_used,
        "has_otp_modal": "one-time passcode" in (response_text or "").lower(),
        "has_session_error": any(indicator in (response_text or "").lower() 
                                for indicator in ["invalid session", "session expired", "login"]),
    }
    
    if response_text and (status_code != 200 or "one-time passcode" in response_text.lower()):
        filename = f"{timestamp.replace(':', '-').replace('.', '-')}_{request_type}_{status_code}.html"
        with open(os.path.join(DEBUG_DIR, filename), "w", encoding="utf-8") as f:
            f.write(response_text)
        log_entry["response_file"] = filename
    
    with log_lock:
        with open(REQUEST_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    if status_code == 400 or status_code == 403 or error or "one-time passcode" in (response_text or "").lower():
        log_step(f"HTTP {request_type}", "DEBUG", 
                f"URL: {url}, Status: {status_code}, "
                f"Proxy: {proxy_used}, Error: {error}")

# ==========================================================
# MOUSE RECORDING/REPLAY FUNCTIONS (UNCHANGED)
# ==========================================================
def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])


def record_mouse_thread():
    """Record only mouse movements at significant distances."""
    global recorded_events, stop_flag, mouse_start_time
    last_pos = pyautogui.position()

    while not stop_flag:
        x, y = pyautogui.position()
        t = time.time() - mouse_start_time

        if distance((x, y), last_pos) >= MIN_DIST:
            with mouse_lock:
                recorded_events.append({"type": "move", "pos": (x, y), "time": t})
            last_pos = (x, y)

        time.sleep(0.005)


def on_click(x, y, button, pressed):
    """Record click events using pynput for accuracy."""
    global mouse_start_time
    t = time.time() - mouse_start_time
    with mouse_lock:
        recorded_events.append({
            "type": "click",
            "pos": (x, y),
            "button": str(button).split(".")[1],
            "action": "down" if pressed else "up",
            "time": t
        })


def on_key_press(key):
    global stop_flag
    if key == keyboard.Key.f10:
        stop_flag = True
        return False


def start_recording():
    """Start recording mouse movements and clicks."""
    global recorded_events, stop_flag, mouse_start_time
    
    with mouse_lock:
        recorded_events = []
    stop_flag = False

    print("\n" + "="*60)
    print("DISCLAIMER MOUSE RECORDING")
    print("="*60)
    print("Instructions:")
    print("1. Move your mouse to the 'Accept' button on the disclaimer")
    print("2. Click on the 'Accept' button")
    print("3. Press F10 to stop recording")
    print("="*60)
    print("Recording... (Move mouse and click, then press F10)")

    t1 = threading.Thread(target=record_mouse_thread, daemon=True)
    t1.start()

    mouse_start_time = time.time()
    
    try:
        with mouse.Listener(on_click=on_click) as m_listener, keyboard.Listener(on_press=on_key_press) as k_listener:
            while not stop_flag:
                time.sleep(0.1)
    except Exception as e:
        print(f"Error in recording: {e}")
    
    t1.join()

    if recorded_events:
        with open(DISCLAIMER_RECORD_FILE, "w") as f:
            json.dump(recorded_events, f, indent=4)

        print(f"Recording saved with {len(recorded_events)} events.")
        print(f"File saved as: {DISCLAIMER_RECORD_FILE}")
        print("="*60)
        return True
    else:
        print("No events recorded!")
        print("="*60)
        return False


def replay_disclaimer():
    """Replay recorded mouse events for disclaimer acceptance."""
    print("\nReplaying recorded disclaimer acceptance...")
    
    try:
        with open(DISCLAIMER_RECORD_FILE, "r") as f:
            events = json.load(f)
    except FileNotFoundError:
        print(f"No recorded disclaimer found at {DISCLAIMER_RECORD_FILE}")
        return False
    
    print(f"Loaded {len(events)} mouse events")
    
    time.sleep(2)
    
    try:
        for i, e in enumerate(events):
            if i == 0:
                dt = e["time"]
            else:
                dt = e["time"] - events[i-1]["time"]

            if dt > 0:
                time.sleep(dt)

            x, y = e["pos"]

            if e["type"] == "move":
                pyautogui.moveTo(x, y, duration=0)
            elif e["type"] == "click":
                pyautogui.moveTo(x, y, duration=0)
                if e["action"] == "down":
                    pyautogui.mouseDown(button=e["button"])
                else:
                    pyautogui.mouseUp(button=e["button"])
        
        print("Disclaimer replay finished.")
        return True
        
    except Exception as e:
        print(f"Error during replay: {e}")
        return False


def handle_cat_chat_disclaimer_automated(driver):
    """Automated disclaimer handler with mouse recording/replaying capability."""
    log_step("Disclaimer", "INFO", "Checking for disclaimer...")
    
    time.sleep(3)
    
    page_source = driver.page_source.lower()
    disclaimer_keywords = [
        "disclaimer", "cat chat", "terms of use", "please read", 
        "by clicking", "i agree", "accept", "acknowledge", "agree to terms"
    ]
    
    has_disclaimer = any(keyword in page_source for keyword in disclaimer_keywords)
    
    if not has_disclaimer:
        log_step("Disclaimer", "DEBUG", "No disclaimer detected")
        return True
    
    log_step("Disclaimer", "WARNING", "CAT CHAT / DISCLAIMER DETECTED!")
    log_step("Disclaimer", "INFO", "Attempting automated handling...")
    
    with open(os.path.join(DEBUG_DIR, "disclaimer_page.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    driver.save_screenshot(os.path.join(DEBUG_DIR, "disclaimer_page.png"))
    
    if os.path.exists(DISCLAIMER_RECORD_FILE):
        log_step("Disclaimer", "INFO", "Found recorded disclaimer actions. Replaying...")
        
        print("\n" + "="*60)
        print("AUTO-ACCEPTING DISCLAIMER IN 5 SECONDS...")
        print("="*60)
        time.sleep(5)
        
        if replay_disclaimer():
            time.sleep(3)
            
            updated_source = driver.page_source.lower()
            still_has_disclaimer = any(keyword in updated_source for keyword in disclaimer_keywords)
            
            log_step("Disclaimer", "SUCCESS", "Disclaimer accepted automatically!")
            return True
        else:
            log_step("Disclaimer", "WARNING", "Automatic replay failed")
    
    print("\n" + "="*60)
    print("DISCLAIMER HANDLING REQUIRED")
    print("="*60)
    print("Options:")
    print("1. Record mouse movements for future automation (RECOMMENDED)")
    print("2. Handle manually now and continue")
    print("3. Handle manually and record for future use")
    print("="*60)
    
    while True:
        choice = input("\nEnter choice (1, 2, or 3): ").strip()
        
        if choice == "1":
            log_step("Disclaimer", "INFO", "Recording mouse movements for disclaimer...")
            log_step("Disclaimer", "INFO", "Please move mouse to 'Accept' button and click it")
            if start_recording():
                log_step("Disclaimer", "INFO", "Recording complete. Now please handle the disclaimer manually.")
                input("Press ENTER after you've accepted the disclaimer...")
                time.sleep(3)
                return True
            else:
                log_step("Disclaimer", "ERROR", "Recording failed, please handle manually")
                input("Press ENTER after you've accepted the disclaimer...")
                time.sleep(3)
                return True
            
        elif choice == "2":
            log_step("Disclaimer", "INFO", "Please handle the disclaimer manually.")
            input("Press ENTER after you've accepted the disclaimer...")
            time.sleep(3)
            return True
            
        elif choice == "3":
            log_step("Disclaimer", "INFO", "Recording mouse movements while you handle disclaimer...")
            log_step("Disclaimer", "INFO", "Please move mouse to 'Accept' button and click it")
            log_step("Disclaimer", "INFO", "Recording will start in 3 seconds...")
            time.sleep(3)
            
            if start_recording():
                log_step("Disclaimer", "INFO", "Recording complete. Waiting for page update...")
                time.sleep(3)
                return True
            else:
                log_step("Disclaimer", "WARNING", "Recording failed, but continuing...")
                time.sleep(3)
                return True
            
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

def refresh_browser_session():
    """Refresh the browser session by navigating through the site"""
    global driver_instance
    
    if not driver_instance:
        log_step("Browser Refresh", "ERROR", "No browser instance to refresh")
        return False
    
    try:
        log_step("Browser Refresh", "INFO", "Refreshing browser session...")
        
        # First, try to go to home page
        driver_instance.get("https://www.caworkcompcoverage.com/")
        time.sleep(3)
        
        # Check for disclaimer
        page_source = driver_instance.page_source.lower()
        if "disclaimer" in page_source or "cat chat" in page_source:
            log_step("Browser Refresh", "INFO", "Disclaimer detected, handling...")
            disclaimer_success = handle_cat_chat_disclaimer_automated(driver_instance)
            if not disclaimer_success:
                log_step("Browser Refresh", "WARNING", "Disclaimer handling failed")
        
        # Navigate to search page
        driver_instance.get("https://www.caworkcompcoverage.com/Search")
        time.sleep(3)
        
        # Check for OTP
        page_source = driver_instance.page_source.lower()
        if "one-time passcode" in page_source or "otp" in page_source:
            log_step("Browser Refresh", "INFO", "OTP detected, handling...")
            otp_success = handle_otp_modal_automatically(driver_instance)
            if not otp_success:
                log_step("Browser Refresh", "WARNING", "OTP handling failed")
        
        # Verify we're on search page
        current_url = driver_instance.current_url.lower()
        if "search" in current_url:
            log_step("Browser Refresh", "SUCCESS", "Browser session refreshed successfully")
            
            # Save new cookies
            save_cookies(driver_instance)
            
            # Update requests session
            session = convert_cookies_to_requests_session()
            if session:
                save_requests_session(session)
                return True
            else:
                log_step("Browser Refresh", "WARNING", "Failed to update requests session")
                return False
        else:
            log_step("Browser Refresh", "ERROR", "Not on search page after refresh")
            return False
            
    except Exception as e:
        log_step("Browser Refresh", "ERROR", f"Error refreshing browser session: {str(e)}")
        traceback.print_exc()
        return False
# ==========================================================
# GMAIL API OTP FUNCTIONS (UNCHANGED)
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
        decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8")
        return decoded
    except:
        try:
            decoded = quopri.decodestring(data).decode("utf-8")
            return decoded
        except:
            return data


def extract_otp_from_email(payload):
    """Extract text content from email payload and find OTP"""
    text_content = ""

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
        body_data = payload["body"]["data"]
        decoded = decode_email_body(body_data)
        text_content = decoded

    text_content = text_content.replace("\r\n", "\n").replace("\r", "\n")

    email_debug_file = os.path.join(DEBUG_DIR, f"email_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(email_debug_file, "w", encoding="utf-8") as f:
        f.write(text_content)

    log_step("OTP Extraction", "DEBUG", f"Email saved to {email_debug_file}")

    patterns = [
        r"Your One-Time Passcode is:\s*(\d{6})",
        r"One-Time Passcode:\s*(\d{6})",
        r"passcode.*?:\s*(\d{6})",
        r"Passcode.*?:\s*(\d{6})",
        r"code.*?:\s*(\d{6})",
        r"OTP.*?:\s*(\d{6})",
        r"\b(\d{6})\b(?!.*\d)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
        if match:
            otp = match.group(1)
            log_step("OTP Extraction", "SUCCESS", f"Found OTP using pattern '{pattern}': {otp}")
            return otp

    all_numbers = re.findall(r"\b(\d{6})\b", text_content)
    if all_numbers:
        otp = all_numbers[-1]
        log_step("OTP Extraction", "WARNING", f"Found potential OTP (last 6-digit number): {otp}")
        return otp

    log_step("OTP Extraction", "ERROR", "No OTP found in email content")
    return None


def get_latest_otp():
    """Get the latest OTP from WCIRB emails"""
    service = gmail_service()

    start_time = time.time()
    max_wait_time = 300

    log_step("OTP Retrieval", "INFO", "Starting to search for OTP emails...")

    while time.time() - start_time < max_wait_time:
        try:
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

            latest_msg_id = messages[0]["id"]
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=latest_msg_id, format="full")
                .execute()
            )

            msg_date = int(msg["internalDate"]) / 1000
            current_time = time.time()

            if current_time - msg_date > 300:
                log_step("OTP Retrieval", "INFO", 
                        f"Email is too old ({int(current_time - msg_date)}s), waiting for new one...")
                time.sleep(5)
                continue

            otp = extract_otp_from_email(msg["payload"])

            if otp:
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
# OTP AUTOMATION FUNCTIONS (UNCHANGED)
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


def find_and_fill_element(driver, selectors, text, by=By.CSS_SELECTOR, timeout=10, description=""):
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
    """Automatically handles the OTP modal with improved error handling and debugging"""
    log_step("OTP Automation", "INFO", "Starting automatic OTP handling...")

    try:
        debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        page_source_file = os.path.join(DEBUG_DIR, f"page_before_otp_{debug_timestamp}.html")
        with open(page_source_file, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        screenshot_file = os.path.join(DEBUG_DIR, f"before_otp_modal_{debug_timestamp}.png")
        driver.save_screenshot(screenshot_file)
        
        log_step("OTP Automation", "DEBUG", f"Saved page source to {page_source_file}")
        log_step("OTP Automation", "DEBUG", f"Saved screenshot to {screenshot_file}")
        
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
            if "search" in driver.current_url.lower():
                log_step("OTP Automation", "SUCCESS", "Already on search page, OTP not needed")
                return True
            else:
                log_step("OTP Automation", "WARNING", "Not on search page but no OTP indicators found")
                return False
        
        log_step("OTP Automation", "INFO", f"OTP modal detected with indicators: {found_indicators}")
        
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
                try:
                    text_to_find = selector.split('contains(')[1].split(')')[0].lower()
                    elements = driver.find_elements(By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text_to_find}')]")
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            log_step("OTP Automation", "DEBUG", f"Clicking request button (text): {text_to_find}")
                            element.click()
                            otp_requested = True
                            time.sleep(3)
                            break
                    if otp_requested:
                        break
                except:
                    continue
            else:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            log_step("OTP Automation", "DEBUG", f"Clicking request button: {selector}")
                            element.click()
                            otp_requested = True
                            time.sleep(3)
                            break
                    if otp_requested:
                        break
                except:
                    continue
        
        if not otp_requested:
            log_step("OTP Automation", "ERROR", "Could not find/click request OTP button")
            driver.save_screenshot(os.path.join(DEBUG_DIR, "no_request_button.png"))
            return False
        
        log_step("OTP Automation", "DEBUG", "Waiting for OTP input field...")
        time.sleep(5)
        
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
            driver.save_screenshot(os.path.join(DEBUG_DIR, "otp_input_error.png"))
            with open(os.path.join(DEBUG_DIR, "page_no_otp_input.html"), "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False
        
        log_step("OTP Automation", "INFO", "Retrieving OTP from Gmail...")
        otp = get_latest_otp()
        
        if not otp:
            log_step("OTP Automation", "ERROR", "Failed to retrieve OTP from Gmail")
            try:
                email_files = [f for f in os.listdir(DEBUG_DIR) if f.startswith("email_")]
                if email_files:
                    latest_email = max(email_files)
                    with open(os.path.join(DEBUG_DIR, latest_email), "r", encoding="utf-8") as f:
                        email_content = f.read()
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
        
        try:
            otp_input.clear()
            otp_input.send_keys(otp)
            log_step("OTP Automation", "DEBUG", f"Filled OTP: {otp}")
            time.sleep(1)
        except Exception as e:
            log_step("OTP Automation", "ERROR", f"Error filling OTP: {e}")
            return False
        
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
            try:
                otp_input.send_keys(Keys.RETURN)
                log_step("OTP Automation", "DEBUG", "Pressed Enter in OTP field")
                submit_clicked = True
            except:
                log_step("OTP Automation", "ERROR", "Could not press Enter")
        
        log_step("OTP Automation", "DEBUG", "Waiting for OTP verification...")
        time.sleep(5)
        
        current_url = driver.current_url.lower()
        if "search" in current_url:
            log_step("OTP Automation", "SUCCESS", "Successfully redirected to search page")
            return True
        
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
        driver.save_screenshot(os.path.join(DEBUG_DIR, "after_otp_attempt.png"))
        with open(os.path.join(DEBUG_DIR, "page_after_otp.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        return False

    except Exception as e:
        log_step("OTP Automation", "ERROR", f"Exception in OTP automation: {str(e)}")
        traceback.print_exc()
        driver.save_screenshot(os.path.join(DEBUG_DIR, "otp_automation_error.png"))
        with open(os.path.join(DEBUG_DIR, "page_otp_error.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return False


def handle_cat_chat_disclaimer(driver):
    """Wait for user to manually handle Cat Chat/Disclaimer OR use automated approach"""
    automated_success = handle_cat_chat_disclaimer_automated(driver)
    
    if automated_success:
        page_source = driver.page_source.lower()
        disclaimer_keywords = ["disclaimer", "cat chat", "terms of use", "please read", "by clicking"]
        
        if not any(keyword in page_source for keyword in disclaimer_keywords):
            log_step("Disclaimer", "SUCCESS", "Disclaimer handled successfully")
            return True
        else:
            log_step("Disclaimer", "WARNING", "Disclaimer might still be present, falling back to manual")
    
    log_step("Disclaimer", "WARNING", "CAT CHAT / DISCLAIMER DETECTED!")
    
    with open(os.path.join(DEBUG_DIR, "disclaimer_page.html"), "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    driver.save_screenshot(os.path.join(DEBUG_DIR, "disclaimer_page.png"))
    
    log_step("Disclaimer", "INFO", "Please manually:")
    log_step("Disclaimer", "INFO", "1. Read and accept the disclaimer/Cat Chat")
    log_step("Disclaimer", "INFO", "2. Complete any CAPTCHA if required")
    log_step("Disclaimer", "INFO", "3. Click 'Accept', 'Agree', or similar button")
    
    record_choice = input("\nWould you like to record mouse movements for future automation? (y/n): ").lower()
    if record_choice == 'y':
        log_step("Disclaimer", "INFO", "Recording mouse movements...")
        log_step("Disclaimer", "INFO", "Move mouse to 'Accept' button and click it in the next 5 seconds...")
        time.sleep(5)
        start_recording()
    
    input("\nPress ENTER after you've completed the CAPTCHA and accepted the disclaimer...")
    
    time.sleep(3)
    
    log_step("Disclaimer", "SUCCESS", "Disclaimer handled")
    return True


# ==========================================================
# BROWSER MANAGEMENT (UPDATED WITH PROXY SUPPORT)
# ==========================================================
def create_browser_instance():
    """Create a new browser instance with proxy configuration"""
    log_step("Browser", "INFO", "Creating new browser instance with proxy...")
    
    try:
        # Configure proxy based on integration method
        if PROXY_INTEGRATION_METHOD == "PROXY_MANAGER":
            # For Proxy Manager, we need to set proxy arguments[citation:9]
            proxy_arg = f"--proxy-server={PROXY_MANAGER_HOST}:{PROXY_MANAGER_PORT}"
            log_step("Browser", "DEBUG", f"Using Proxy Manager: {proxy_arg}")
            
            driver = Driver(
                uc=True, 
                headless=False,
                chromium_arg=f"{proxy_arg} --ozone-platform=x11"
            )
        else:
            # For Gateway method or no proxy
            driver = Driver(
                uc=True, 
                headless=False,
                chromium_arg="--ozone-platform=x11"
            )
        
        driver.maximize_window()
        log_step("Browser", "SUCCESS", "Browser instance created with proxy configuration")
        return driver
        
    except Exception as e:
        log_step("Browser", "ERROR", f"Failed to create browser instance: {str(e)}")
        traceback.print_exc()
        return None


def perform_full_authentication(driver):
    """Perform full authentication process"""
    log_step("Authentication", "INFO", "Starting authentication...")
    
    try:
        driver.get(URL)
        driver.maximize_window()

        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        log_step("Authentication", "INFO", "Page loaded, checking for disclaimer...")
        
        disclaimer_success = handle_cat_chat_disclaimer_automated(driver)
        
        if not disclaimer_success:
            log_step("Authentication", "WARNING", "Disclaimer handling failed")
            return False
        else:
            log_step("Authentication", "INFO", "Disclaimer handled, proceeding...")
        
        log_step("Authentication", "INFO", "Checking for OTP modal...")
        time.sleep(3)
        
        otp_success = handle_otp_modal_automatically(driver)
        
        if otp_success:
            log_step("Authentication", "SUCCESS", "Authentication completed successfully")
            time.sleep(3)
            return True
        else:
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
    """Initialize browser with authentication and proxy"""
    global driver_instance

    with driver_lock:
        if driver_instance is None:
            log_step("Browser", "INFO", "Initializing browser with proxy...")
            
            driver_instance = create_browser_instance()
            if not driver_instance:
                log_step("Browser", "ERROR", "Failed to create browser instance")
                return None
            
            auth_success = perform_full_authentication(driver_instance)
            
            if auth_success:
                save_cookies(driver_instance)
                log_step("Browser", "SUCCESS", "Browser initialized successfully with proxy")
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
    """Convert Selenium cookies to requests session with proxy support"""
    try:
        if not os.path.exists(COOKIE_FILE):
            log_step("Convert Cookies", "ERROR", "No cookie file found")
            return None

        with open(COOKIE_FILE, "rb") as file:
            selenium_cookies = pickle.load(file)

        session = requests.Session()
        
        # Disable SSL verification for proxy MITM (Man-in-the-Middle)
        # Bright Data proxies perform SSL interception which causes certificate errors
        session.verify = False
        
        # Get proxy configuration for this session
        proxy_config = proxy_manager.get_proxy_for_request()
        session.proxies.update(proxy_config)
        
        # Add authentication for gateway method
        if PROXY_INTEGRATION_METHOD == "PROXY_GATEWAY":
            session.auth = (BRIGHT_DATA_USERNAME, BRIGHT_DATA_PASSWORD)
        
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

        for cookie in selenium_cookies:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ""),
                path=cookie.get("path", "/"),
            )

        log_step("Convert Cookies", "SUCCESS", f"Converted {len(selenium_cookies)} cookies with proxy")
        return session

    except Exception as e:
        log_step("Convert Cookies", "ERROR", f"Error converting cookies: {e}")
        return None


def save_requests_session(session):
    """Save requests session to file"""
    try:
        with open(REQUESTS_SESSION_FILE, "wb") as file:
            pickle.dump(session, file)
        log_step("Save Requests Session", "SUCCESS", "Session saved with proxy")
        return True
    except Exception as e:
        log_step("Save Requests Session", "ERROR", f"Error saving session: {e}")
        return False


def load_requests_session():
    """Load requests session from file and update proxy"""
    try:
        if not os.path.exists(REQUESTS_SESSION_FILE):
            return None

        with open(REQUESTS_SESSION_FILE, "rb") as file:
            session = pickle.load(file)

        # Disable SSL verification for proxy MITM
        session.verify = False
        
        # Update proxy configuration for the loaded session
        proxy_config = proxy_manager.get_proxy_for_request()
        session.proxies.update(proxy_config)
        
        if PROXY_INTEGRATION_METHOD == "PROXY_GATEWAY":
            session.auth = (BRIGHT_DATA_USERNAME, BRIGHT_DATA_PASSWORD)

        log_step("Load Requests Session", "SUCCESS", "Session loaded with updated proxy")
        return session
    except Exception as e:
        log_step("Load Requests Session", "ERROR", f"Error loading session: {e}")
        return None


from requests.exceptions import SSLError, ProxyError, ConnectTimeout

def check_session_valid(session):
    """
    Check if session is valid by using the browser instead of requests.
    Returns True if session is valid, False if session expired.
    """
    global driver_instance
    
    if not driver_instance:
        log_step("Session Check", "WARNING", "No browser instance available")
        return False
    
    try:
        # Use browser to check session status
        test_url = "https://www.caworkcompcoverage.com/Search"
        
        # Save current URL for restoration
        current_url = driver_instance.current_url
        
        # Navigate to search page to check session
        driver_instance.get(test_url)
        
        # Wait for page load
        WebDriverWait(driver_instance, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        time.sleep(3)  # Extra wait for any modals
        
        # Check for session indicators in page source
        page_source = driver_instance.page_source.lower()
        
        # Indicators of invalid session
        session_expired_indicators = [
            "invalid session",
            "session expired",
            "please log in",
            "authentication required",
            "sign in",
            "log in"
        ]
        
        # Check if we're actually on the search page
        search_page_indicators = [
            "input[name='employername']",
            "searchpolicyholders",
            "employer name",
            "coverage date",
            "search form"
        ]
        
        # Check for expired session
        for indicator in session_expired_indicators:
            if indicator in page_source:
                log_step("Session Check", "ERROR", f"Session expired detected: {indicator}")
                # Go back to original URL if possible
                try:
                    driver_instance.get(current_url)
                except:
                    pass
                return False
        
        # Check if we're on the search page
        is_on_search_page = False
        for indicator in search_page_indicators:
            if indicator in page_source:
                is_on_search_page = True
                break
        
        # Check current URL
        current_url_after_check = driver_instance.current_url.lower()
        if "search" in current_url_after_check or is_on_search_page:
            log_step("Session Check", "SUCCESS", "Session is valid (on search page)")
            # Stay on this page for session refresh
            return True
        
        # Check for OTP modal (session might be valid but needs OTP)
        if "one-time passcode" in page_source or "otp" in page_source:
            log_step("Session Check", "INFO", "Session valid but OTP modal present")
            # Go back to original URL
            try:
                driver_instance.get(current_url)
            except:
                pass
            return True
        
        # Check for disclaimer (session is valid)
        if "disclaimer" in page_source or "cat chat" in page_source:
            log_step("Session Check", "INFO", "Session valid but disclaimer present")
            # Go back to original URL
            try:
                driver_instance.get(current_url)
            except:
                pass
            return True
        
        # If we're not sure, assume session is valid
        log_step("Session Check", "WARNING", "Session status uncertain, assuming valid")
        # Go back to original URL
        try:
            driver_instance.get(current_url)
        except:
            pass
        return True
        
    except Exception as e:
        log_step("Session Check", "ERROR", f"Error checking session with browser: {str(e)}")
        traceback.print_exc()
        return False
def analyze_error(response_text, status_code):
    """Analyze error response"""
    if not response_text:
        return "UNKNOWN_ERROR"
    
    text_lower = response_text.lower() 
    
    session_indicators = [
        'invalidsession',
        'invalid session',
        'session expired',
        'please log in',
        'authentication required',
        'forbidden',
        'access denied'
    ]
    
    for indicator in session_indicators:
        if indicator in text_lower:
            return "SESSION_EXPIRED"
    
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
    
    proxy_indicators = [
        'proxy error',
        'connection refused',
        'timeout',
        'too many requests',
        'rate limit'
    ]
    
    for indicator in proxy_indicators:
        if indicator in text_lower:
            return "PROXY_ERROR"
    
    return "UNKNOWN_ERROR"


def clear_all_sessions():
    """Clear all session files and cookies"""
    log_step("Session Cleanup", "INFO", "Clearing all session data...")
    
    files_to_clear = [
        COOKIE_FILE,
        REQUESTS_SESSION_FILE,
        PROXY_STATUS_FILE
    ]
    
    cleared_count = 0
    for file_path in files_to_clear:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                log_step("Session Cleanup", "DEBUG", f"Removed: {file_path}")
                cleared_count += 1
            except Exception as e:
                log_step("Session Cleanup", "ERROR", f"Failed to remove {file_path}: {e}")
    
    log_step("Session Cleanup", "SUCCESS", f"Cleared {cleared_count} session files")
    return cleared_count


def recover_session():
    """Recover session by using browser to re-authenticate"""
    global driver_instance, session_recovery_count
    
    session_recovery_count += 1
    
    if session_recovery_count > MAX_SESSION_RECOVERIES:
        log_step("Session Recovery", "ERROR", f"Maximum session recoveries ({MAX_SESSION_RECOVERIES}) reached. Stopping.")
        return None
    
    log_step("Session Recovery", "INFO", f"Starting browser-based session recovery... (Attempt {session_recovery_count}/{MAX_SESSION_RECOVERIES})")
    
    try:
        with driver_lock:
            # Close current browser if exists
            if driver_instance:
                try:
                    driver_instance.quit()
                    log_step("Session Recovery", "DEBUG", "Closed existing browser")
                except:
                    pass
                driver_instance = None
            
            # Create new browser with proxy
            log_step("Session Recovery", "INFO", "Creating new browser instance...")
            driver_instance = create_browser_instance()
            
            if not driver_instance:
                log_step("Session Recovery", "ERROR", "Failed to create browser instance")
                return None
            
            # Perform full authentication
            log_step("Session Recovery", "INFO", "Performing full re-authentication with browser...")
            auth_success = perform_full_authentication(driver_instance)
            
            if not auth_success:
                log_step("Session Recovery", "ERROR", "Browser re-authentication failed")
                return None
            
            # Save cookies from browser
            save_cookies(driver_instance)
            
            # Convert cookies to requests session
            session = convert_cookies_to_requests_session()
            
            if session:
                save_requests_session(session)
                
                # Verify session is valid using browser
                if check_session_valid(session):
                    log_step("Session Recovery", "SUCCESS", "Session fully recovered via browser")
                    return session
                else:
                    log_step("Session Recovery", "WARNING", "Recovered session check failed")
                    return None
            else:
                log_step("Session Recovery", "ERROR", "Failed to convert cookies to session")
                return None
    
    except Exception as e:
        log_step("Session Recovery", "ERROR", f"Browser recovery failed: {str(e)}")
        traceback.print_exc()
        return None

# ==========================================================
# API FUNCTIONS WITH PROXY SUPPORT (UPDATED)
# ==========================================================
def convert_date_format(date_str):
    """Convert date from mm/dd/yyyy to yyyy-mm-dd"""
    try:
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d")
    except ValueError as e:
        log_step("Date Conversion", "ERROR", f"Date conversion error: {e}")
        return date_str


def search_policy_holders_with_recovery(session, employer_name, coverage_date, zip_code, max_retries=PROXY_MAX_RETRIES):
    """Search with automatic session recovery using browser refresh"""
    session_id = id(session)
    
    for attempt in range(max_retries):
        try:
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
            
            log_step("Search", "DEBUG", f"Searching for {employer_name} on {coverage_date} in {zip_code} (Attempt {attempt+1}/{max_retries})")
            
            # Update proxy for this attempt
            if attempt > 0:
                proxy_config = proxy_manager.get_proxy_for_request()
                session.proxies.update(proxy_config)
                log_step("Proxy", "INFO", f"Rotating proxy for retry attempt {attempt+1}")
            
            response = session.get(url, params=params, timeout=PROXY_REQUEST_TIMEOUT)
            
            log_request_response(session_id, "SEARCH", url, params, response.status_code, response.text)

            if response.status_code == 400 or response.status_code == 403:
                error_type = analyze_error(response.text, response.status_code)
                
                if error_type == 'SESSION_EXPIRED':
                    log_step("Search", "WARNING", f"Session expired (attempt {attempt + 1}/{max_retries})")
                    
                    # Try browser refresh first
                    if attempt == 0:
                        log_step("Search", "INFO", "Attempting browser session refresh...")
                        if refresh_browser_session():
                            # Get fresh session from browser cookies
                            new_session = convert_cookies_to_requests_session()
                            if new_session:
                                session = new_session
                                save_requests_session(session)
                                session_id = id(session)
                                log_step("Search", "SUCCESS", "Browser session refreshed, retrying...")
                                continue
                    
                    # If browser refresh failed, do full recovery
                    new_session = recover_session()
                    if new_session:
                        session = new_session
                        session_id = id(session)
                        
                        if attempt < max_retries - 1:
                            time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                            continue
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                            continue
                
                elif error_type == 'NOT_FOUND':
                    log_step("Search", "INFO", f"No results found for {employer_name}")
                    return [], session
                
                else:
                    if attempt < max_retries - 1:
                        time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                        continue

            elif response.status_code != 200:
                log_step("Search", "ERROR", f"Search failed with status: {response.status_code}")
                
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                    continue
                else:
                    return [], session

            soup = BeautifulSoup(response.text, "html.parser")
            results = []

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
            log_step("Search", "ERROR", f"Search exception (attempt {attempt + 1}/{max_retries}): {str(e)}")
            traceback.print_exc()
            
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                continue

    return [], session
def get_policy_details_with_recovery(session, employer, coverage_date, max_retries=PROXY_MAX_RETRIES):
    """Get details with automatic session recovery and proxy rotation"""
    session_id = id(session)
    proxy_url = PROXY_GATEWAY_URL if PROXY_INTEGRATION_METHOD == "PROXY_GATEWAY" else PROXY_MANAGER_URL
    
    for attempt in range(max_retries):
        try:
            coverage_date_api = convert_date_format(coverage_date)

            params = {
                "handler": "PolicyHolderDetails",
                "CoverageDate": coverage_date_api,
                "EmployerName": employer["employer_name"],
                "City": employer["city"],
                "State": employer["state"],
            }

            url = "https://www.caworkcompcoverage.com/Search"
            
            log_step("Details", "DEBUG", f"Getting details for {employer['employer_name']} (Attempt {attempt+1}/{max_retries})")
            
            # Update proxy for this attempt
            if attempt > 0:
                proxy_config = proxy_manager.get_proxy_for_request()
                session.proxies.update(proxy_config)
                log_step("Proxy", "INFO", f"Rotating proxy for retry attempt {attempt+1}")
            
            response = session.get(url, params=params, timeout=PROXY_REQUEST_TIMEOUT)
            
            log_request_response(session_id, "DETAILS", url, params, response.status_code, response.text, proxy_used=proxy_url)

            if response.status_code == 400 or response.status_code == 403:
                error_type = analyze_error(response.text, response.status_code)
                
                if error_type == 'SESSION_EXPIRED':
                    log_step("Details", "WARNING", f"Session expired (attempt {attempt + 1}/{max_retries})")
                    
                    if attempt < max_retries - 1:
                        new_session = recover_session()
                        if new_session:
                            session = new_session
                            session_id = id(session)
                        time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                        continue
                    else:
                        proxy_manager.record_proxy_result(proxy_url, success=False)
                        return {}, session
                
                elif error_type == 'NOT_FOUND':
                    log_step("Details", "INFO", f"Details not found for {employer['employer_name']}")
                    proxy_manager.record_proxy_result(proxy_url, success=True)
                    return {}, session
                
                elif error_type == 'PROXY_ERROR':
                    log_step("Details", "WARNING", f"Proxy error for {employer['employer_name']}. Rotating proxy...")
                    proxy_manager.record_proxy_result(proxy_url, success=False)
                    
                    if attempt < max_retries - 1:
                        time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                        continue
                    else:
                        return {}, session
                
                else:
                    log_step("Details", "WARNING", f"Unknown error for {employer['employer_name']}")
                    proxy_manager.record_proxy_result(proxy_url, success=False)
                    return {}, session

            if response.status_code != 200:
                log_step("Details", "ERROR", f"Details request failed: {response.status_code}")
                proxy_manager.record_proxy_result(proxy_url, success=False)
                
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                    continue
                else:
                    return {}, session

            soup = BeautifulSoup(response.text, "html.parser")
            policy_data = {}

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
                    log_step("Details", "SUCCESS", f"Found details for {policy_data['employer_name']}")
                    break

            proxy_manager.record_proxy_result(proxy_url, success=True)
            return policy_data, session

        except Exception as e:
            log_step("Details", "ERROR", f"Details exception (attempt {attempt + 1}/{max_retries}): {str(e)}")
            traceback.print_exc()
            proxy_manager.record_proxy_result(proxy_url, success=False)
            
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY * (PROXY_BACKOFF_FACTOR ** attempt))
                continue

    return {}, session


# ==========================================================
# DATA PROCESSING FUNCTIONS (UNCHANGED)
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
# MAIN PROCESSING (UPDATED WITH PROXY STATS)
# ==========================================================
def process_employer(session, employer_data, progress):
    """Process a single employer - ONLY save progress if session is valid"""
    bureau_number = employer_data["bureau_number"]
    employer_name = employer_data["employer_name"]
    zip_code = employer_data["zip_code"]
    coverage_date = employer_data["coverage_date"]

    log_step("Processing", "INFO", f"Processing Bureau #{bureau_number}: {employer_name}")

    if not check_session_valid(session):
        log_step("Processing", "ERROR", "Session is invalid before processing")
        return None, session, False

    search_results, session = search_policy_holders_with_recovery(
        session, employer_name, coverage_date, zip_code
    )

    if not check_session_valid(session):
        log_step("Processing", "ERROR", "Session became invalid during search")
        return None, session, False

    if not search_results:
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
        return [result], session, True

    all_results = []
    session_valid = True
    
    for search_result in search_results:
        if not check_session_valid(session):
            log_step("Processing", "ERROR", "Session became invalid before details")
            session_valid = False
            break
            
        details, session = get_policy_details_with_recovery(
            session, search_result, coverage_date
        )
        
        if not check_session_valid(session):
            log_step("Processing", "ERROR", "Session became invalid during details")
            session_valid = False
            break

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
            log_step("Processing", "SUCCESS", f"Found details for {details['employer_name']}")
        else:
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
            log_step("Processing", "WARNING", f"Details not found for {search_result['employer_name']}")
        
        all_results.append(result)

    if not session_valid:
        log_step("Processing", "ERROR", f"Session invalid during processing of {employer_name}")
        return None, session, False

    log_step("Processing", "SUCCESS", f"Completed processing for {employer_name}: {len(all_results)} results")
    return all_results, session, True


def main():
    """Main execution function with proxy integration"""
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", "🚀 WORKERS COMP COVERAGE SCRAPER WITH PROXY ROTATION")
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", f"Proxy Method: {PROXY_INTEGRATION_METHOD}")
    if PROXY_INTEGRATION_METHOD == "PROXY_GATEWAY":
        log_step("Main", "INFO", f"Gateway URL: {PROXY_GATEWAY_URL}")
    else:
        log_step("Main", "INFO", f"Proxy Manager: {PROXY_MANAGER_URL}")
    log_step("Main", "INFO", "Workflow:")
    log_step("Main", "INFO", "1. Browser will open with proxy - handle CAPTCHA/disclaimer")
    log_step("Main", "INFO", "2. System will handle OTP automatically")
    log_step("Main", "INFO", "3. Processing will continue with proxy rotation")
    log_step("Main", "INFO", "4. Invalid sessions/proxies will trigger recovery")
    log_step("Main", "INFO", "=" * 60)

    # Display proxy stats at startup
    stats = proxy_manager.get_stats()
    log_step("Proxy Stats", "INFO", f"Initial Stats - Total: {stats['total_requests']}, Success Rate: {stats['success_rate']:.1f}%")

    if not os.path.exists(INPUT_CSV):
        log_step("Main", "ERROR", f"Input file {INPUT_CSV} not found!")
        return

    log_step("Main", "INFO", "Launching browser with proxy...")
    driver = initialize_browser()
    if not driver:
        log_step("Main", "ERROR", "Failed to initialize browser with proxy")
        return

    session = load_requests_session()
    if not session:
        session = convert_cookies_to_requests_session()
        if session:
            save_requests_session(session)
        else:
            log_step("Main", "ERROR", "Failed to create session with proxy")
            return

    if not check_session_valid(session):
        log_step("Main", "WARNING", "Initial session invalid, recovering...")
        session = recover_session()
        if not session:
            log_step("Main", "ERROR", "Failed to recover session with proxy")
            return

    progress = load_progress()
    employers = read_input_csv(INPUT_CSV)

    if not employers:
        log_step("Main", "ERROR", "No employers to process")
        return

    pending_employers = [
        e for e in employers if e["bureau_number"] not in progress["completed"]
    ]

    if not pending_employers:
        log_step("Main", "SUCCESS", "All employers already processed!")
        save_final_output(progress["results"])
        
        # Display final proxy stats
        final_stats = proxy_manager.get_stats()
        log_step("Proxy Stats", "SUCCESS", 
                f"Final Stats - Total: {final_stats['total_requests']}, "
                f"Success: {final_stats['successful_requests']}, "
                f"Failed: {final_stats['failed_requests']}, "
                f"Success Rate: {final_stats['success_rate']:.1f}%")
        
        return

    log_step("Main", "INFO", f"Starting with {len(pending_employers)} employers pending")

    total_processed = 0
    start_time = time.time()
    consecutive_failures = 0
    max_consecutive_failures = 3

    for employer in pending_employers:
        results, session, session_valid = process_employer(session, employer, progress)

        if results and session_valid:
            with progress_lock:
                progress["results"].extend(results)
                progress["completed"].append(employer["bureau_number"])
                save_progress(progress)

            total_processed += 1
            consecutive_failures = 0

            if total_processed % 5 == 0:
                save_requests_session(session)
                # Display periodic proxy stats
                stats = proxy_manager.get_stats()
                log_step("Proxy Stats", "INFO", 
                        f"Progress Update - Requests: {stats['total_requests']}, "
                        f"Success Rate: {stats['success_rate']:.1f}%")

            percentage = (total_processed / len(pending_employers)) * 100
            elapsed_time = time.time() - start_time
            avg_time = elapsed_time / total_processed if total_processed > 0 else 0
            remaining = avg_time * (len(pending_employers) - total_processed)
            
            log_step("Progress", "INFO", 
                    f"Completed {total_processed}/{len(pending_employers)} "
                    f"({percentage:.1f}%) - "
                    f"Elapsed: {elapsed_time:.0f}s, "
                    f"ETA: {remaining:.0f}s")

            time.sleep(1)
            
        else:
            consecutive_failures += 1
            log_step("Progress", "WARNING", 
                    f"Session invalid for {employer['employer_name']}, not saving progress. "
                    f"Consecutive failures: {consecutive_failures}/{max_consecutive_failures}")
            
            if consecutive_failures >= max_consecutive_failures:
                log_step("Progress", "ERROR", 
                        f"Too many consecutive failures ({consecutive_failures}). "
                        f"Attempting full session recovery with new proxy...")
                
                new_session = recover_session()
                if new_session:
                    session = new_session
                    consecutive_failures = 0
                    log_step("Progress", "SUCCESS", "Session recovered with new proxy, retrying current employer...")
                    continue
                else:
                    log_step("Progress", "ERROR", "Failed to recover session, stopping...")
                    break
            
            time.sleep(2)

    if progress["results"]:
        save_final_output(progress["results"])
    else:
        log_step("Main", "WARNING", "No results to save")

    # Display final statistics
    final_stats = proxy_manager.get_stats()
    
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", "📊 PROCESSING COMPLETE!")
    log_step("Main", "INFO", "=" * 60)
    log_step("Main", "INFO", f"Total Employers Processed: {total_processed}")
    log_step("Main", "INFO", f"Total Time: {time.time() - start_time:.2f} seconds")
    log_step("Main", "INFO", f"Total Records Found: {len(progress['results'])}")
    log_step("Main", "INFO", "=" * 60)
    log_step("Proxy Stats", "SUCCESS", 
            f"Proxy Performance - Total Requests: {final_stats['total_requests']}")
    log_step("Proxy Stats", "SUCCESS", 
            f"Successful: {final_stats['successful_requests']}, "
            f"Failed: {final_stats['failed_requests']}")
    log_step("Proxy Stats", "SUCCESS", 
            f"Success Rate: {final_stats['success_rate']:.1f}%")
    log_step("Main", "INFO", "=" * 60)

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
        if driver_instance:
            try:
                driver_instance.quit()
            except:
                pass
        log_step("Main", "INFO", "Script ended.")