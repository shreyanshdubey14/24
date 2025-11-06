#!/usr/bin/env python3
"""
AdShare Monitor v11.0 - Ultra Low Resource
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
    'my_user_id': '4242',
    'browser_url': "https://adsha.re/surf",
    'login_url': "https://adsha.re/login",  # Added login URL
    'leaderboard_url': 'https://adsha.re/ten',
    'timezone': 'Asia/Kolkata',
    'profile_dir': '/app/firefox_profile',
    'extensions_dir': '/app/extensions',
    'auto_start': True,
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

state = MonitorState()

# ==================== CORE FUNCTIONS ====================

def download_files():
    os.makedirs(CONFIG['extensions_dir'], exist_ok=True)
    logger.info("Downloading extensions...")
    
    paths = {}
    for ext_id, ext_info in EXTENSIONS.items():
        filepath = os.path.join(CONFIG['extensions_dir'], ext_info["xpi_file"])
        if not os.path.exists(filepath):
            urllib.request.urlretrieve(ext_info["xpi_url"], filepath)
            logger.info(f"Downloaded {ext_info['name']}")
        paths[ext_id] = filepath
    return paths

def install_userscript_properly(driver):
    logger.info("Installing userscript...")
    
    try:
        main_window = driver.current_window_handle
        initial_windows = driver.window_handles
        
        driver.get(USERSCRIPT_PAGE)
        time.sleep(6)
        
        if "install this script" not in driver.page_source.lower():
            logger.error("Violentmonkey not detected!")
            return False
        
        logger.info("Violentmonkey detected!")
        
        try:
            install_link = driver.find_element(By.CSS_SELECTOR, "a.install-link")
            install_link.click()
            logger.info("Clicked install link")
        except Exception as e:
            driver.execute_script("document.querySelector('a.install-link').click();")
            logger.info("JS click executed")
        
        time.sleep(5)
        current_windows = driver.window_handles
        
        if len(current_windows) > len(initial_windows):
            logger.info("New window detected!")
            new_window = [w for w in current_windows if w not in initial_windows][-1]
            driver.switch_to.window(new_window)
            time.sleep(3)
            
            install_selectors = [
                (By.XPATH, "//button[contains(text(), 'Install')]"),
                (By.XPATH, "//button[contains(@class, 'install')]"),
                (By.CSS_SELECTOR, "button.vm-confirm"),
                (By.XPATH, "//button[@type='submit']"),
            ]
            
            for by, selector in install_selectors:
                try:
                    install_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    driver.execute_script("arguments[0].scrollIntoView(true);", install_btn)
                    time.sleep(1)
                    install_btn.click()
                    logger.info(f"Clicked Install button using {selector}")
                    time.sleep(3)
                    break
                except:
                    continue
            
            time.sleep(2)
            if main_window in driver.window_handles:
                driver.switch_to.window(main_window)
            else:
                driver.switch_to.window(driver.window_handles[0])
            
            logger.info("Userscript installation completed!")
            return True
        else:
            logger.error("No new window opened!")
            return False
            
    except Exception as e:
        logger.error(f"Installation error: {e}")
        return False

def initialize_profile():
    if state.profile_initialized:
        return True
        
    logger.info("Initializing profile...")
    
    if os.path.exists(CONFIG['profile_dir']):
        import shutil
        shutil.rmtree(CONFIG['profile_dir'])
    os.makedirs(CONFIG['profile_dir'])
    
    extension_paths = download_files()
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"-profile")
    options.add_argument(CONFIG['profile_dir'])
    options.set_preference("xpinstall.signatures.required", False)
    options.set_preference("extensions.autoDisableScopes", 0)
    options.set_preference("extensions.enabledScopes", 15)
    
    # ULTRA LOW MEMORY SETTINGS
    options.set_preference("browser.tabs.remote.autostart", False)
    options.set_preference("browser.tabs.remote.autostart.2", False)
    options.set_preference("dom.ipc.processCount", 1)  # Single process
    options.set_preference("dom.ipc.processCount.webIsolated", 1)
    options.set_preference("browser.sessionstore.interval", 60000)  # Reduce session save frequency
    options.set_preference("browser.sessionstore.max_resumed_crashes", 0)
    options.set_preference("browser.sessionstore.restore_on_demand", False)
    options.set_preference("browser.sessionstore.resume_from_crash", False)
    options.set_preference("browser.startup.homepage_override.mstone", "ignore")
    options.set_preference("toolkit.telemetry.reportingpolicy.firstRun", False)
    options.set_preference("toolkit.telemetry.shutdownPingSender.enabled", False)
    options.set_preference("datareporting.healthreport.uploadEnabled", False)
    options.set_preference("dom.disable_beforeunload", True)
    options.set_preference("dom.max_script_run_time", 30)
    options.set_preference("dom.min_timeout_value", 1000)
    
    # Install extensions
    logger.info("Installing extensions...")
    driver = None
    try:
        driver = webdriver.Firefox(options=options)
        for ext_id, ext_path in extension_paths.items():
            abs_path = os.path.abspath(ext_path)
            driver.install_addon(abs_path, temporary=False)
            logger.info(f"Installed {EXTENSIONS[ext_id]['name']}")
            time.sleep(2)
        driver.quit()
    except Exception as e:
        logger.error(f"Extension install error: {e}")
        if driver:
            driver.quit()
        return False
    
    # Install userscript
    logger.info("Installing userscript...")
    time.sleep(3)
    try:
        driver = webdriver.Firefox(options=options)
        time.sleep(8)  # Wait for extensions to load
        
        success = install_userscript_properly(driver)
        driver.quit()
        
        if success:
            state.profile_initialized = True
            logger.info("Profile initialization complete!")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Userscript install error: {e}")
        if driver:
            driver.quit()
        return False

def start_browser():
    if not state.profile_initialized:
        if not initialize_profile():
            return None
    
    logger.info("Starting browser with low memory settings...")
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"-profile")
    options.add_argument(CONFIG['profile_dir'])
    
    # ULTRA LOW MEMORY SETTINGS
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
        logger.info("Browser started with low memory settings!")
        return driver
    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        return None

def stop_browser():
    if state.driver:
        try:
            state.driver.quit()
            logger.info("Browser stopped")
        except:
            pass
        state.driver = None
    state.browser_active = False

def smart_login_flow(driver):
    """New login flow: login page first, wait 60s, then surf"""
    try:
        logger.info("Starting smart login flow...")
        
        # Step 1: Open login page first
        logger.info("Step 1: Opening login page...")
        driver.get(CONFIG['login_url'])
        time.sleep(5)
        
        # Step 2: Wait 60 seconds for auto-login by userscript
        logger.info("Step 2: Waiting 60 seconds for auto-login...")
        for i in range(60):
            time.sleep(1)
            if i % 10 == 0:  # Log every 10 seconds
                logger.info(f"Auto-login wait: {i}/60 seconds")
        
        # Step 3: Navigate to surf page
        logger.info("Step 3: Navigating to surf page...")
        driver.get(CONFIG['browser_url'])
        time.sleep(5)
        
        # Check if successfully on surf page
        if "surf" in driver.current_url or "game" in driver.current_url.lower():
            logger.info("✅ Login successful! Ready to surf.")
            return True
        else:
            logger.error("❌ Login failed - not on surf page")
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
            entries = soup.find_all('div', style=lambda x: x and 'width:250px' in x and 'margin:5px auto' in x)
            
            if not entries:
                all_divs = soup.find_all('div')
                entries = [div for div in all_divs if 'T:' in div.get_text() and 'Y:' in div.get_text()]
            
            rank = 1
            for entry in entries:
                text = entry.get_text(strip=True)
                user_match = re.search(r'#(\d+)', text)
                if not user_match:
                    continue
                
                user_id = user_match.group(1)
                today_match = re.search(r'T:\s*(\d+(?:,\d+)*)', text)
                yesterday_match = re.search(r'Y:\s*(\d+(?:,\d+)*)', text)
                db_match = re.search(r'DB:\s*(\d+(?:,\d+)*)', text)
                
                today = int(today_match.group(1).replace(',', '')) if today_match else 0
                yesterday = int(yesterday_match.group(1).replace(',', '')) if yesterday_match else 0
                day_before = int(db_match.group(1).replace(',', '')) if db_match else 0
                total = today + yesterday + day_before
                
                leaderboard.append({
                    'rank': rank, 'user_id': user_id, 'total_surfed': total,
                    'today_credits': today, 'yesterday_credits': yesterday, 'day_before_credits': day_before
                })
                rank += 1
            
            logger.info(f"Parsed {len(leaderboard)} entries")
            return leaderboard
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return []

def fetch_leaderboard() -> Optional[List[Dict]]:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Cookie': 'adshare_e=bonna.b.o.rre.z%40gmail.com; adshare_s=e4dc9d210bb38a86cd360253a82feb2cc6ed84f5ddf778be89484fb476998e0dfc31280c575a38a2467067cd6ec1d6ff7e25aa46dedd6ea454831df26365dfc2; adshare_d=20251025; adshare_h=https%3A%2F%2Fadsha.re%2Faffiliates'
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
    if len(leaderboard) < 2:
        return 0, "Not enough data"
    
    second_place = leaderboard[1]
    if state.strategy == 'today_only':
        target = second_place['today_credits'] + state.safety_margin
        explanation = f"2nd today ({second_place['today_credits']}) + {state.safety_margin}"
    else:
        second_combined = second_place['today_credits'] + second_place['yesterday_credits']
        target = second_combined
        explanation = f"2nd combined ({second_combined})"
    return target, explanation

def get_my_value(my_data: Dict) -> int:
    return my_data['today_credits']

def should_stop_browser(leaderboard: List[Dict]) -> bool:
    if state.my_position != 1:
        return False
    
    my_data = None
    for entry in leaderboard:
        if entry['user_id'] == CONFIG['my_user_id']:
            my_data = entry
            break
    if not my_data:
        return False
    
    my_today = get_my_value(my_data)
    target, _ = calculate_target(leaderboard)
    return my_today >= target

def send_telegram_message(message: str):
    if not CONFIG.get('chat_id'):
        return
    try:
        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
        data = {'chat_id': CONFIG['chat_id'], 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, data=data, timeout=15)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

def check_competition_status():
    current_time = datetime.now()
    state.last_check_time = current_time
    
    leaderboard = fetch_leaderboard()
    if not leaderboard:
        logger.error("Failed to fetch leaderboard")
        return
    
    state.leaderboard = leaderboard
    my_data = None
    for entry in state.leaderboard:
        if entry['user_id'] == CONFIG['my_user_id']:
            my_data = entry
            state.my_position = entry['rank']
            break
    
    if not my_data:
        logger.error(f"User #{CONFIG['my_user_id']} not found!")
        return
    
    my_value = get_my_value(my_data)
    if state.last_my_credits > 0 and state.last_credits_time:
        time_diff_hours = (current_time - state.last_credits_time).total_seconds() / 3600.0
        credits_gained = my_value - state.last_my_credits
        if credits_gained > 0 and time_diff_hours > 0:
            state.credits_growth_rate = credits_gained / time_diff_hours
    
    state.last_my_credits = my_value
    state.last_credits_time = current_time
    
    # Browser control
    should_stop = should_stop_browser(leaderboard)
    if should_stop and state.browser_active:
        logger.info("Target achieved, stopping browser")
        stop_browser()
        send_telegram_message("🎯 <b>TARGET ACHIEVED!</b> Browser stopped.")
    elif not should_stop and not state.browser_active and state.is_running:
        logger.info("Starting browser to chase target")
        state.driver = start_browser()
        if state.driver:
            smart_login_flow(state.driver)
    
    target, explanation = calculate_target(leaderboard)
    state.current_target = target
    
    status_message = ""
    if state.my_position != 1:
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
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/getUpdates?timeout=30"
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
                                    send_telegram_message("🎯 Strategy: TODAY ONLY")
                                    check_competition_status()
                                elif command == '/strategy_combined':
                                    state.strategy = 'combined'
                                    send_telegram_message("🎯 Strategy: COMBINED")
                                    check_competition_status()
                                elif command.startswith('/margin '):
                                    try:
                                        state.safety_margin = int(command.split()[1])
                                        send_telegram_message(f"🛡️ Margin: {state.safety_margin}")
                                        check_competition_status()
                                    except:
                                        send_telegram_message("❌ Usage: /margin <number>")
                                elif command == '/help':
                                    help_text = """
