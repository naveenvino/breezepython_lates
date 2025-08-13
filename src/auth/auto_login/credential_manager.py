"""
Secure credential management for auto-login
Uses Windows Credential Manager for secure storage
"""
import logging
import os
import json
import base64
from typing import Dict, Optional
from pathlib import Path
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class CredentialManager:
    """
    Manages secure storage and retrieval of credentials
    """
    
    def __init__(self):
        self.config_file = Path("config/auto_login_credentials.json")
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.use_windows_credential_manager = self._check_windows_available()
        self._init_encryption()
    
    def _check_windows_available(self) -> bool:
        """
        Check if Windows Credential Manager is available
        """
        try:
            import win32cred
            return True
        except ImportError:
            logger.info("Windows Credential Manager not available, using encrypted file storage")
            return False
    
    def _init_encryption(self):
        """
        Initialize encryption for credential storage
        """
        # Generate or load encryption key
        key_file = Path("config/.key")
        key_file.parent.mkdir(parents=True, exist_ok=True)
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                self.cipher_suite = Fernet(f.read())
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            self.cipher_suite = Fernet(key)
            
            # Set restrictive permissions on key file (Windows)
            import stat
            os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)
    
    def save_credentials(self, service: str, credentials: Dict[str, str]):
        """
        Save credentials securely
        
        Args:
            service: Service name ('breeze' or 'kite')
            credentials: Dictionary of credentials
        """
        if self.use_windows_credential_manager:
            self._save_to_windows_credential_manager(service, credentials)
        else:
            self._save_to_encrypted_file(service, credentials)
    
    def get_credentials(self, service: str) -> Optional[Dict[str, str]]:
        """
        Retrieve credentials for a service
        
        Args:
            service: Service name ('breeze' or 'kite')
            
        Returns:
            Dictionary of credentials if found
        """
        if self.use_windows_credential_manager:
            return self._get_from_windows_credential_manager(service)
        else:
            return self._get_from_encrypted_file(service)
    
    def _save_to_windows_credential_manager(self, service: str, credentials: Dict[str, str]):
        """
        Save credentials to Windows Credential Manager
        """
        try:
            import win32cred
            
            target_name = f"UnifiedTradingPlatform_{service}"
            cred_blob = json.dumps(credentials)
            
            credential = {
                'Type': win32cred.CRED_TYPE_GENERIC,
                'TargetName': target_name,
                'CredentialBlob': cred_blob,
                'Comment': f'Credentials for {service} auto-login',
                'Persist': win32cred.CRED_PERSIST_LOCAL_MACHINE
            }
            
            win32cred.CredWrite(credential)
            logger.info(f"Credentials saved to Windows Credential Manager for {service}")
            
        except Exception as e:
            logger.error(f"Failed to save to Windows Credential Manager: {e}")
            # Fallback to encrypted file
            self._save_to_encrypted_file(service, credentials)
    
    def _get_from_windows_credential_manager(self, service: str) -> Optional[Dict[str, str]]:
        """
        Retrieve credentials from Windows Credential Manager
        """
        try:
            import win32cred
            
            target_name = f"UnifiedTradingPlatform_{service}"
            cred = win32cred.CredRead(target_name, win32cred.CRED_TYPE_GENERIC)
            
            if cred:
                cred_blob = cred['CredentialBlob']
                if isinstance(cred_blob, bytes):
                    cred_blob = cred_blob.decode('utf-8')
                
                credentials = json.loads(cred_blob)
                logger.info(f"Credentials retrieved from Windows Credential Manager for {service}")
                return credentials
                
        except Exception as e:
            logger.debug(f"Failed to get from Windows Credential Manager: {e}")
            # Try encrypted file as fallback
            return self._get_from_encrypted_file(service)
        
        return None
    
    def _save_to_encrypted_file(self, service: str, credentials: Dict[str, str]):
        """
        Save credentials to encrypted file
        """
        try:
            # Load existing data
            if self.config_file.exists():
                with open(self.config_file, 'rb') as f:
                    encrypted_data = f.read()
                    decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                    all_credentials = json.loads(decrypted_data)
            else:
                all_credentials = {}
            
            # Update credentials
            all_credentials[service] = credentials
            
            # Encrypt and save
            encrypted_data = self.cipher_suite.encrypt(json.dumps(all_credentials).encode())
            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions
            import stat
            os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
            
            logger.info(f"Credentials saved to encrypted file for {service}")
            
        except Exception as e:
            logger.error(f"Failed to save to encrypted file: {e}")
    
    def _get_from_encrypted_file(self, service: str) -> Optional[Dict[str, str]]:
        """
        Retrieve credentials from encrypted file
        """
        try:
            if not self.config_file.exists():
                return None
            
            with open(self.config_file, 'rb') as f:
                encrypted_data = f.read()
                decrypted_data = self.cipher_suite.decrypt(encrypted_data)
                all_credentials = json.loads(decrypted_data)
            
            return all_credentials.get(service)
            
        except Exception as e:
            logger.error(f"Failed to get from encrypted file: {e}")
            return None
    
    # Convenience methods for specific services
    
    def get_breeze_credentials(self) -> Optional[Dict[str, str]]:
        """Get Breeze login credentials"""
        creds = self.get_credentials('breeze')
        
        # If not found in secure storage, try .env as fallback
        if not creds:
            from dotenv import load_dotenv
            load_dotenv()
            
            user_id = os.getenv('BREEZE_USER_ID')
            password = os.getenv('BREEZE_PASSWORD')
            
            if user_id and password:
                creds = {
                    'user_id': user_id,
                    'password': password
                }
        
        return creds
    
    def get_kite_credentials(self) -> Optional[Dict[str, str]]:
        """Get Kite login credentials"""
        creds = self.get_credentials('kite')
        
        # If not found in secure storage, try .env as fallback
        if not creds:
            from dotenv import load_dotenv
            load_dotenv()
            
            user_id = os.getenv('KITE_USER_ID')
            password = os.getenv('KITE_PASSWORD')
            pin = os.getenv('KITE_PIN')
            api_secret = os.getenv('KITE_API_SECRET')
            
            if user_id and password:
                creds = {
                    'user_id': user_id,
                    'password': password,
                    'api_secret': api_secret
                }
                if pin:
                    creds['pin'] = pin
        
        return creds
    
    def get_breeze_api_key(self) -> Optional[str]:
        """Get Breeze API key from .env"""
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv('BREEZE_API_KEY')
    
    def get_kite_api_key(self) -> Optional[str]:
        """Get Kite API key from .env"""
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv('KITE_API_KEY')
    
    def get_breeze_totp_secret(self) -> Optional[str]:
        """Get Breeze TOTP secret if configured"""
        creds = self.get_credentials('breeze_totp')
        if creds:
            return creds.get('secret')
        
        # Try .env as fallback
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv('BREEZE_TOTP_SECRET')
    
    def get_kite_totp_secret(self) -> Optional[str]:
        """Get Kite TOTP secret if configured"""
        creds = self.get_credentials('kite_totp')
        if creds:
            return creds.get('secret')
        
        # Try .env as fallback
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv('KITE_TOTP_SECRET')
    
    def save_breeze_credentials(self, user_id: str, password: str, totp_secret: str = None):
        """Save Breeze credentials"""
        creds = {
            'user_id': user_id,
            'password': password
        }
        self.save_credentials('breeze', creds)
        
        if totp_secret:
            self.save_credentials('breeze_totp', {'secret': totp_secret})
    
    def save_kite_credentials(self, user_id: str, password: str, pin: str = None, 
                            api_secret: str = None, totp_secret: str = None):
        """Save Kite credentials"""
        creds = {
            'user_id': user_id,
            'password': password
        }
        
        if pin:
            creds['pin'] = pin
        if api_secret:
            creds['api_secret'] = api_secret
            
        self.save_credentials('kite', creds)
        
        if totp_secret:
            self.save_credentials('kite_totp', {'secret': totp_secret})