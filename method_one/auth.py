import json

import requests

from config import API_REQUEST_OTP, API_SUBMIT_OTP, EMAIL

AUTH_FILE = "auth.json"


def get_initial_session():
    """Get initial session with all required cookies"""
    session = requests.Session()

    # Set headers to mimic a real browser
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
    )

    # First, visit the main search page to get initial cookies
    print("Getting initial cookies...")
    response = session.get("https://www.caworkcompcoverage.com/Search")
    response.raise_for_status()

    print(f"Initial cookies obtained: {len(session.cookies)} cookies")
    return session


def request_otp():
    session = get_initial_session()

    # Extract the anti-forgery token from cookies
    antiforgery_cookie = None
    for cookie in session.cookies:
        if "Antiforgery" in cookie.name:
            antiforgery_cookie = cookie.value
            break

    if not antiforgery_cookie:
        print("Warning: No anti-forgery cookie found")

    # Update headers for the API request
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "RequestVerificationToken": antiforgery_cookie or "",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.caworkcompcoverage.com",
        "Referer": "https://www.caworkcompcoverage.com/Search",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    payload = {"EmailAddress": EMAIL}

    print("Sending OTP request...")
    print(
        f"Using antiforgery token: {antiforgery_cookie[:20]}..."
        if antiforgery_cookie
        else "No antiforgery token"
    )

    r = session.post(API_REQUEST_OTP, json=payload, headers=headers)

    print(f"Status Code: {r.status_code}")
    print(f"Response Headers: {dict(r.headers)}")

    if r.status_code != 200:
        print(f"Response Text: {r.text}")
        r.raise_for_status()

    # Save the complete session state
    auth_data = {
        "cookies": requests.utils.dict_from_cookiejar(session.cookies),
        "antiforgery_token": antiforgery_cookie,
        "session_initialized": True,
    }

    with open(AUTH_FILE, "w") as f:
        json.dump(auth_data, f, indent=2)

    print("OTP request sent successfully. Check your email.")
    return True


def submit_otp(otp):
    # Load the saved session data
    try:
        with open(AUTH_FILE, "r") as f:
            auth_data = json.load(f)
    except:
        print("No saved session found. Please request OTP first.")
        return None

    session = requests.Session()

    # Restore all cookies
    if auth_data.get("cookies"):
        cookies_dict = auth_data["cookies"]
        for name, value in cookies_dict.items():
            session.cookies.set(name, value)

    # Get antiforgery token
    antiforgery_token = auth_data.get("antiforgery_token", "")

    # Update headers for OTP submission
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "RequestVerificationToken": antiforgery_token,
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.caworkcompcoverage.com",
        "Referer": "https://www.caworkcompcoverage.com/Search",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    payload = {"OneTimePasscode": otp}

    print("Submitting OTP...")
    r = session.post(API_SUBMIT_OTP, json=payload, headers=headers)

    print(f"Status Code: {r.status_code}")
    print(f"Response Headers: {dict(r.headers)}")

    if r.status_code != 200:
        print(f"Response Text: {r.text}")
        r.raise_for_status()

    data = r.json()
    print(f"OTP response: {data}")

    # Update auth data with new token and cookies
    auth_data.update(
        {
            "token": data.get("token"),
            "cookies": requests.utils.dict_from_cookiejar(session.cookies),
        }
    )

    with open(AUTH_FILE, "w") as f:
        json.dump(auth_data, f, indent=2)

    print("Authentication successful and saved.")
    return auth_data


def load_auth():
    try:
        with open(AUTH_FILE, "r") as f:
            auth_data = json.load(f)
            # Check if we have a token
            if auth_data.get("token"):
                return auth_data
            return None
    except:
        return None
