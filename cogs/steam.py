import discord
from discord.ext import commands
from discord import app_commands
import time
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class Steam_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.driver = None
        self.wait = None
        self.is_logged_in = False
        self.quit_after_given_time = 15 # in minutes
        self.timer_start_time = None
        
    def setup_driver(self):
        """Set up headless Chrome WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")  # Only show fatal errors
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-voice-transcription")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 15)
            return True
        except Exception as e:
            return False
    
    def navigate_to_login(self):
        """Navigate to Steam login page"""
        try:
            self.driver.get("https://steamcommunity.com/login/home/?goto=")
            time.sleep(3)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
            time.sleep(2)
            return True
        except Exception as e:
            return False
    
    def find_login_form(self):
        """Find login form elements"""
        try:
            input_elements = self.driver.find_elements(By.TAG_NAME, "input")
            
            username_field = None
            for input_elem in input_elements:
                input_type = input_elem.get_attribute("type")
                input_id = input_elem.get_attribute("id") or ""
                
                if (input_type == "text" and 
                    "auth" not in input_id.lower() and 
                    "factor" not in input_id.lower() and
                    "friendly" not in input_id.lower()):
                    username_field = input_elem
                    break
            
            password_field = self.driver.find_element(By.XPATH, "//input[@type='password']")
            login_button = self.driver.find_element(
                By.XPATH, "//button[@type='submit' and contains(text(), 'Sign in')]"
            )
            
            if username_field and password_field and login_button:
                return username_field, password_field, login_button
            else:
                return None, None, None
                
        except Exception as e:
            return None, None, None
    
    def fill_login_form(self, username_field, password_field, username, password):
        """Fill in the login form"""
        try:
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            return True
        except Exception as e:
            return False
    
    async def submit_login(self, login_button):
        """Submit the login form"""
        try:
            login_button.click()
            await asyncio.sleep(5)
            return True
        except Exception as e:
            return False
    
    def check_login_result(self):
        """Check the result of the login attempt"""
        try:
            page_source = self.driver.page_source
            current_url = self.driver.current_url
            

            
            # Check for successful login without verification needed
            if ("Edit Profile" in page_source and 
                ("steamcommunity.com/profiles" in current_url or 
                 "steamcommunity.com/id/" in current_url or
                 "steamcommunity.com/home" in current_url)):
                try:
                    profile_name_element = self.driver.find_element(
                        By.CSS_SELECTOR, "span.actual_persona_name"
                    )
                    profile_name = profile_name_element.text
                    return "success", current_url, profile_name
                except Exception as e:
                    return "success", current_url, "Unknown"
            
            # Check for Steam Mobile App requirement
            elif "Use the Steam Mobile App to confirm your sign in" in page_source:
                return "mobile_app", None, None
            
            # Check for email verification requirement
            elif "Enter the code from your email address at" in page_source:
                return "email_verification", None, None
            
            # Check for other common Steam responses
            elif "Incorrect login" in page_source or "Invalid login" in page_source:
                return "invalid_credentials", None, None
            elif "CAPTCHA" in page_source or "captcha" in page_source.lower():
                return "captcha_required", None, None
            elif "Steam Guard" in page_source:
                return "steam_guard_required", None, None
            else:
                return "unknown", None, None
                
        except Exception as e:
            return "error", None, None
    
    async def handle_email_verification(self, ctx):
        """Handle email verification by entering 5-character code"""
        try:
            #await ctx.send("Enter 5-character verification code:")
            
            code_inputs = self.driver.find_elements(
                By.XPATH, "//input[@type='text' and @maxlength='1' and @autocomplete='none']"
            )
            
            if len(code_inputs) != 5:
                await ctx.send("Verification fields not found")
                return "email_verification_failed"
            
            # Wait for user response
            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel
            
            try:
                await ctx.send("Enter your 5-character verification code in the message box below:")
                msg = await self.bot.wait_for('message', timeout=60.0, check=check)
                verification_code = msg.content.strip()
                await ctx.send(f"Received code: {verification_code}")
            except Exception as e:
                await ctx.send(f"Timeout or error waiting for verification code: {e}")
                return "timeout"
            
            if len(verification_code) != 5:
                await ctx.send("Invalid code - must be exactly 5 characters")
                return "invalid_code_format"
            
            # Enter the code
            for i, (input_field, digit) in enumerate(zip(code_inputs, verification_code)):
                input_field.clear()
                input_field.send_keys(digit)
            
            await ctx.send("Code entered. Waiting for Steam to process...")
            await asyncio.sleep(3)
            
            # Check if code was incorrect
            page_source = self.driver.page_source
            if "Incorrect code, please try again" in page_source:
                await ctx.send("❌ Incorrect verification code")
                return "incorrect_code"
            
            # Code was correct, check login success
            await asyncio.sleep(3)
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            # Check for successful login - Steam can redirect to different URL patterns
            if ("Edit Profile" in page_source and 
                ("steamcommunity.com/profiles" in current_url or 
                 "steamcommunity.com/id/" in current_url or
                 "steamcommunity.com/home" in current_url)):
                try:
                    profile_name_element = self.driver.find_element(
                        By.CSS_SELECTOR, "span.actual_persona_name"
                    )
                    profile_name = profile_name_element.text
                    await ctx.send("✅ Email verification successful!")
                    return "success", current_url, profile_name
                except Exception as e:
                    await ctx.send("✅ Email verification successful! (Profile name extraction failed)")
                    return "success", current_url, "Unknown"
            else:
                await ctx.send("⚠️ Email verification completed but login status unclear")
                return "verification_completed", None, None
                
        except Exception as e:
            await ctx.send(f"❌ Error during email verification: {e}")
            return "email_verification_error"
    
    async def handle_mobile_app_verification(self, ctx):
        """Handle Steam Mobile App authentication"""
        try:

            
            def check(message):
                return message.author == ctx.author and message.channel == ctx.channel and message.content.lower() == 'done'
            
            try:
                await ctx.send("Approve sign-in in Steam Mobile App, then reply 'done'...")
                msg = await self.bot.wait_for('message', timeout=120.0, check=check)
                await ctx.send(f"Received: {msg.content}")
            except Exception as e:
                await ctx.send(f"Timeout or error waiting for mobile app approval: {e}")
                return "timeout", None, None
            
            # Wait 5 seconds for Steam to process mobile app approval
            await ctx.send("Mobile app approval received. Waiting 5 seconds for Steam to process...")
            await asyncio.sleep(5)
            
            # Check if login was successful
            current_url = self.driver.current_url
            page_source = self.driver.page_source

            if ("Edit Profile" in page_source and 
                ("steamcommunity.com/profiles" in current_url or 
                 "steamcommunity.com/id/" in current_url or
                 "steamcommunity.com/home" in current_url)):
                try:
                    profile_name_element = self.driver.find_element(
                        By.CSS_SELECTOR, "span.actual_persona_name"
                    )
                    profile_name = profile_name_element.text
                    await ctx.send(f"✅ Mobile app verification successful!")
                    return "success", current_url, profile_name
                except Exception as e:
                    await ctx.send(f"✅ Mobile app verification successful! (Profile name extraction failed)")
                    return "success", current_url, "Unknown"
            
            # Check if we're still on the mobile app page
            elif "Use the Steam Mobile App to confirm your sign in" in page_source:
                await ctx.send("⚠️ Still waiting for mobile app approval. Please try again.")
                return "mobile_app_pending", None, None
            
            # Check for other Steam responses
            elif "Incorrect" in page_source or "Invalid" in page_source:
                await ctx.send("❌ Mobile app approval was rejected or incorrect")
                return "mobile_app_rejected", None, None
            elif "Steam Guard" in page_source:
                await ctx.send("🔐 Additional Steam Guard verification required")
                return "steam_guard_required", None, None
            else:
                await ctx.send("⚠️ Mobile app verification completed but login status unclear")
                return "mobile_app_verification_completed", None, None
            
        except Exception as e:
            return "mobile_app_verification_error", None, None
    
    async def activate_product_key(self, ctx, key):
        """Activate a Steam product key"""
        try:
            await ctx.send(f"Please wait, activating product key: {key}")
            # Navigate to product key activation page
            self.driver.get("https://store.steampowered.com/account/registerkey")
            await asyncio.sleep(3)
            
            # Find and enter the product key
            key_input = self.driver.find_element(By.NAME, "product_key")
            key_input.clear()
            key_input.send_keys(key)
            
            # Find and check the checkbox
            checkbox = self.driver.find_element(By.NAME, "accept_ssa")
            if not checkbox.is_selected():
                checkbox.click()
            
            # Find and click the continue button
            continue_button = self.driver.find_element(By.ID, "register_btn")
            continue_button.click()
            
            # Wait for response and check result
            await asyncio.sleep(3)
            page_source = self.driver.page_source
            current_url = self.driver.current_url
            
            # Check for error_display element first
            try:
                error_element = self.driver.find_element(By.ID, "error_display")
                if error_element.is_displayed():
                    error_text = error_element.text
                    await ctx.send(f"Activation unsuccessful: {error_text}")
                else:
                    game_name_element = self.driver.find_element(By.CSS_SELECTOR, "div.registerkey_lineitem")
                    game_name = game_name_element.text
                    await ctx.send(f"Activation successful: {key} | {game_name}")
            except Exception as e:
                await ctx.send("Error while activating key. With error: " + str(e))
                
        except Exception as e:
            await ctx.send(f"Error activating product key: {e}")
    
    async def auto_quit_timer(self, ctx):
        """Automatically quit Steam session after specified time"""
        self.timer_start_time = time.time()
        await asyncio.sleep(self.quit_after_given_time * 60)  # Convert minutes to seconds
        if self.is_logged_in and self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
            self.is_logged_in = False
            self.timer_start_time = None
            await ctx.send(f"⏰ Auto-quit: Steam session closed after {self.quit_after_given_time} minutes")
    
    @commands.command(name="Steam")
    async def steam_command(self, ctx, action: str = None, username: str = None, password: str = None):
        """Steam login command"""
        if not action:
            await ctx.send("Available commands:\n`!Steam login <username> <password>` - Login to Steam\n`!Steam activate <key1,key2;key3>` - Activate product key(s)\n`!Steam quit` - Close browser session")
            return
            
        if action.lower() == "login":
            if not username or not password:
                await ctx.send("Usage: !Steam login <username> <password>")
                return
            
            await ctx.send("Starting Steam login...")
            
            if not self.setup_driver():
                await ctx.send("Failed to setup browser")
                return
            
            if not self.navigate_to_login():
                await ctx.send("Failed to navigate to login page")
                self.driver.quit()
                return
            
            username_field, password_field, login_button = self.find_login_form()
            if not all([username_field, password_field, login_button]):
                await ctx.send("Failed to find login form")
                self.driver.quit()
                return
            
            if not self.fill_login_form(username_field, password_field, username, password):
                await ctx.send("Failed to fill login form")
                self.driver.quit()
                return
            
            if not await self.submit_login(login_button):
                await ctx.send("Failed to submit login")
                self.driver.quit()
                return
            
            login_result, url, profile_name = self.check_login_result()
            
            if login_result == "success":
                self.is_logged_in = True
                await ctx.send(f"Login successful!\nProfile: {profile_name}\nURL: {url}")
                # Start auto-quit timer
                await ctx.send(f"⏰ Auto-quit: Session will be terminated after {self.quit_after_given_time} minutes")
                self.bot.loop.create_task(self.auto_quit_timer(ctx))
            elif login_result == "mobile_app":
                result, url, profile_name = await self.handle_mobile_app_verification(ctx)
                if result == "success":
                    self.is_logged_in = True
                    await ctx.send(f"🎉 Login successful!\nProfile: {profile_name}\nURL: {url}")
                    # Start auto-quit timer
                    await ctx.send(f"⏰ Auto-quit: Session will be terminated after {self.quit_after_given_time} minutes")
                    self.bot.loop.create_task(self.auto_quit_timer(ctx))
                elif result == "mobile_app_rejected":
                    await ctx.send("❌ Mobile app approval was rejected")
                elif result == "steam_guard_required":
                    await ctx.send("🔐 Additional Steam Guard verification required")
                elif result == "mobile_app_pending":
                    await ctx.send("⚠️ Mobile app approval still pending. Please try again.")
                elif result == "mobile_app_verification_completed":
                    await ctx.send("⚠️ Mobile app verification completed but login status unclear")
                else:
                    await ctx.send(f"❌ Mobile app verification failed: {result}")
            elif login_result == "email_verification":
                result, url, profile_name = await self.handle_email_verification(ctx)
                if result == "success":
                    self.is_logged_in = True
                    await ctx.send(f"🎉 Login successful!\nProfile: {profile_name}\nURL: {url}")
                    # Start auto-quit timer
                    await ctx.send(f"⏰ Auto-quit: Session will be terminated after {self.quit_after_given_time} minutes")
                    self.bot.loop.create_task(self.auto_quit_timer(ctx))
                elif result == "incorrect_code":
                    await ctx.send("❌ Email verification failed: Incorrect code")
                elif result == "invalid_code_format":
                    await ctx.send("❌ Email verification failed: Code must be exactly 5 characters")
                elif result == "timeout":
                    await ctx.send("⏰ Email verification failed: Timeout waiting for code")
                elif result == "verification_completed":
                    await ctx.send("⚠️ Email verification completed but login status unclear")
                else:
                    await ctx.send(f"❌ Email verification failed: {result}")
            elif login_result == "invalid_credentials":
                await ctx.send("❌ Login failed: Invalid username or password")
            elif login_result == "captcha_required":
                await ctx.send("❌ Login failed: CAPTCHA required - Steam detected automated login")
            elif login_result == "steam_guard_required":
                await ctx.send("❌ Login failed: Steam Guard required - additional verification needed")
            elif login_result == "unknown":
                await ctx.send("❌ Login failed: Unknown response from Steam - check console for details")
            elif login_result == "error":
                await ctx.send("❌ Login failed: Error occurred during login process")
            else:
                await ctx.send(f"❌ Login failed: {login_result}")
        
        elif action.lower() == "quit":
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
                self.is_logged_in = False
                self.timer_start_time = None
                await ctx.send("Browser session closed.")
            else:
                await ctx.send("No active browser session.")
        
        elif action.lower() == "activate":
            if not self.is_logged_in:
                await ctx.send("Please login first using !Steam login")
                return
            
            if not username:
                await ctx.send("Usage: !Steam activate <key1,key2;key3>")
                return
            
            # Split keys by comma or semicolon
            keys = [key.strip() for key in username.replace(';', ',').split(',') if key.strip()]
            
            if len(keys) == 1:
                await self.activate_product_key(ctx, keys[0])
            else:
                await ctx.send(f"Activating {len(keys)} keys...")
                for i, key in enumerate(keys, 1):
                    await ctx.send(f"Activating key {i}/{len(keys)}: {key}")
                    await self.activate_product_key(ctx, key)
                    if i < len(keys):  # Don't wait after the last key
                        await asyncio.sleep(2)
        
        elif action.lower() == "remaining":
            if not self.is_logged_in or not self.timer_start_time:
                await ctx.send("No active session with auto-quit timer running.")
                return
            
            elapsed_time = time.time() - self.timer_start_time
            remaining_time = (self.quit_after_given_time * 60) - elapsed_time
            
            if remaining_time <= 0:
                await ctx.send("⏰ Auto-quit timer has expired. Session will be closed shortly.")
            else:
                remaining_minutes = int(remaining_time // 60)
                remaining_seconds = int(remaining_time % 60)
                await ctx.send(f"⏰ Auto-quit in: {remaining_minutes} minutes and {remaining_seconds} seconds")
        
        else:
            await ctx.send("Available commands:\n`!Steam login <username> <password>` - Login to Steam\n`!Steam activate <key1,key2;key3>` - Activate product key(s)\n`!Steam remaining` - Show remaining time until auto-quit\n`!Steam quit` - Close browser session")
            



async def setup(bot):
    await bot.add_cog(Steam_Commands(bot))
