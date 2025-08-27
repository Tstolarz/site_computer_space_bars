#!/usr/bin/env python3
# If chrome gets updated go to this site: https://googlechromelabs.github.io/chrome-for-testing/#stable
# Download the mac-arm64 version and replace the chromedriver-mac-arm64 folder with the new one
# Open the terminal and run the command: cd /Users/timothystolarz/python_projects/side_projects/25_01_27_computer_space_bars/chromedriver-mac-arm64
# xattr -d com.apple.quarantine chromedriver

import pickle
import re
import sys
import time
import os
import glob
import argparse
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import matplotlib
# Use a non-interactive backend so plotting can work on a headless server
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

######################
# User-configurable
######################

# Where to save the final figure
OUTPUT_FIGURE_PATH = "/path/to/working/folder/output"

# If your server or environment can't open a GUI, we should run in headless mode:
HEADLESS = True

# WebDriver Path (change according to your driver)
CHROME_DRIVER_PATH = "/path/to/working/folder/chromedriver-mac-arm64/chromedriver"

# Cookie path
COOKIE_PATH = "/path/to/working/folder/cookies"

# Credentials file path (JSON file containing login information)
CREDENTIALS_FILE = "credentials.json"

# Debug mode - set to True to see detailed output about what's found on each page
DEBUG_MODE = False

site_list = [
    'NANT', 'BLCK', 'AMAG', 'MRCH', 'HEMP', 'HOOK', 'LOVE', 'BRIG', 'WILD', # 5 MHz
    'SILD', 'OLDB', 'PORT', 'CAPE', 'CMPT', 'LEWE', 'HLPN',                 # 25 MHz
    'SEAB', 'BRAD', 'SPRK', 'HLGT', 'BRMR', 'RATH', 'WOOD'                  # 13 MHz
]

print("Spinning up WebDriver...")
rws_link_prefix = 'http://'
rws_link_suffix = '-maracoos.dyndns.org:8240'

# Global variables for credentials (loaded from JSON)
username = None
password_dict = None

