import json

import requests

AUTH_FILE = "auth.json"


def get_client():
    try:
        with open(AUTH_FILE, "r") as f:
            auth = json.load(f)
    except:
        raise Exception(
            "No authentication data found. Please run authentication first."
        )

    token = auth.get("token")
    antiforgery_token = auth.get("antiforgery_token", "")
    cookies_dict = auth.get("cookies", {})

    session = requests.Session()

    # Restore all cookies
    if cookies_dict:
        for name, value in cookies_dict.items():
            session.cookies.set(name, value)

    # Set headers
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.caworkcompcoverage.com",
        "Referer": "https://www.caworkcompcoverage.com/Search",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    # Add authorization if we have a token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Add anti-forgery token
    if antiforgery_token:
        headers["RequestVerificationToken"] = antiforgery_token

    session.headers.update(headers)

    return session
