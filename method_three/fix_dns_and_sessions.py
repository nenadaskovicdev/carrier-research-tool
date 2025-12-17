"""
Script to diagnose and fix DNS/proxy issues
"""
import socket
import os
import pickle
import json

def test_dns_resolution():
    """Test if we can resolve the Bright Data proxy hostname"""
    print("=" * 60)
    print("DNS RESOLUTION TEST")
    print("=" * 60)
    
    hostname = 'brd.superproxy.io'
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ SUCCESS: Resolved {hostname} to {ip}")
        return True
    except socket.gaierror as e:
        print(f"❌ FAILED: Cannot resolve {hostname}")
        print(f"Error: {e}")
        print("\nPossible causes:")
        print("1. No internet connection")
        print("2. DNS server issues")
        print("3. Firewall blocking DNS queries")
        print("4. ISP blocking Bright Data domains")
        return False

def clear_session_files():
    """Clear all cached session files"""
    print("\n" + "=" * 60)
    print("CLEARING SESSION FILES")
    print("=" * 60)
    
    files_to_clear = [
        "browser_cookies_fast_1.pkl",
        "requests_session_fast_1.pkl",
        "proxy_status.json"
    ]
    
    cleared = 0
    for filename in files_to_clear:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"✅ Removed: {filename}")
                cleared += 1
            except Exception as e:
                print(f"❌ Failed to remove {filename}: {e}")
        else:
            print(f"⚠️  Not found: {filename}")
    
    print(f"\n✅ Cleared {cleared} session files")
    return cleared

def check_proxy_status_file():
    """Check and display proxy status"""
    print("\n" + "=" * 60)
    print("PROXY STATUS CHECK")
    print("=" * 60)
    
    if os.path.exists("proxy_status.json"):
        try:
            with open("proxy_status.json", "r") as f:
                status = json.load(f)
            
            print(f"Total requests: {status.get('total_requests', 0)}")
            print(f"Failed requests: {status.get('failed_requests', 0)}")
            
            print("\nProxy details:")
            for proxy_url, stats in status.get('proxies', {}).items():
                success = stats.get('success', 0)
                failures = stats.get('failures', 0)
                total = success + failures
                success_rate = (success / total * 100) if total > 0 else 0
                print(f"  Success: {success}, Failures: {failures}, Rate: {success_rate:.1f}%")
        except Exception as e:
            print(f"❌ Error reading proxy status: {e}")
    else:
        print("⚠️  No proxy status file found")

def test_internet_connectivity():
    """Test basic internet connectivity"""
    print("\n" + "=" * 60)
    print("INTERNET CONNECTIVITY TEST")
    print("=" * 60)
    
    test_hosts = [
        ('google.com', '8.8.8.8'),
        ('cloudflare.com', '1.1.1.1'),
    ]
    
    for hostname, expected_ip in test_hosts:
        try:
            ip = socket.gethostbyname(hostname)
            print(f"✅ {hostname} resolved to {ip}")
        except socket.gaierror:
            print(f"❌ Failed to resolve {hostname}")
            return False
    
    return True

def main():
    print("\n🔧 DIAGNOSTIC AND FIX TOOL FOR SCRAPER ISSUES\n")
    
    # Test internet connectivity
    internet_ok = test_internet_connectivity()
    
    if not internet_ok:
        print("\n❌ CRITICAL: No internet connectivity detected!")
        print("Please check your network connection and try again.")
        return
    
    # Test DNS resolution for Bright Data
    dns_ok = test_dns_resolution()
    
    if not dns_ok:
        print("\n⚠️  WARNING: Cannot resolve Bright Data proxy hostname")
        print("This will cause connection failures in the scraper.")
        print("\nRecommended actions:")
        print("1. Check if your ISP blocks Bright Data")
        print("2. Try using a different DNS server (e.g., 8.8.8.8)")
        print("3. Check firewall settings")
        print("4. Contact Bright Data support")
    
    # Check proxy status
    check_proxy_status_file()
    
    # Ask user if they want to clear sessions
    print("\n" + "=" * 60)
    response = input("\nDo you want to clear all session files? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        clear_session_files()
        print("\n✅ Session files cleared. The scraper will create fresh sessions on next run.")
    else:
        print("\n⚠️  Session files not cleared.")
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    
    if dns_ok:
        print("\n✅ DNS resolution is working. You can run the scraper.")
    else:
        print("\n❌ DNS resolution is NOT working. Fix network issues before running scraper.")

if __name__ == "__main__":
    main()
