import os
import shutil
import tempfile

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

# Path to your existing Firefox profile
profile_path = "/home/abeselom/.mozilla/firefox/agzghh1w.default-release"

# Create temporary copy of profile, ignoring lock files
temp_profile_dir = tempfile.mkdtemp()
shutil.copytree(
    profile_path,
    temp_profile_dir,
    dirs_exist_ok=True,
    ignore=lambda d, files: [
        f for f in files if f == "lock" or f.endswith(".lock")
    ],
)

options = Options()
# Uncomment to run headless
# options.headless = True
options.add_argument(f"-profile")
options.add_argument(temp_profile_dir)

driver = webdriver.Firefox(
    service=Service(GeckoDriverManager().install()), options=options
)

driver.get("https://whatismyipaddress.com/")
print("Title:", driver.title)
input("Press Enter to quit...")
driver.quit()
