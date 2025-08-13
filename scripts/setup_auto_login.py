"""
Setup script for auto-login system
Configures credentials and schedules
"""
import sys
import os
import getpass
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.auth.auto_login import CredentialManager, LoginScheduler

def setup_breeze_credentials():
    """Setup Breeze credentials"""
    print("\n=== Breeze (ICICI Direct) Credentials Setup ===")
    
    user_id = input("Enter Breeze User ID: ")
    password = getpass.getpass("Enter Breeze Password: ")
    
    totp_secret = input("Enter Breeze TOTP Secret (optional, press Enter to skip): ")
    
    cm = CredentialManager()
    cm.save_breeze_credentials(user_id, password, totp_secret if totp_secret else None)
    
    print("✓ Breeze credentials saved securely")

def setup_kite_credentials():
    """Setup Kite credentials"""
    print("\n=== Kite (Zerodha) Credentials Setup ===")
    
    user_id = input("Enter Kite User ID (Client ID): ")
    password = getpass.getpass("Enter Kite Password: ")
    pin = getpass.getpass("Enter Kite PIN (optional): ")
    api_secret = input("Enter Kite API Secret: ")
    
    totp_secret = input("Enter Kite TOTP Secret (optional, press Enter to skip): ")
    
    cm = CredentialManager()
    cm.save_kite_credentials(
        user_id, 
        password, 
        pin if pin else None,
        api_secret,
        totp_secret if totp_secret else None
    )
    
    print("✓ Kite credentials saved securely")

def setup_scheduler():
    """Setup scheduler configuration"""
    print("\n=== Scheduler Configuration ===")
    
    scheduler = LoginScheduler()
    
    # Breeze schedule
    print("\n-- Breeze Auto-Login Schedule --")
    enable_breeze = input("Enable Breeze auto-login? (y/n): ").lower() == 'y'
    
    if enable_breeze:
        times = input("Enter login times (comma-separated, e.g., 05:30,08:30): ")
        times_list = [t.strip() for t in times.split(',')]
        
        weekdays_only = input("Weekdays only? (y/n): ").lower() == 'y'
        headless = input("Run in headless mode? (y/n): ").lower() == 'y'
        
        scheduler.config['breeze']['enabled'] = True
        scheduler.config['breeze']['times'] = times_list
        scheduler.config['breeze']['weekdays_only'] = weekdays_only
        scheduler.config['breeze']['headless'] = headless
    else:
        scheduler.config['breeze']['enabled'] = False
    
    # Kite schedule
    print("\n-- Kite Auto-Login Schedule --")
    enable_kite = input("Enable Kite auto-login? (y/n): ").lower() == 'y'
    
    if enable_kite:
        times = input("Enter login times (comma-separated, e.g., 05:45,08:45): ")
        times_list = [t.strip() for t in times.split(',')]
        
        weekdays_only = input("Weekdays only? (y/n): ").lower() == 'y'
        headless = input("Run in headless mode? (y/n): ").lower() == 'y'
        
        scheduler.config['kite']['enabled'] = True
        scheduler.config['kite']['times'] = times_list
        scheduler.config['kite']['weekdays_only'] = weekdays_only
        scheduler.config['kite']['headless'] = headless
    else:
        scheduler.config['kite']['enabled'] = False
    
    # Notifications
    print("\n-- Notification Settings --")
    enable_notifications = input("Enable notifications? (y/n): ").lower() == 'y'
    
    if enable_notifications:
        email = input("Enter email for notifications (press Enter to skip): ")
        webhook = input("Enter webhook URL (press Enter to skip): ")
        
        scheduler.config['notifications']['enabled'] = True
        scheduler.config['notifications']['email'] = email if email else None
        scheduler.config['notifications']['webhook'] = webhook if webhook else None
    else:
        scheduler.config['notifications']['enabled'] = False
    
    scheduler.save_config()
    print("✓ Scheduler configuration saved")

