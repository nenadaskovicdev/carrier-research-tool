from seleniumbase import SB


def verify_success(sb):
    """Check if we successfully bypassed Cloudflare and reached the target page"""
    # Check for the actual elements on your target website
    success_indicators = [
        'input[name*="search"]',  # Search inputs
        'input[type*="search"]',
        "#Search",  # Common ID for search pages
        ".search",  # Common class for search pages
        "h1",  # Any heading
        "title",  # Page title
    ]

    for indicator in success_indicators:
        if sb.is_element_visible(indicator):
            print(f"✅ Success indicator found: {indicator}")
            return True

    # Also check if we're still on a Cloudflare page
    page_source = sb.get_page_source().lower()
    if any(
        word in page_source
        for word in ["cloudflare", "challenge", "verifying", "checking"]
    ):
        print("❌ Still on Cloudflare page")
        return False

    # If we have reasonable page content and no Cloudflare, consider it success
    if len(page_source) > 1000:  # Reasonable page size
        print("✅ Page loaded with substantial content")
        return True

    return False


def manual_cloudflare_bypass(sb):
    """Manual approach for when automatic fails"""
    print("=" * 60)
    print("MANUAL CLOUDFLARE BYPASS REQUIRED")
    print("=" * 60)
    print("1. A browser window has opened")
    print("2. Please MANUALLY solve the Cloudflare challenge")
    print("3. Complete any CAPTCHAs or verification steps")
    print("4. Wait until you see the actual website")
    print("5. Then come back here and press Enter")
    print("=" * 60)

    input("Press Enter AFTER you have manually bypassed Cloudflare...")

    return verify_success(sb)


with SB(uc=True, headless=False) as sb:
    try:
        print("🌐 Opening website with undetected-chromedriver...")
        sb.uc_open_with_reconnect(
            "https://www.caworkcompcoverage.com/Search", 3
        )

        # Wait a bit for initial load
        sb.sleep(5)

        # Check if we successfully bypassed
        if verify_success(sb):
            print("🎉 Successfully bypassed Cloudflare automatically!")
        else:
            print("🔄 Automatic bypass failed, switching to manual mode...")

            # Try to find and click verify button if present
            if sb.is_element_visible('input[value*="Verify"]'):
                print("🔍 Found verify button, clicking...")
                sb.uc_click('input[value*="Verify"]')
                sb.sleep(5)

                if verify_success(sb):
                    print("🎉 Verify button worked!")
                else:
                    print("❌ Verify button didn't work")
                    if not manual_cloudflare_bypass(sb):
                        raise Exception(
                            "Failed to bypass Cloudflare even manually"
                        )
            else:
                print("🔍 No verify button found, trying manual bypass...")
                if not manual_cloudflare_bypass(sb):
                    raise Exception("Failed to bypass Cloudflare manually")

        # Success! Now we can interact with the page
        print("\n✅ SUCCESS! Cloudflare bypassed!")
        print(f"📄 Page Title: {sb.get_title()}")
        print(f"🌐 Current URL: {sb.get_current_url()}")

        # Take screenshot
        sb.save_screenshot("success.png")
        print("📸 Screenshot saved: success.png")

        # Save page source for inspection
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(sb.get_page_source())
        print("💾 Page source saved: page_source.html")

        # Keep browser open for further automation
        print("\n🔧 Browser remains open for automation...")
        input("Press Enter to close browser and continue...")

    except Exception as e:
        print(f"❌ Error: {e}")
        # Save debug info even on failure
        try:
            sb.save_screenshot("error.png")
            print("📸 Error screenshot saved: error.png")
        except:
            pass
