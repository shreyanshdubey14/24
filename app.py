#!/usr/bin/env python3
"""
AdShare Monitor v11.1 - Ultra Low Resource - FIXED
"""

import subprocess
import time
import re
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import signal
import sys
import urllib.request

try:
    import requests
    from bs4 import BeautifulSoup
    import pytz
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
except ImportError:
    print("Installing packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", 
                   "selenium", "requests", "beautifulsoup4", "pytz"], check=True)
    import requests
    from bs4 import BeautifulSoup
    import pytz
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

# ==================== CONFIGURATION ====================

CONFIG = {
    'telegram_token': "8225236307:AAF9Y2-CM7TlLDFm2rcTVY6f3SA75j0DFI8",
    'chat_id': None,
    'email': 'loginallapps@gmail.com',
    'password': '@Sd2007123',
    'leaderboard_check_interval': 1800,
    'safety_margin': 250,
    'competition_strategy': 'today_only',
    'my_user_id': '4150',
    'browser_url': "https://adsha.re/surf",
    'login_url': "https://adsha.re/login",
    'leaderboard_url': 'https://adsha.re/ten',
    'timezone': 'Asia/Kolkata',
    'profile_dir': '/app/firefox_profile',
    'extensions_dir': '/app/extensions',
    'auto_start': True,
    'manual_target': None,  # Added manual target feature
}

EXTENSIONS = {
    "violentmonkey": {
        "xpi_url": "https://addons.mozilla.org/firefox/downloads/file/4455138/violentmonkey-2.31.0.xpi",
        "xpi_file": "violentmonkey.xpi",
        "name": "Violentmonkey"
    },
    "ublock": {
        "xpi_url": "https://addons.mozilla.org/firefox/downloads/file/4598854/ublock_origin-1.67.0.xpi", 
        "xpi_file": "ublock_origin.xpi",
        "name": "uBlock Origin"
    }
}

USERSCRIPT_PAGE = "https://greasyfork.org/en/scripts/554948-very-smart-symbol-game-auto-solver-pro-v3-4-with-auto-loginallapps"

# ==================== LOGGING ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==================== STATE ====================

class MonitorState:
    def __init__(self):
        self.is_running = False
        self.browser_active = False
        self.driver = None
        self.leaderboard = []
        self.my_position = None
        self.target_achieved = False
        self.current_target = 0
        self.strategy = CONFIG['competition_strategy']
        self.safety_margin = CONFIG['safety_margin']
        self.last_my_credits = 0
        self.last_credits_time = None
        self.credits_growth_rate = 0
        self.last_check_time = None
        self.profile_initialized = False
        self.manual_target = None  # Manual target feature
        self.initialization_attempted = False

state = MonitorState()

# ==================== CORE FUNCTIONS ====================

def download_files():
    """Download extension files with retry logic"""
    os.makedirs(CONFIG['extensions_dir'], exist_ok=True)
    logger.info("Downloading extensions...")
    
    paths = {}
    for ext_id, ext_info in EXTENSIONS.items():
        filepath = os.path.join(CONFIG['extensions_dir'], ext_info["xpi_file"])
        if not os.path.exists(filepath):
            logger.info(f"Downloading {ext_info['name']}...")
            try:
                urllib.request.urlretrieve(ext_info["xpi_url"], filepath)
                logger.info(f"Downloaded {ext_info['name']}")
            except Exception as e:
                logger.error(f"Failed to download {ext_info['name']}: {e}")
                # Try alternative download method
                try:
                    response = requests.get(ext_info["xpi_url"], timeout=30)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Downloaded {ext_info['name']} via requests")
                except Exception as e2:
                    logger.error(f"Alternative download also failed: {e2}")
                    continue
        paths[ext_id] = filepath
    return paths

