"""
Encryption Service for Sensitive Data
Handles encryption and decryption of API keys and credentials
"""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    def __init__(self, master_key: Optional[str] = None):
        """Initialize encryption service with master key"""
        if master_key:
            self.master_key = master_key.encode()
        else:
            # Generate or load master key
            self.master_key = self._get_or_create_master_key()
            
        # Derive encryption key from master key
        self.cipher = self._create_cipher()
        
        # Path for encrypted credentials
        self.credentials_file = "credentials.enc"
        
    def _get_or_create_master_key(self) -> bytes:
        """Get master key from environment or create new one"""
        # Try to get from environment
        env_key = os.getenv("ENCRYPTION_MASTER_KEY")
        if env_key:
            return env_key.encode()
            
        # Try to load from file
        key_file = ".encryption_key"
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
                
        # Generate new key
        key = Fernet.generate_key()
        
        # Save to file (should be in .gitignore)
        with open(key_file, 'wb') as f:
            f.write(key)
            
        logger.warning(f"New encryption key generated and saved to {key_file}")
        logger.warning("IMPORTANT: Back up this key securely and add to .gitignore!")
        
        return key
        
    def _create_cipher(self) -> Fernet:
        """Create Fernet cipher from master key"""
        # Use PBKDF2HMAC to derive a key from the master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'stable_salt_for_app',  # Use stable salt for deterministic key
            iterations=100000,
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        return Fernet(key)
        
    def encrypt_string(self, plaintext: str) -> str:
        """Encrypt a string"""
        encrypted = self.cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
        
    def decrypt_string(self, ciphertext: str) -> str:
        """Decrypt a string"""
        try:
            encrypted = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")
            
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt a dictionary"""
        json_str = json.dumps(data)
        return self.encrypt_string(json_str)
        
    def decrypt_dict(self, ciphertext: str) -> Dict[str, Any]:
        """Decrypt to dictionary"""
        json_str = self.decrypt_string(ciphertext)
        return json.loads(json_str)
        
    def save_credentials(self, broker: str, credentials: Dict[str, str]):
        """Save encrypted broker credentials"""
        try:
            # Load existing credentials
            all_creds = self.load_all_credentials()
            
            # Encrypt new credentials
            encrypted = self.encrypt_dict(credentials)
            
            # Update
            all_creds[broker] = encrypted
            
            # Save to file
            with open(self.credentials_file, 'w') as f:
                json.dump(all_creds, f, indent=2)
                
            logger.info(f"Credentials saved for {broker}")
            
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            raise
            
    def load_credentials(self, broker: str) -> Optional[Dict[str, str]]:
        """Load and decrypt broker credentials"""
        try:
            all_creds = self.load_all_credentials()
            
            if broker not in all_creds:
                return None
                
            encrypted = all_creds[broker]
            return self.decrypt_dict(encrypted)
            
        except Exception as e:
            logger.error(f"Failed to load credentials for {broker}: {e}")
            return None
            
    def load_all_credentials(self) -> Dict[str, str]:
        """Load all encrypted credentials"""
        if not os.path.exists(self.credentials_file):
            return {}
            
        try:
            with open(self.credentials_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load credentials file: {e}")
            return {}
            
    def delete_credentials(self, broker: str) -> bool:
        """Delete broker credentials"""
        try:
            all_creds = self.load_all_credentials()
            
            if broker in all_creds:
                del all_creds[broker]
                
                with open(self.credentials_file, 'w') as f:
                    json.dump(all_creds, f, indent=2)
                    
                logger.info(f"Credentials deleted for {broker}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete credentials: {e}")
            return False
            
    def list_stored_brokers(self) -> list:
        """List brokers with stored credentials"""
        all_creds = self.load_all_credentials()
        return list(all_creds.keys())
        
    def encrypt_api_key(self, api_key: str, api_secret: str) -> Dict[str, str]:
        """Encrypt API key and secret"""
        return {
            "api_key": self.encrypt_string(api_key),
            "api_secret": self.encrypt_string(api_secret)
        }
        
    def decrypt_api_key(self, encrypted_data: Dict[str, str]) -> Dict[str, str]:
        """Decrypt API key and secret"""
        return {
            "api_key": self.decrypt_string(encrypted_data["api_key"]),
            "api_secret": self.decrypt_string(encrypted_data["api_secret"])
        }
        
    def rotate_encryption_key(self, new_master_key: str) -> bool:
        """Rotate encryption key (re-encrypt all data with new key)"""
        try:
            # Load all credentials with old key
            all_creds = {}
            for broker in self.list_stored_brokers():
                creds = self.load_credentials(broker)
                if creds:
                    all_creds[broker] = creds
                    
            # Create new cipher with new key
            old_cipher = self.cipher
            self.master_key = new_master_key.encode()
            self.cipher = self._create_cipher()
            
            # Re-encrypt all credentials
            for broker, creds in all_creds.items():
                self.save_credentials(broker, creds)
                
            # Save new master key
            key_file = ".encryption_key"
            with open(key_file, 'wb') as f:
                f.write(self.master_key)
                
            logger.info("Encryption key rotated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            # Restore old cipher
            self.cipher = old_cipher
            return False
            
    def secure_wipe_file(self, filepath: str):
        """Securely delete a file by overwriting with random data"""
        try:
            if not os.path.exists(filepath):
                return
                
            filesize = os.path.getsize(filepath)
            
            with open(filepath, "ba+", buffering=0) as f:
                # Overwrite with random data 3 times
                for _ in range(3):
                    f.seek(0)
                    f.write(os.urandom(filesize))
                    
            # Finally delete
            os.remove(filepath)
            logger.info(f"Securely deleted {filepath}")
            
        except Exception as e:
            logger.error(f"Secure wipe failed: {e}")
            
class SecureConfig:
    """Secure configuration management"""
    
    def __init__(self, encryption_service: Optional[EncryptionService] = None):
        self.encryption_service = encryption_service or EncryptionService()
        self.config_file = "secure_config.enc"
        
    def set(self, key: str, value: Any, encrypt: bool = True):
        """Set configuration value"""
        config = self._load_config()
        
        if encrypt and isinstance(value, str):
            value = self.encryption_service.encrypt_string(value)
            
        config[key] = {
            "value": value,
            "encrypted": encrypt,
            "updated": datetime.now().isoformat()
        }
        
        self._save_config(config)
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        config = self._load_config()
        
        if key not in config:
            return default
            
        item = config[key]
        value = item["value"]
        
        if item.get("encrypted") and isinstance(value, str):
            try:
                value = self.encryption_service.decrypt_string(value)
            except Exception as e:
                logger.error(f"Failed to decrypt config value: {e}")
                return default
                
        return value
        
    def delete(self, key: str) -> bool:
        """Delete configuration value"""
        config = self._load_config()
        
        if key in config:
            del config[key]
            self._save_config(config)
            return True
            
        return False
        
    def list_keys(self) -> list:
        """List all configuration keys"""
        config = self._load_config()
        return list(config.keys())
        
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            return {}
            
        try:
            with open(self.config_file, 'r') as f:
                encrypted = f.read()
                if encrypted:
                    return self.encryption_service.decrypt_dict(encrypted)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            
        return {}
        
    def _save_config(self, config: Dict):
        """Save configuration to file"""
        try:
            encrypted = self.encryption_service.encrypt_dict(config)
            with open(self.config_file, 'w') as f:
                f.write(encrypted)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

# Singleton instances
_encryption_service = None
_secure_config = None

def get_encryption_service() -> EncryptionService:
    """Get or create encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service

def get_secure_config() -> SecureConfig:
    """Get or create secure config instance"""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfig()
    return _secure_config