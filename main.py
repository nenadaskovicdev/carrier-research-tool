import getpass

from browser_cookie_auth import request_otp_browser_cookies
from selenium_auth import request_otp_selenium, submit_otp_selenium

from auth import load_auth
from client import get_client
from email_reader import get_otp_from_email, get_otp_simple
from search import search_worker_detailed
from storage import save_excel, save_json


def main():
    auth = load_auth()

    if not auth:
        print("=== WCIRB Automation ===")
        print("Choose authentication method:")
        print("1. Selenium (recommended - will open browser)")
        print("2. Browser cookies (requires Chrome with logged-in session)")

        choice = input("Enter choice (1 or 2): ").strip()

        if choice == "1":
            print("Using Selenium method...")
            success = request_otp_selenium()
        elif choice == "2":
            print("Using browser cookies method...")
            success = request_otp_browser_cookies()
        else:
            print("Invalid choice, using Selenium...")
            success = request_otp_selenium()

        if not success:
            print("Failed to request OTP. Please check the error messages.")
            return

        # Get OTP automatically or manually
        email_password = getpass.getpass(
            "Enter your email app password for auto-OTP (or press Enter for manual): "
        )
        otp = None

        if email_password:
            print("Attempting to read OTP automatically...")
            otp = get_otp_from_email(email_password)

        if not otp:
            otp = input("Enter OTP manually: ").strip()

        # Submit OTP
        if choice == "1":
            submit_otp_selenium(otp)
        else:
            # For browser cookies method, we'd need to implement submit_otp_browser_cookies
            print(
                "Browser cookies OTP submission not implemented yet. Please use Selenium method."
            )
            return

        auth = load_auth()

    if auth and auth.get("authenticated"):
        print("Authentication successful! Performing search...")

        # Example search
        search_data = {
            "EmployerName": "BAXTER AUTO PARTS, INC",
            "City": "PORTLAND",
            "State": "OR",
            "CoverageDate": "11/01/2025",
            "ZipCode": "97217",
        }

        try:
            session = get_client()
            result = search_worker_detailed(session, search_data)
            output = {"input": search_data, "result": result}
            save_json(output)
            save_excel(output)
            print("Search completed and saved successfully.")
        except Exception as e:
            print(f"Search failed: {e}")
    else:
        print("Authentication failed or not completed.")


if __name__ == "__main__":
    main()