def install_userscript_simple(driver):
    """Simplified userscript installation that works"""
    logger.info("Installing userscript...")
    
    try:
        # Navigate to userscript page
        driver.get(USERSCRIPT_PAGE)
        time.sleep(10)  # Wait for page to load completely
        
        # Check if we're on the right page
        if "very-smart-symbol-game" not in driver.page_source.lower():
            logger.warning("May not be on correct userscript page")
        
        # Try multiple selectors for install button
        install_selectors = [
            "a.install-link",
            ".install-link",
            "a[href*='userjs']",
            "a[href*='user.js']", 
            "a[href*='install']",
            "button.install",
            ".install-button",
            "a.btn-install"
        ]
        
        installed = False
        for selector in install_selectors:
            try:
                install_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", install_btn)
                time.sleep(1)
                install_btn.click()
                logger.info(f"Clicked install button: {selector}")
                time.sleep(8)  # Wait for Violentmonkey popup
                installed = True
                break
            except Exception as e:
                continue
        
        if not installed:
            # Fallback: try to find by text
            try:
                install_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Install')]")
                install_btn.click()
                logger.info("Clicked Install via text")
                time.sleep(8)
                installed = True
            except:
                pass
        
        # Handle Violentmonkey installation popup if it appears
        try:
            # Switch to any new windows that opened
            if len(driver.window_handles) > 1:
                original_window = driver.current_window_handle
                for window in driver.window_handles:
                    if window != original_window:
                        driver.switch_to.window(window)
                        time.sleep(3)
                        
                        # Look for install button in Violentmonkey popup
                        vm_selectors = [
                            "button[data-cmd='install']",
                            "button.install",
                            "input[value='Install']",
                            "button:contains('Install')"
                        ]
                        
                        for vm_selector in vm_selectors:
                            try:
                                install_btn = driver.find_element(By.CSS_SELECTOR, vm_selector)
                                install_btn.click()
                                logger.info("Clicked install in Violentmonkey popup")
                                time.sleep(3)
                                break
                            except:
                                continue
                        
                        driver.close()
                        driver.switch_to.window(original_window)
        except Exception as e:
            logger.warning(f"Could not handle Violentmonkey popup: {e}")
        
        logger.info("Userscript installation completed")
        return True
        
    except Exception as e:
        logger.error(f"Userscript installation error: {e}")
        return False