🤖 <b>AdShare Monitor (Low Resource)</b>

/start - Start monitoring
/stop - Stop monitoring  
/status - Check status
/strategy_today - Today only strategy
/strategy_combined - Combined strategy
/margin <number> - Set safety margin
/help - This help

💡 <i>Running in low resource mode</i>
                                    """
                                    send_telegram_message(help_text)
        except Exception as e:
            logger.error(f"Telegram error: {e}")
        time.sleep(10)

def main_loop():
    logger.info("Starting AdShare Monitor (Low Resource Mode)...")
    
    if not initialize_profile():
        logger.error("Profile init failed!")
        send_telegram_message("❌ Profile setup failed!")
        return
    
    send_telegram_message("🚀 AdShare Monitor Started! (Low Resource Mode)")
    
    if CONFIG['auto_start']:
        state.is_running = True
        state.driver = start_browser()
        if state.driver:
            smart_login_flow(state.driver)
        check_competition_status()
    
    last_check = datetime.now()
    while True:
        try:
            if state.is_running:
                current_time = datetime.now()
                if (current_time - last_check).total_seconds() >= CONFIG['leaderboard_check_interval']:
                    check_competition_status()
                    last_check = current_time
                
                if state.driver and state.browser_active:
                    try:
                        current_url = state.driver.current_url
                        if "adsha.re" not in current_url:
                            state.driver.get(CONFIG['browser_url'])
                            time.sleep(5)
                    except:
                        try:
                            state.driver.quit()
                        except:
                            pass
                        state.driver = start_browser()
                        if state.driver:
                            smart_login_flow(state.driver)
            time.sleep(30)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(30)

def signal_handler(sig, frame):
    logger.info("Shutting down...")
    stop_browser()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    import threading
    bot_thread = threading.Thread(target=telegram_bot_loop, daemon=True)
    bot_thread.start()
    main_loop()
