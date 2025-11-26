import json
import os
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import EMAIL

AUTH_FILE = "auth.json"


def setup_undetected_chrome():
    """Setup undetected Chrome driver to bypass bot detection"""
    options = uc.ChromeOptions()

    # Add options to make it look more like a real browser
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = uc.Chrome(options=options)

    # Execute script to remove webdriver properties
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


def request_otp_selenium():
    driver = setup_undetected_chrome()

    try:
        print("Navigating to search page...")
        driver.get("https://www.caworkcompcoverage.com/Search")

        # Wait for page to load completely
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        print("Page loaded successfully")

        # Look for email input field - try different selectors
        email_selectors = [
            "input[name='EmailAddress']",
            "input[type='email']",
            "input[placeholder*='email' i]",
            "input[placeholder*='Email' i]",
            "#EmailAddress",
            ".email-input",
            "input[id*='Email']",
        ]

        email_field = None
        for selector in email_selectors:
            try:
                email_field = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                print(f"Found email field with selector: {selector}")
                break
            except:
                continue

        if not email_field:
            print(
                "Could not find email field. Taking screenshot for debugging..."
            )
            driver.save_screenshot("debug_email_field.png")
            print("Page source saved to debug_page.html")
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return False

        # Fill email
        email_field.clear()
        email_field.send_keys(EMAIL)
        print("Email filled")

        # Look for send OTP button
        button_selectors = [
            "button[type='submit']",
            "button:contains('Send OTP')",
            "input[type='submit']",
            "button[onclick*='otp']",
            ".btn-primary",
            "button.btn",
        ]

        submit_button = None
        for selector in button_selectors:
            try:
                if "contains" in selector:
                    # Use XPath for text contains
                    xpath_selector = f"//button[contains(text(), 'Send OTP')]"
                    submit_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_selector))
                    )
                else:
                    submit_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                print(f"Found submit button with selector: {selector}")
                break
            except:
                continue

        if not submit_button:
            # Try to find by text using XPath
            try:
                submit_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//*[contains(text(), 'Send OTP') or contains(text(), 'Request OTP') or contains(text(), 'Get OTP')]",
                        )
                    )
                )
                print("Found submit button by text")
            except:
                print("Could not find submit button. Taking screenshot...")
                driver.save_screenshot("debug_submit_button.png")
                return False

        # Click the button
        driver.execute_script("arguments[0].click();", submit_button)
        print("OTP request submitted")

        # Wait for success message
        try:
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located(
                    (
                        By.XPATH,
                        "//*[contains(text(), 'sent') or contains(text(), 'success') or contains(text(), 'check your email')]",
                    )
                )
            )
            print("OTP sent successfully!")
        except:
            print("Waiting for OTP sent confirmation...")
            time.sleep(5)

        # Save cookies for later use
        cookies = driver.get_cookies()
        auth_data = {"cookies": cookies, "method": "selenium", "email": EMAIL}

        with open(AUTH_FILE, "w") as f:
            json.dump(auth_data, f, indent=2)

        print("Session saved successfully")
        return True

    except Exception as e:
        print(f"Error during OTP request: {e}")
        # Take screenshot for debugging
        driver.save_screenshot("error_screenshot.png")
        return False
    finally:
        driver.quit()


def submit_otp_selenium(otp):
    driver = setup_undetected_chrome()

    try:
        # Load saved cookies
        with open(AUTH_FILE, "r") as f:
            auth_data = json.load(f)

        # Navigate to the page first
        driver.get("https://www.caworkcompcoverage.com/Search")

        # Load cookies
        for cookie in auth_data.get("cookies", []):
            driver.add_cookie(cookie)

        # Refresh to apply cookies
        driver.refresh()

        # Look for OTP input field
        otp_selectors = [
            "input[name='OneTimePasscode']",
            "input[type='text'][placeholder*='code' i]",
            "input[placeholder*='OTP' i]",
            "input[placeholder*='passcode' i]",
            "#OneTimePasscode",
            ".otp-input",
            "input[id*='Passcode']",
        ]

        otp_field = None
        for selector in otp_selectors:
            try:
                otp_field = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                print(f"Found OTP field with selector: {selector}")
                break
            except:
                continue

        if not otp_field:
            print("Could not find OTP field")
            return False

        # Fill OTP
        otp_field.clear()
        otp_field.send_keys(otp)
        print("OTP filled")

        # Look for verify button
        verify_selectors = [
            "button[type='submit']",
            "button:contains('Verify')",
            "button:contains('Submit')",
            "input[type='submit'][value*='Verify' i]",
            ".btn-primary",
        ]

        verify_button = None
        for selector in verify_selectors:
            try:
                if "contains" in selector:
                    xpath_selector = f"//button[contains(text(), 'Verify') or contains(text(), 'Submit')]"
                    verify_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_selector))
                    )
                else:
                    verify_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                print(f"Found verify button with selector: {selector}")
                break
            except:
                continue

        if not verify_button:
            print("Could not find verify button")
            return False

        # Click verify button
        driver.execute_script("arguments[0].click();", verify_button)
        print("OTP submitted")

        # Wait for authentication to complete
        time.sleep(5)

        # Check if we're still on the search page (success)
        if "Search" in driver.title or "search" in driver.current_url.lower():
            print("Authentication successful!")

            # Save updated cookies
            auth_data["cookies"] = driver.get_cookies()
            auth_data["authenticated"] = True

            with open(AUTH_FILE, "w") as f:
                json.dump(auth_data, f, indent=2)

            return True
        else:
            print("Authentication might have failed")
            return False

    except Exception as e:
        print(f"Error during OTP submission: {e}")
        return False
    finally:
        driver.quit()
