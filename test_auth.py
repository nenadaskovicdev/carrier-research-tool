import requests

from auth import load_auth, request_otp, submit_otp


def test_cookies():
    """Test if we can get the initial cookies"""
    session = requests.Session()
    response = session.get("https://www.caworkcompcoverage.com/Search")

    print("=== COOKIES OBTAINED ===")
    for cookie in session.cookies:
        print(f"{cookie.name}: {cookie.value}")

    print(f"\nTotal cookies: {len(session.cookies)}")
    print(f"Status Code: {response.status_code}")


def test_otp_request():
    """Test just the OTP request part"""
    try:
        request_otp()
        print("✓ OTP request successful")
        return True
    except Exception as e:
        print(f"✗ OTP request failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing cookie collection...")
    test_cookies()

    print("\nTesting OTP request...")
    test_otp_request()