def setup_email_smtp():
    """Setup SMTP settings for email notifications"""
    print("\n=== Email SMTP Configuration (Optional) ===")
    
    setup_smtp = input("Setup SMTP for email notifications? (y/n): ").lower() == 'y'
    
    if not setup_smtp:
        return
    
    smtp_server = input("SMTP Server (default: smtp.gmail.com): ") or "smtp.gmail.com"
    smtp_port = input("SMTP Port (default: 587): ") or "587"
    smtp_user = input("SMTP Username/Email: ")
    smtp_password = getpass.getpass("SMTP Password/App Password: ")
    
    # Update .env file
    env_path = Path(".env")
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    else:
        lines = []
    
    # Remove existing SMTP settings
    lines = [l for l in lines if not l.startswith('SMTP_')]
    
    # Add new SMTP settings
    lines.extend([
        f"SMTP_SERVER={smtp_server}",
        f"SMTP_PORT={smtp_port}",
        f"SMTP_USER={smtp_user}",
        f"SMTP_PASSWORD={smtp_password}"
    ])
    
    env_path.write_text('\n'.join(lines) + '\n')
    print("✓ SMTP configuration saved to .env")

def test_logins():
    """Test the auto-login functionality"""
    print("\n=== Test Auto-Login ===")
    
    test_breeze = input("Test Breeze login now? (y/n): ").lower() == 'y'
    if test_breeze:
        print("Testing Breeze login...")
        from src.auth.auto_login import BreezeAutoLogin
        
        breeze = BreezeAutoLogin(headless=False)  # Run with GUI for testing
        success, result = breeze.login()
        
        if success:
            print(f"✓ Breeze login successful! Token: {result[:20]}...")
        else:
            print(f"✗ Breeze login failed: {result}")
    
    test_kite = input("Test Kite login now? (y/n): ").lower() == 'y'
    if test_kite:
        print("Testing Kite login...")
        from src.auth.auto_login import KiteAutoLogin
        
        kite = KiteAutoLogin(headless=False)  # Run with GUI for testing
        success, result = kite.login()
        
        if success:
            print(f"✓ Kite login successful! Token: {result[:20]}...")
        else:
            print(f"✗ Kite login failed: {result}")

def main():
    """Main setup flow"""
    print("=" * 50)
    print("Auto-Login System Setup")
    print("=" * 50)
    
    print("\nThis script will help you set up automated daily login for:")
    print("1. Breeze API (ICICI Direct)")
    print("2. Kite API (Zerodha)")
    
    print("\n⚠️  Prerequisites:")
    print("- Chrome browser installed")
    print("- ChromeDriver in PATH or same directory")
    print("- API keys configured in .env file")
    
    proceed = input("\nProceed with setup? (y/n): ")
    if proceed.lower() != 'y':
        print("Setup cancelled")
        return
    
    # Setup credentials
    setup_breeze = input("\nSetup Breeze credentials? (y/n): ").lower() == 'y'
    if setup_breeze:
        setup_breeze_credentials()
    
    setup_kite_creds = input("\nSetup Kite credentials? (y/n): ").lower() == 'y'
    if setup_kite_creds:
        setup_kite_credentials()
    
    # Setup scheduler
    setup_sched = input("\nSetup auto-login schedule? (y/n): ").lower() == 'y'
    if setup_sched:
        setup_scheduler()
    
    # Setup email
    setup_email_smtp()
    
    # Test logins
    test = input("\nTest auto-login now? (y/n): ").lower() == 'y'
    if test:
        test_logins()
    
    print("\n" + "=" * 50)
    print("✓ Setup Complete!")
    print("=" * 50)
    
    print("\nNext steps:")
    print("1. Ensure ChromeDriver is installed")
    print("2. Start the scheduler from your main application")
    print("3. Monitor logs/login_status.json for results")
    print("\nTo manually trigger login, use the API endpoints:")
    print("- POST /auth/auto-login/breeze")
    print("- POST /auth/auto-login/kite")

if __name__ == "__main__":
    main()