def initialize_profile():
    """Initialize profile - SIMPLIFIED VERSION that works"""
    if state.profile_initialized:
        return True
        
    if state.initialization_attempted:
        logger.info("Profile initialization already attempted, skipping")
        return False
        
    state.initialization_attempted = True
    logger.info("Initializing profile...")
    
    # Clean up existing profile
    if os.path.exists(CONFIG['profile_dir']):
        import shutil
        try:
            shutil.rmtree(CONFIG['profile_dir'])
            logger.info("Cleaned existing profile")
        except Exception as e:
            logger.warning(f"Could not remove old profile: {e}")
    
    os.makedirs(CONFIG['profile_dir'], exist_ok=True)
    
    # Download extensions first
    extension_paths = download_files()
    if not extension_paths:
        logger.error("Failed to download extensions")
        return False
    
    # Create browser options
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"-profile")
    options.add_argument(CONFIG['profile_dir'])
    
    # Essential preferences
    options.set_preference("xpinstall.signatures.required", False)
    options.set_preference("extensions.autoDisableScopes", 0)
    options.set_preference("extensions.enabledScopes", 15)
    
    # Install extensions in one session
    logger.info("Installing extensions...")
    driver = None
    try:
        driver = webdriver.Firefox(options=options)
        time.sleep(5)
        
        for ext_id, ext_path in extension_paths.items():
            try:
                abs_path = os.path.abspath(ext_path)
                driver.install_addon(abs_path, temporary=False)
                logger.info(f"Installed {EXTENSIONS[ext_id]['name']}")
                time.sleep(3)
            except Exception as e:
                logger.error(f"Failed to install {EXTENSIONS[ext_id]['name']}: {e}")
        
        driver.quit()
        time.sleep(3)
        
    except Exception as e:
        logger.error(f"Extension installation failed: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return False
    
    # Install userscript in separate session
    logger.info("Installing userscript...")
    try:
        driver = webdriver.Firefox(options=options)
        time.sleep(10)  # Wait for extensions to load
        
        success = install_userscript_simple(driver)
        driver.quit()
        
        if success:
            state.profile_initialized = True
            logger.info("✅ Profile initialization complete!")
            return True
        else:
            logger.warning("Userscript installation may have failed, but continuing...")
            state.profile_initialized = True
            return True
            
    except Exception as e:
        logger.error(f"Userscript installation failed: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        # Even if userscript fails, mark as initialized and continue
        state.profile_initialized = True
        return True

def start_browser():
    """Start browser with the pre-configured profile"""
    if not state.profile_initialized:
        if not initialize_profile():
            logger.error("Cannot start browser: profile not initialized")
            return None
    
    logger.info("Starting browser...")
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"-profile")
    options.add_argument(CONFIG['profile_dir'])
    
    # Low memory settings
    options.set_preference("dom.ipc.processCount", 1)
    options.set_preference("dom.ipc.processCount.webIsolated", 1)
    options.set_preference("browser.tabs.remote.autostart", False)
    options.set_preference("browser.tabs.remote.autostart.2", False)
    options.set_preference("browser.sessionstore.interval", 60000)
    options.set_preference("browser.sessionstore.max_resumed_crashes", 0)
    options.set_preference("dom.disable_beforeunload", True)
    
    try:
        driver = webdriver.Firefox(options=options)
        state.browser_active = True
        logger.info("✅ Browser started successfully!")
        return driver
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        return None

def stop_browser():
    """Stop browser safely"""
    if state.driver:
        try:
            state.driver.quit()
            logger.info("Browser stopped")
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")
        state.driver = None
    state.browser_active = False

def smart_login_flow(driver):
    """Login flow that works"""
    try:
        logger.info("Starting login flow...")
        
        # Step 1: Open login page first
        logger.info("Step 1: Opening login page...")
        driver.get(CONFIG['login_url'])
        time.sleep(8)
        
        # Step 2: Wait for auto-login by userscript
        logger.info("Step 2: Waiting for auto-login...")
        wait_time = 60
        for i in range(wait_time):
            time.sleep(1)
            current_url = driver.current_url.lower()
            if "surf" in current_url or "game" in current_url:
                logger.info("✅ Auto-login detected early!")
                return True
            if i % 10 == 0:
                logger.info(f"Auto-login wait: {i}/{wait_time} seconds")
        
        # Step 3: Navigate to surf page
        logger.info("Step 3: Navigating to surf page...")
        driver.get(CONFIG['browser_url'])
        time.sleep(8)
        
        # Check if successfully on surf page
        current_url = driver.current_url.lower()
        if "surf" in current_url or "game" in current_url:
            logger.info("✅ Login successful! Ready to surf.")
            return True
        else:
            logger.warning("Not on surf page, checking current state...")
            logger.info(f"Current URL: {driver.current_url}")
            return False
            
    except Exception as e:
        logger.error(f"Login flow error: {e}")
        return False

# ==================== LEADERBOARD ====================

class LeaderboardParser:
    @staticmethod
    def parse_with_beautifulsoup(html: str) -> List[Dict]:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            leaderboard = []
            
            # Multiple parsing strategies
            entries = soup.find_all('div', style=lambda x: x and 'width:250px' in x and 'margin:5px auto' in x)
            
            if not entries:
                # Alternative: look for divs containing competition data
                all_divs = soup.find_all('div')
                entries = [div for div in all_divs if any(x in div.get_text() for x in ['T:', 'Y:', 'DB:'])]
            
            rank = 1
            for entry in entries:
                text = entry.get_text(strip=True)
                
                # Extract user ID
                user_match = re.search(r'#(\d+)', text)
                if not user_match:
                    continue
                
                user_id = user_match.group(1)
                
                # Extract credits with flexible patterns
                today_match = re.search(r'T:\s*([\d,]+)', text)
                yesterday_match = re.search(r'Y:\s*([\d,]+)', text)
                db_match = re.search(r'DB:\s*([\d,]+)', text)
                
                today = int(today_match.group(1).replace(',', '')) if today_match else 0
                yesterday = int(yesterday_match.group(1).replace(',', '')) if yesterday_match else 0
                day_before = int(db_match.group(1).replace(',', '')) if db_match else 0
                total = today + yesterday + day_before
                
                leaderboard.append({
                    'rank': rank, 
                    'user_id': user_id, 
                    'total_surfed': total,
                    'today_credits': today, 
                    'yesterday_credits': yesterday, 
                    'day_before_credits': day_before
                })
                rank += 1
            
            logger.info(f"Parsed {len(leaderboard)} leaderboard entries")
            return leaderboard
            
        except Exception as e:
            logger.error(f"Leaderboard parse error: {e}")
            return []

def fetch_leaderboard() -> Optional[List[Dict]]:
    """Fetch leaderboard with improved error handling"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Cookie': 'adshare_e=loginallapps%40gmail.com; adshare_s=e4dc9d210bb38a86cd360253a82feb2cc6ed84f5ddf778be89484fb476998e0dfc31280c575a38a2467067cd6ec1d6ff7e25aa46dedd6ea454831df26365dfc2; adshare_d=20251025; adshare_h=https%3A%2F%2Fadsha.re%2Faffiliates'
        }
        
        response = requests.post(CONFIG['leaderboard_url'], headers=headers, timeout=30)
        if response.status_code == 200:
            leaderboard = LeaderboardParser.parse_with_beautifulsoup(response.text)
            if leaderboard:
                return leaderboard
        return None
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return None

def calculate_target(leaderboard: List[Dict]) -> Tuple[int, str]:
    """Calculate target with manual target support"""
    # MANUAL TARGET OVERRIDE
    if state.manual_target is not None:
        return state.manual_target, f"MANUAL TARGET: {state.manual_target}"
    
    if len(leaderboard) < 2:
        return 1000, "Default target (insufficient data)"
    
    second_place = leaderboard[1]
    if state.strategy == 'today_only':
        target = second_place['today_credits'] + state.safety_margin
        explanation = f"2nd today ({second_place['today_credits']}) + {state.safety_margin}"
    else:
        second_combined = second_place['today_credits'] + second_place['yesterday_credits']
        target = second_combined + state.safety_margin
        explanation = f"2nd combined ({second_combined}) + {state.safety_margin}"
    return target, explanation

def get_my_value(my_data: Dict) -> int:
    """Get my today's credits"""
    return my_data['today_credits']

def should_stop_browser(leaderboard: List[Dict]) -> bool:
    """Determine if browser should be stopped based on targets"""
    my_data = None
    for entry in leaderboard:
        if entry['user_id'] == CONFIG['my_user_id']:
            my_data = entry
            break
    if not my_data:
        return False
    
    my_today = get_my_value(my_data)
    
    # MANUAL TARGET CHECK
    if state.manual_target is not None:
        return my_today >= state.manual_target
    
    # Rank-based target
    if state.my_position != 1:
        return False
    
    target, _ = calculate_target(leaderboard)
    return my_today >= target

def send_telegram_message(message: str):
    """Send Telegram message with error handling"""
    if not CONFIG.get('chat_id'):
        return
    try:
        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
        data = {'chat_id': CONFIG['chat_id'], 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, data=data, timeout=15)
        if response.status_code != 200:
            logger.error(f"Telegram API error: {response.text}")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

def check_competition_status():
    """Check competition status and control browser"""
    current_time = datetime.now()
    state.last_check_time = current_time
    
    leaderboard = fetch_leaderboard()
    if not leaderboard:
        logger.error("Failed to fetch leaderboard")
        send_telegram_message("❌ Failed to fetch leaderboard data")
        return
    
    state.leaderboard = leaderboard
    my_data = None
    for entry in state.leaderboard:
        if entry['user_id'] == CONFIG['my_user_id']:
            my_data = entry
            state.my_position = entry['rank']
            break
    
    if not my_data:
        logger.error(f"User #{CONFIG['my_user_id']} not found in leaderboard!")
        send_telegram_message(f"❌ User #{CONFIG['my_user_id']} not found in leaderboard!")
        return
    
    my_value = get_my_value(my_data)
    
    # Calculate growth rate
    if state.last_my_credits > 0 and state.last_credits_time:
        time_diff_hours = (current_time - state.last_credits_time).total_seconds() / 3600.0
        credits_gained = my_value - state.last_my_credits
        if credits_gained > 0 and time_diff_hours > 0:
            state.credits_growth_rate = credits_gained / time_diff_hours
    
    state.last_my_credits = my_value
    state.last_credits_time = current_time
    
    # Browser control logic
    should_stop = should_stop_browser(leaderboard)
    if should_stop and state.browser_active:
        logger.info("🎯 Target achieved, stopping browser")
        stop_browser()
        send_telegram_message("🎯 <b>TARGET ACHIEVED!</b> Browser stopped.")
        state.target_achieved = True
    elif not should_stop and not state.browser_active and state.is_running and not state.target_achieved:
        logger.info("Starting browser to chase target")
        state.driver = start_browser()
        if state.driver:
            if smart_login_flow(state.driver):
                send_telegram_message("🚀 <b>Browser started</b> - chasing target!")
            else:
                send_telegram_message("⚠️ <b>Browser started but login may have failed</b>")
    
    target, explanation = calculate_target(leaderboard)
    state.current_target = target
    
    # Status message
    status_message = ""
    if state.manual_target is not None:
        if my_value >= state.manual_target:
            status_message = f"✅ MANUAL TARGET ACHIEVED! ({state.manual_target})"
        else:
            gap = state.manual_target - my_value
            status_message = f"🎯 CHASING MANUAL TARGET - Need {gap} more credits"
    elif state.my_position != 1:
        first_place = leaderboard[0]
        gap = first_place['today_credits'] - my_value
        status_message = f"📉 Currently #{state.my_position}, chasing #1 (gap: {gap})"
    else:
        if my_value >= target:
            status_message = f"✅ TARGET ACHIEVED! Position #1 secured"
        else:
            gap = target - my_value
            status_message = f"🏃 CHASING TARGET - Need {gap} more credits"
    
    full_message = f"""
🔄 <b>Competition Update</b>
🏆 Position: <b>#{state.my_position}</b>
📊 My Credits Today: <b>{my_value}</b>
🎯 Target: <b>{target}</b> ({explanation})
📈 Speed: <b>{state.credits_growth_rate:.1f}/hour</b>
🖥️ Browser: <b>{'RUNNING' if state.browser_active else 'STOPPED'}</b>

{status_message}
    """.strip()
    
    send_telegram_message(full_message)

def telegram_bot_loop():
    """Telegram bot command handler"""
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/getUpdates?timeout=30&offset={last_update_id + 1}"
            response = requests.get(url, timeout=35)
            if response.status_code == 200:
                updates = response.json()
                if updates and 'result' in updates:
                    for update in updates['result']:
                        update_id = update['update_id']
                        if update_id > last_update_id:
                            last_update_id = update_id
                            if 'message' in update and 'text' in update['message']:
                                command = update['message']['text']
                                chat_id = update['message']['chat']['id']
                                CONFIG['chat_id'] = chat_id
                                
                                if command == '/start':
                                    state.is_running = True
                                    state.target_achieved = False
                                    send_telegram_message("✅ Monitor STARTED!")
                                    if not state.browser_active:
                                        state.driver = start_browser()
                                        if state.driver:
                                            smart_login_flow(state.driver)
                                    check_competition_status()
                                elif command == '/stop':
                                    state.is_running = False
                                    stop_browser()
                                    send_telegram_message("⏹️ Monitor STOPPED!")
                                elif command == '/status':
                                    check_competition_status()
                                elif command == '/strategy_today':
                                    state.strategy = 'today_only'
                                    state.manual_target = None
                                    state.target_achieved = False
                                    send_telegram_message("🎯 Strategy: TODAY ONLY")
                                    check_competition_status()
                                elif command == '/strategy_combined':
                                    state.strategy = 'combined'
                                    state.manual_target = None
                                    state.target_achieved = False
                                    send_telegram_message("🎯 Strategy: COMBINED")
                                    check_competition_status()
                                elif command.startswith('/margin '):
                                    try:
                                        state.safety_margin = int(command.split()[1])
                                        state.target_achieved = False
                                        send_telegram_message(f"🛡️ Margin: {state.safety_margin}")
                                        check_competition_status()
                                    except:
                                        send_telegram_message("❌ Usage: /margin <number>")
                                elif command.startswith('/target '):
                                    try:
                                        target_value = int(command.split()[1])
                                        state.manual_target = target_value
                                        state.target_achieved = False
                                        send_telegram_message(f"🎯 MANUAL TARGET SET: {target_value}\n\nNow ignoring competitors and focusing only on reaching {target_value} credits today!")
                                        check_competition_status()
                                    except:
                                        send_telegram_message("❌ Usage: /target <number>")
                                elif command == '/target_clear':
                                    state.manual_target = None
                                    state.target_achieved = False
                                    send_telegram_message("🔄 Manual target cleared! Returning to automatic competition mode.")
                                    check_competition_status()
                                elif command == '/restart_browser':
                                    stop_browser()
                                    time.sleep(2)
                                    state.driver = start_browser()
                                    if state.driver:
                                        smart_login_flow(state.driver)
                                        send_telegram_message("🔁 Browser RESTARTED!")
                                    else:
                                        send_telegram_message("❌ Failed to restart browser")
                                elif command == '/help':
                                    help_text = """
🤖 <b>AdShare Monitor v11.1 (Fixed)</b>

/start - Start monitoring
/stop - Stop monitoring  
/status - Check status
/strategy_today - Today only strategy
/strategy_combined - Combined strategy
/margin <number> - Set safety margin
/target <number> - Set manual target (overrides auto)
/target_clear - Clear manual target
/restart_browser - Restart browser
/help - This help

💡 <i>Running in ultra low resource mode</i>
                                    """
                                    send_telegram_message(help_text)
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
        time.sleep(10)

def main_loop():
    """Main monitoring loop"""
    logger.info("Starting AdShare Monitor v11.1 (Fixed)...")
    
    # Initial setup
    if not initialize_profile():
        logger.error("Profile initialization failed!")
        send_telegram_message("❌ Profile setup failed! Check logs.")
        return
    
    send_telegram_message("🚀 AdShare Monitor v11.1 Started! (Fixed Version)")
    
    # Auto-start if configured
    if CONFIG['auto_start']:
        state.is_running = True
        state.driver = start_browser()
        if state.driver:
            smart_login_flow(state.driver)
        check_competition_status()
    
    last_check = datetime.now()
    last_browser_check = datetime.now()
    
    while True:
        try:
            if state.is_running:
                current_time = datetime.now()
                
                # Regular competition check
                if (current_time - last_check).total_seconds() >= CONFIG['leaderboard_check_interval']:
                    check_competition_status()
                    last_check = current_time
                
                # Browser health check (less frequent)
                if state.driver and state.browser_active:
                    if (current_time - last_browser_check).total_seconds() >= 300:  # 5 minutes
                        try:
                            current_url = state.driver.current_url
                            if "adsha.re" not in current_url:
                                logger.warning("Browser not on AdShare, redirecting...")
                                state.driver.get(CONFIG['browser_url'])
                                time.sleep(5)
                        except Exception as e:
                            logger.error(f"Browser health check failed: {e}")
                            # Restart browser
                            stop_browser()
                            time.sleep(5)
                            state.driver = start_browser()
                            if state.driver:
                                smart_login_flow(state.driver)
                        last_browser_check = current_time
            
            time.sleep(30)  # Main loop interval
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(30)

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Shutting down gracefully...")
    stop_browser()
    sys.exit(0)

if __name__ == '__main__':
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start Telegram bot in background thread
    import threading
    bot_thread = threading.Thread(target=telegram_bot_loop, daemon=True)
    bot_thread.start()
    
    # Start main loop
    main_loop()