def load_credentials():
    """
    Load credentials from the JSON file in the same directory as the script.
    Returns (username, password_dict) or raises an exception if the file is not found or invalid.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(script_dir, CREDENTIALS_FILE)
    
    try:
        with open(credentials_path, 'r') as f:
            credentials = json.load(f)
        
        if 'username' not in credentials or 'passwords' not in credentials:
            raise ValueError("Credentials file must contain 'username' and 'passwords' keys")
        
        return credentials['username'], credentials['passwords']
    
    except FileNotFoundError:
        print(f"Error: Credentials file '{CREDENTIALS_FILE}' not found in {script_dir}")
        print(f"Please create a credentials.json file with the following structure:")
        print("""{
    "username": "your_username",
    "passwords": {
        "SITE1": "password1",
        "SITE2": "password2",
        ...
    }
}""")
        sys.exit(1)
    
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in credentials file: {e}")
        sys.exit(1)
    
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


from selenium.webdriver.chrome.service import Service  # Import Service

def create_webdriver(headless=True):
    """Create and return a Selenium WebDriver with (optional) headless mode."""
    from selenium.webdriver.chrome.options import Options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    # Add additional options if needed:
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    # Create a Service object using the path to the driver
    service = Service(executable_path=CHROME_DRIVER_PATH)
    
    # Use both service and options parameters
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(25)
    return driver

def login_and_navigate(driver, site, password):
    """
    Given a driver, site name, and password,
    attempt to load the site login page and sign in.
    Returns True if login is successful, False otherwise.
    """
    full_url = f"{rws_link_prefix}{site}{rws_link_suffix}"

    # Open a new tab for each site (optional, you can also reuse the same tab)
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[-1])

    try:
        driver.get(full_url)
    except TimeoutException:
        print(f"Loading took too much time for {site}")
        return False

    # Attempt cookie load with improved error handling
    cookie_file_path = f"{COOKIE_PATH}/{site}cookies.pkl"
    cookies_loaded = False
    try:
        with open(cookie_file_path, "rb") as file:
            cookies = pickle.load(file)
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"[{site}] Error adding cookie: {e}")
                    # Delete corrupted cookie file and proceed with login
                    if os.path.exists(cookie_file_path):
                        os.remove(cookie_file_path)
                        print(f"[{site}] Deleted corrupted cookie file")
                    break
            
            # Try to refresh with timeout handling
            try:
                driver.refresh()
                cookies_loaded = True
                time.sleep(3)  # small delay after refresh
            except TimeoutException:
                print(f"[{site}] Timeout during page refresh after loading cookies. Proceeding with login.")
                # Delete problematic cookies and continue
                if os.path.exists(cookie_file_path):
                    os.remove(cookie_file_path)
                    print(f"[{site}] Deleted problematic cookie file")
                # Reload the original page
                try:
                    driver.get(full_url)
                except TimeoutException:
                    print(f"[{site}] Timeout reloading page after cookie refresh failure")
                    return False
                    
    except (FileNotFoundError, pickle.UnpicklingError, EOFError) as e:
        if DEBUG_MODE:
            print(f"[{site}] Cookie file issue: {e}. Will login with credentials.")
        pass

    # Check if we're already logged in by looking for /status or a known element
    # If not logged in, proceed with credentials
    try:
        # Wait for the login elements to appear or the site to redirect
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "login_username")))
        # If we do see the login fields, fill them in
        username_field = driver.find_element(By.NAME, 'login_username')
        username_field.send_keys(username)
        password_field = driver.find_element(By.NAME, 'login_password')
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)
        
        # Wait for redirect with better error handling
        try:
            WebDriverWait(driver, 15).until(EC.url_contains("/status"))
            print(f"[{site}] Logged in successfully.")
        except TimeoutException:
            # Check if we're on a different page that indicates successful login
            current_url = driver.current_url
            if "login" not in current_url.lower():
                print(f"[{site}] Login appears successful (redirected to: {current_url})")
            else:
                print(f"[{site}] Login may have failed - still on login page")
                return False

        # Save new cookies only if login was successful
        if not cookies_loaded:  # Only save if we didn't use existing cookies
            try:
                cookies = driver.get_cookies()
                # Ensure cookie directory exists
                os.makedirs(COOKIE_PATH, exist_ok=True)
                with open(cookie_file_path, "wb") as file:
                    pickle.dump(cookies, file)
                if DEBUG_MODE:
                    print(f"[{site}] Saved new cookies")
            except Exception as e:
                print(f"[{site}] Warning: Could not save cookies: {e}")

    except TimeoutException:
        # Possibly we are already logged in or the site didn't need login
        current_url = driver.current_url
        if "login" in current_url.lower():
            print(f"[{site}] Timeout waiting for login elements")
            return False
        else:
            if DEBUG_MODE:
                print(f"[{site}] No login required or already logged in (URL: {current_url})")
        pass
    except Exception as e:
        print(f"[{site}] Login exception: {e}")
        return False

    return True


def get_storage_info(driver, site):
    """
    Navigate to the 'details' page for `site` and return
    (internal_free, external_free) as integer percentages.
    Updated to handle new Codar Radial Suite format.
    """
    full_url = f"{rws_link_prefix}{site}{rws_link_suffix}/details"

    try:
        # Set a shorter timeout for the details page
        driver.set_page_load_timeout(15)
        driver.get(full_url)
        # Reset timeout back to default
        driver.set_page_load_timeout(25)
    except TimeoutException:
        print(f"[{site}] Timeout loading details page.")
        driver.set_page_load_timeout(25)  # Reset timeout
        return (None, None)

    internal_free = None
    external_free = None

    try:
        # First, try to find storage info in notice blocks anywhere on the page
        notice_blocks = driver.find_elements(By.XPATH, "//div[contains(@class, 'notice')]")
        
        if DEBUG_MODE:
            print(f"[{site}] Found {len(notice_blocks)} notice blocks:")
        
        storage_blocks = []
        for i, block in enumerate(notice_blocks):
            text = block.text
            if DEBUG_MODE:
                print(f"  Block {i}: {text[:100]}...")
            
            # Look for patterns indicating storage information
            if any(keyword in text.lower() for keyword in ['avail.', 'available', 'gb', 'free', 'used']):
                if any(keyword in text.lower() for keyword in ['volume', 'boot', 'disk', 'storage', 'codar']):
                    storage_blocks.append(text)
        
        if DEBUG_MODE:
            print(f"[{site}] Found {len(storage_blocks)} storage-related blocks")
        
        # Parse storage blocks
        if len(storage_blocks) > 0:
            internal_free = parse_free_percentage(storage_blocks[0])
            if DEBUG_MODE:
                print(f"[{site}] Internal storage: {internal_free}% from '{storage_blocks[0][:50]}...'")
                
        if len(storage_blocks) > 1:
            external_free = parse_free_percentage(storage_blocks[1])
            if DEBUG_MODE:
                print(f"[{site}] External storage: {external_free}% from '{storage_blocks[1][:50]}...'")
        
        # If we didn't find storage blocks in notices, try the original Processor approach
        if internal_free is None:
            try:
                processor_div = driver.find_element(By.XPATH, "//div[contains(@class, 'collapse_tab') and contains(text(), 'Processor')]")
                repsection = processor_div.find_element(By.XPATH, "following-sibling::div[contains(@class, 'repsection')]")
                processor_notices = repsection.find_elements(By.XPATH, ".//div[contains(@class, 'notice')]")
                
                if len(processor_notices) > 0:
                    internal_free = parse_free_percentage(processor_notices[0].text)
                if len(processor_notices) > 1:
                    external_free = parse_free_percentage(processor_notices[1].text)
                    
                if DEBUG_MODE:
                    print(f"[{site}] Found storage in Processor section: internal={internal_free}%, external={external_free}%")
                    
            except NoSuchElementException:
                if DEBUG_MODE:
                    print(f"[{site}] Processor section not found")
                pass

    except NoSuchElementException:
        print(f"[{site}] No storage information found on page.")
        return (None, None)
    except Exception as e:
        print(f"[{site}] Error parsing storage info: {e}")
        return (None, None)

    return (internal_free, external_free)


def parse_free_percentage(text_block):
    """
    Parse storage percentage from various text formats:
    - "Boot Volume has 476.47 GB available out of 1000.24 GB [48% avail.]"
    - "XX% free" or "XX% used" patterns
    Returns an integer free-space percentage or None if parsing fails.
    """
    if not text_block:
        return None
    
    # Look for [XX% avail.] pattern (new format)
    match_bracket = re.search(r'\[(\d+)\%\s*avail\.\]', text_block, re.IGNORECASE)
    if match_bracket:
        return int(match_bracket.group(1))
    
    # Look for "XX% avail." pattern
    match_avail = re.search(r'(\d+)\%\s*avail\.', text_block, re.IGNORECASE)
    if match_avail:
        return int(match_avail.group(1))
    
    # Look for "XX% available" pattern
    match_available = re.search(r'(\d+)\%\s*available', text_block, re.IGNORECASE)
    if match_available:
        return int(match_available.group(1))
    
    # Look for "XX% free" pattern
    match_free = re.search(r'(\d+)\%\s*free', text_block, re.IGNORECASE)
    if match_free:
        return int(match_free.group(1))

    # Look for "XX% used" pattern and convert
    match_used = re.search(r'(\d+)\%\s*used', text_block, re.IGNORECASE)
    if match_used:
        used_val = int(match_used.group(1))
        return 100 - used_val
    
    # Try to extract from "X.XX GB available out of Y.YY GB" format
    match_gb = re.search(r'(\d+\.?\d*)\s*gb\s*available\s*out\s*of\s*(\d+\.?\d*)\s*gb', text_block, re.IGNORECASE)
    if match_gb:
        available = float(match_gb.group(1))
        total = float(match_gb.group(2))
        if total > 0:
            percentage = int((available / total) * 100)
            return percentage

    if DEBUG_MODE:
        print(f"Could not parse percentage from: '{text_block[:100]}...'")
    
    return None


def create_figure(results, output_path):
    """
    Takes `results` (list of dicts with keys: site, internal_free, external_free),
    creates a horizontal bar chart, and saves to `output_path`.

    Features:
    1. Leaves an empty space for sites that can't be accessed (i.e., missing data).
    2. Colors each bar based on free-space percentage:
       100–50: green, 50–35: yellow, 35–20: orange, 20–0: red.
    3. Differentiates internal vs external storage using hatch patterns.
    4. Moves the legend outside the plot to the top right.
    5. Adds vertical padding between each site group while keeping the two bars for the same site contiguous.
    6. Inserts an extra vertical gap between frequency groups.
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import Patch

    def get_color(free_val):
        if free_val >= 50:
            return 'green'
        elif free_val >= 35:
            return 'yellow'
        elif free_val >= 20:
            return 'orange'
        else:
            return 'red'

    # Define a mapping from site to frequency group.
    frequency_mapping = {
        'NANT': '5MHz', 'BLCK': '5MHz', 'AMAG': '5MHz', 'MRCH': '5MHz', 'HEMP': '5MHz',
        'HOOK': '5MHz', 'LOVE': '5MHz', 'BRIG': '5MHz', 'WILD': '5MHz',
        'SILD': '25MHz', 'OLDB': '25MHz', 'PORT': '25MHz', 'CAPE': '25MHz',
        'CMPT': '25MHz', 'LEWE': '25MHz', 'HLPN': '25MHz',
        'SEAB': '13MHz', 'BRAD': '13MHz', 'SPRK': '13MHz', 'HLGT': '13MHz',
        'BRMR': '13MHz', 'RATH': '13MHz', 'WOOD': '13MHz'
    }

    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    save_time = datetime.now().strftime("%Y%m%d_%H%M")
    save_name = f"MARACOOS_Storage_Space_{save_time}.png"
    full_output_path = f"{output_path}/{save_name}"
    
    # Ensure output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Reverse the results for plotting order.
    ordered_results = results[::-1]
    n_groups = len(ordered_results)
    
    # Parameters for group heights and gaps.
    group_height = 0.8       # Height for each site's group (both internal and external bars)
    regular_gap = 0.5        # Regular gap between sites
    extra_freq_gap = 1.0     # Extra gap inserted when frequency group changes

    # Compute y-positions for each site group, adding extra gap when the frequency changes.
    y_positions = []
    current_y = 0
    previous_freq = None
    for r in ordered_results:
        site = r["site"]
        freq = frequency_mapping.get(site, None)
        if previous_freq is not None and freq != previous_freq:
            current_y += extra_freq_gap
        y_positions.append(current_y)
        current_y += group_height + regular_gap
        previous_freq = freq

    # Compute y-tick positions (center of each group)
    y_tick_positions = [y + group_height/2 for y in y_positions]
    site_labels = [r["site"] for r in ordered_results]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot each site's bars.
    for idx, (r, y_pos) in enumerate(zip(ordered_results, y_positions)):
        # Internal storage: lower half of the group.
        if r["internal_free"] is not None:
            color_internal = get_color(r["internal_free"])
            ax.barh(y_pos, r["internal_free"], height=group_height/2,
                    color=color_internal, edgecolor='black', align='edge')
            center_internal = y_pos + (group_height/2) / 2
            ax.annotate(f'{r["internal_free"]}%',
                        xy=(r["internal_free"], center_internal),
                        xytext=(3, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=8)
        # External storage: upper half of the group.
        if r["external_free"] is not None:
            color_external = get_color(r["external_free"])
            external_y = y_pos + group_height/2
            ax.barh(external_y, r["external_free"], height=group_height/2,
                    color=color_external, hatch='//', edgecolor='black', align='edge')
            center_external = external_y + (group_height/2) / 2
            ax.annotate(f'{r["external_free"]}%',
                        xy=(r["external_free"], center_external),
                        xytext=(3, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=8)
    
    ax.set_xlabel('Free Space (%)')
    ax.set_xlim([0, 100])
    ax.set_yticks(y_tick_positions)
    ax.set_yticklabels(site_labels)
    ax.set_title('RUCODAR Site Computer Storage Space as of ' + current_time)
    
    legend_handles = [
        Patch(facecolor='gray', label='Internal Free (%)'),
        Patch(facecolor='gray', hatch='//', label='External Free (%)')
    ]
    ax.legend(handles=legend_handles, bbox_to_anchor=(1.0, 1.0), loc='upper left', borderaxespad=0.)
    
    plt.tight_layout()
    plt.savefig(full_output_path, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {full_output_path}")


def main():
    # Load credentials at startup
    global username, password_dict
    username, password_dict = load_credentials()
    print(f"Loaded credentials for {len(password_dict)} sites")

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='MARACOOS Storage Space Monitor')
    parser.add_argument('--refresh-cookies', action='store_true', 
                       help='Force refresh of all cookies by deleting existing ones')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode for detailed output')
    args = parser.parse_args()

    # Set global debug mode
    global DEBUG_MODE
    DEBUG_MODE = args.debug

    # Handle cookie refresh
    if args.refresh_cookies:
        cookie_files = glob.glob(f"{COOKIE_PATH}/*.pkl")
        for cookie_file in cookie_files:
            os.remove(cookie_file)
        print(f"Deleted {len(cookie_files)} existing cookie files. Will create fresh ones.")

    # Ensure cookie directory exists
    os.makedirs(COOKIE_PATH, exist_ok=True)

    driver = create_webdriver(headless=HEADLESS)

    # For each site, login and gather storage stats
    results = []  # Will hold dicts like: {"site": site, "internal_free": X, "external_free": Y}

    for site in site_list:
        print(f"Accessing site: {site}")
        if site not in password_dict:
            print(f"No password found for site {site}; skipping.")
            continue

        success = login_and_navigate(driver, site, password_dict[site])
        if not success:
            results.append({"site": site, "internal_free": None, "external_free": None})
            continue
        else:
            print(f"Successfully logged in to {site}")

        internal_free, external_free = get_storage_info(driver, site)
        results.append({
            "site": site,
            "internal_free": internal_free,
            "external_free": external_free
        })

        if DEBUG_MODE:
            print(f"[{site}] Final result: internal={internal_free}%, external={external_free}%")

        # Close the site tab if you want to keep things clean
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[-1])

    driver.quit()

    # Print summary
    print("\n=== STORAGE SUMMARY ===")
    for result in results:
        site = result["site"]
        internal = result["internal_free"]
        external = result["external_free"]
        internal_str = f"{internal}%" if internal is not None else "N/A"
        external_str = f"{external}%" if external is not None else "N/A"
        print(f"{site}: Internal={internal_str}, External={external_str}")

    # Generate the horizontal bar chart figure with extra frequency-group padding
    create_figure(results, OUTPUT_FIGURE_PATH)


if __name__ == "__main__":
    main()