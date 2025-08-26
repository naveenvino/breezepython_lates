from typing import Dict, Any, Optional
from .base_broker import BaseBroker
from .breeze_broker import BreezeBroker
import os
from dotenv import load_dotenv

load_dotenv()

class BrokerFactory:
    """Factory class for creating broker instances"""
    
    _brokers = {
        "breeze": BreezeBroker,
        "icici": BreezeBroker,  # Alias for Breeze
    }
    
    _instances = {}
    
    @classmethod
    def register_broker(cls, name: str, broker_class: type):
        """Register a new broker implementation"""
        if not issubclass(broker_class, BaseBroker):
            raise ValueError(f"{broker_class} must inherit from BaseBroker")
        cls._brokers[name.lower()] = broker_class
        
    @classmethod
    def create_broker(
        cls, 
        broker_name: str, 
        config: Optional[Dict[str, Any]] = None,
        use_singleton: bool = True
    ) -> BaseBroker:
        """
        Create or get a broker instance
        
        Args:
            broker_name: Name of the broker (e.g., 'breeze', 'zerodha')
            config: Broker configuration. If None, will try to load from environment
            use_singleton: If True, returns cached instance if available
        """
        broker_name = broker_name.lower()
        
        if broker_name not in cls._brokers:
            available = ", ".join(cls._brokers.keys())
            raise ValueError(f"Unknown broker: {broker_name}. Available: {available}")
            
        if use_singleton and broker_name in cls._instances:
            return cls._instances[broker_name]
            
        if config is None:
            config = cls._get_config_from_env(broker_name)
            
        broker_class = cls._brokers[broker_name]
        broker_instance = broker_class(config)
        
        if use_singleton:
            cls._instances[broker_name] = broker_instance
            
        return broker_instance
        
    @classmethod
    def _get_config_from_env(cls, broker_name: str) -> Dict[str, Any]:
        """Load broker configuration from environment variables"""
        
        if broker_name in ["breeze", "icici"]:
            return {
                "api_key": os.getenv("BREEZE_API_KEY"),
                "api_secret": os.getenv("BREEZE_API_SECRET"),
                "session_token": os.getenv("BREEZE_API_SESSION")
            }
        elif broker_name == "zerodha":
            return {
                "api_key": os.getenv("KITE_API_KEY"),
                "api_secret": os.getenv("KITE_API_SECRET"),
                "access_token": os.getenv("KITE_ACCESS_TOKEN")
            }
        else:
            raise ValueError(f"No environment configuration for {broker_name}")
            
    @classmethod
    def get_available_brokers(cls) -> list:
        """Get list of available broker names"""
        return list(cls._brokers.keys())
        
    @classmethod
    def clear_cache(cls, broker_name: Optional[str] = None):
        """Clear cached broker instances"""
        if broker_name:
            cls._instances.pop(broker_name.lower(), None)
        else:
            cls._instances.clear()


class MultiBrokerManager:
    """Manage multiple broker connections simultaneously"""
    
    def __init__(self):
        self.brokers: Dict[str, BaseBroker] = {}
        self.primary_broker: Optional[str] = None
        
    def add_broker(
        self, 
        name: str, 
        broker_name: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a broker to the manager"""
        try:
            broker = BrokerFactory.create_broker(broker_name, config)
            if broker.connect():
                self.brokers[name] = broker
                if self.primary_broker is None:
                    self.primary_broker = name
                return True
            return False
        except Exception as e:
            print(f"Failed to add broker {name}: {e}")
            return False
            
    def remove_broker(self, name: str):
        """Remove a broker from the manager"""
        if name in self.brokers:
            self.brokers[name].disconnect()
            del self.brokers[name]
            if self.primary_broker == name:
                self.primary_broker = next(iter(self.brokers.keys()), None)
                
    def get_broker(self, name: Optional[str] = None) -> Optional[BaseBroker]:
        """Get a specific broker or the primary broker"""
        if name:
            return self.brokers.get(name)
        elif self.primary_broker:
            return self.brokers.get(self.primary_broker)
        return None
        
    def set_primary(self, name: str):
        """Set the primary broker"""
        if name in self.brokers:
            self.primary_broker = name
        else:
            raise ValueError(f"Broker {name} not found")
            
    def execute_on_all(self, method_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a method on all connected brokers"""
        results = {}
        for name, broker in self.brokers.items():
            try:
                method = getattr(broker, method_name)
                results[name] = method(*args, **kwargs)
            except Exception as e:
                results[name] = {"error": str(e)}
        return results
        
    def disconnect_all(self):
        """Disconnect all brokers"""
        for broker in self.brokers.values():
            broker.disconnect()
        self.brokers.clear()
        self.primary_broker = None