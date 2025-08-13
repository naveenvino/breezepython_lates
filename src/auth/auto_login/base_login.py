"""
Base class for automated login implementations
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from datetime import datetime
import os
from pathlib import Path
import json
import time

logger = logging.getLogger(__name__)

class BaseAutoLogin(ABC):
    """
    Abstract base class for automated login systems
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        """
        Initialize base auto login
        
        Args:
            headless: Run browser in headless mode
            timeout: Maximum wait time for elements (seconds)
        """
        self.headless = headless
        self.timeout = timeout
        self.driver = None
        self.last_login_time = None
        self.last_login_status = None
        self.screenshots_dir = Path("logs/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
    @abstractmethod
    def login(self) -> Tuple[bool, Optional[str]]:
        """
        Perform automated login
        
        Returns:
            Tuple of (success: bool, token/error_message: str)
        """
        pass
    
    @abstractmethod
    def validate_token(self, token: str) -> bool:
        """
        Validate if the token is working
        
        Args:
            token: Token to validate
            
        Returns:
            True if token is valid
        """
        pass
    
    @abstractmethod
    def update_env_file(self, token: str) -> bool:
        """
        Update .env file with new token
        
        Args:
            token: New token to save
            
        Returns:
            True if update successful
        """
        pass
    
    def setup_driver(self):
        """
        Setup Selenium WebDriver with appropriate options
        """
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
            
        # Additional options for stability
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set user agent to avoid detection
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            logger.info(f"WebDriver initialized successfully (headless={self.headless})")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            return False
    
    def cleanup_driver(self):
        """
        Clean up WebDriver resources
        """
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None
    
    def take_screenshot(self, name: str = None):
        """
        Take screenshot for debugging
        
        Args:
            name: Optional name for screenshot file
        """
        if not self.driver:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = name or "screenshot"
        filename = self.screenshots_dir / f"{name}_{timestamp}.png"
        
        try:
            self.driver.save_screenshot(str(filename))
            logger.info(f"Screenshot saved: {filename}")
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
    
    def wait_for_element(self, by, value, timeout=None):
        """
        Wait for element to be present
        
        Args:
            by: Selenium By locator strategy
            value: Locator value
            timeout: Custom timeout (uses self.timeout if not provided)
            
        Returns:
            WebElement if found, None otherwise
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        timeout = timeout or self.timeout
        
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception as e:
            logger.error(f"Element not found: {by}={value}, Error: {e}")
            return None
    
    def save_login_status(self, success: bool, message: str = None):
        """
        Save login status to file for monitoring
        
        Args:
            success: Whether login was successful
            message: Optional status message
        """
        status_file = Path("logs/login_status.json")
        status_file.parent.mkdir(parents=True, exist_ok=True)
        
        status_data = {
            "timestamp": datetime.now().isoformat(),
            "service": self.__class__.__name__,
            "success": success,
            "message": message
        }
        
        # Read existing status
        existing_data = []
        if status_file.exists():
            try:
                with open(status_file, 'r') as f:
                    existing_data = json.load(f)
            except:
                existing_data = []
        
        # Append new status
        existing_data.append(status_data)
        
        # Keep only last 100 entries
        existing_data = existing_data[-100:]
        
        # Write back
        try:
            with open(status_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save login status: {e}")
    
    def retry_login(self, max_attempts: int = 3, delay: int = 30):
        """
        Retry login with exponential backoff
        
        Args:
            max_attempts: Maximum number of attempts
            delay: Initial delay between attempts (seconds)
            
        Returns:
            Tuple of (success: bool, token/error_message: str)
        """
        for attempt in range(max_attempts):
            logger.info(f"Login attempt {attempt + 1}/{max_attempts}")
            
            success, result = self.login()
            
            if success:
                logger.info(f"Login successful on attempt {attempt + 1}")
                self.save_login_status(True, f"Success after {attempt + 1} attempts")
                return True, result
            
            if attempt < max_attempts - 1:
                wait_time = delay * (2 ** attempt)  # Exponential backoff
                logger.info(f"Login failed, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        logger.error(f"Login failed after {max_attempts} attempts")
        self.save_login_status(False, f"Failed after {max_attempts} attempts")
        return False, "Max attempts reached"