import json

import browser_cookie3
import requests

from config import EMAIL

AUTH_FILE = "auth.json"


def get_browser_cookies():
    """Extract cookies from Chrome browser"""
    try:
        # Try to get cookies from Chrome
        cj = browser_cookie3.chrome(domain_name="caworkcompcoverage.com")
        cookies_dict = {}

        for cookie in cj:
            cookies_dict[cookie.name] = cookie.value

        print(f"Found {len(cookies_dict)} cookies from browser")
        return cookies_dict
    except Exception as e:
        print(f"Error getting browser cookies: {e}")
        return None


def request_otp_browser_cookies():
    """Use browser cookies to request OTP"""
    cookies_dict = get_browser_cookies()

    if not cookies_dict:
        print("No browser cookies found")
        return False

    session = requests.Session()

    # Add all cookies to session
    for name, value in cookies_dict.items():
        session.cookies.set(name, value)

    # Headers from your curl command
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json; charset=utf-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.caworkcompcoverage.com",
        "Connection": "keep-alive",
        "Referer": "https://www.caworkcompcoverage.com/Search",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

    # Extract anti-forgery token from cookies
    antiforgery_token = None
    for name, value in cookies_dict.items():
        if "Antiforgery" in name:
            antiforgery_token = value
            break

    if antiforgery_token:
        headers["RequestVerificationToken"] = antiforgery_token

    payload = {"EmailAddress": EMAIL}

    try:
        response = session.post(
            "https://www.caworkcompcoverage.com/bot-prevention/submit-one-time-passcode-initiation-request",
            json=payload,
            headers=headers,
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("OTP request sent successfully using browser cookies")

            # Save the session
            auth_data = {
                "cookies": cookies_dict,
                "antiforgery_token": antiforgery_token,
                "method": "browser_cookies",
            }

            with open(AUTH_FILE, "w") as f:
                json.dump(auth_data, f, indent=2)

            return True
        else:
            print(f"Failed: {response.text}")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False
