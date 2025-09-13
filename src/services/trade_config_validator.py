"""
Trade Configuration Validator
Validates mandatory fields and business rules
"""

from typing import Dict, Any, Tuple, List

class TradeConfigValidator:
    """Validates trade configuration before saving"""
    
    @staticmethod
    def get_mandatory_fields() -> Dict[str, Any]:
        """Define mandatory fields and their validation rules"""
        return {
            # CRITICAL - Must have for execution
            'num_lots': {
                'type': int,
                'min': 1,
                'max': 100,
                'default': None,  # No default - user must specify
                'error': 'Number of lots is required (1-100)'
            },
            
            'entry_timing': {
                'type': str,
                'values': ['immediate', 'delayed'],
                'default': 'immediate',  # Default to immediate as requested
                'error': 'Entry timing must be specified (immediate/delayed)'
            },
            
            # SEMI-MANDATORY - Has defaults but important
            'hedge_enabled': {
                'type': bool,
                'default': True,
                'error': 'Hedge enabled must be specified'
            },
            
            # CONDITIONAL MANDATORY - Required if hedge_enabled
            'hedge_method': {
                'type': str,
                'values': ['percentage', 'offset'],
                'default': 'percentage',
                'required_if': ('hedge_enabled', True),
                'error': 'Hedge method required when hedging is enabled'
            },
            
            'hedge_percent': {
                'type': float,
                'min': 10.0,
                'max': 50.0,
                'default': 30.0,
                'required_if': ('hedge_enabled', True, 'hedge_method', 'percentage'),
                'error': 'Hedge percentage required (10-50%)'
            },
            
            'hedge_offset': {
                'type': int,
                'min': 100,
                'max': 500,
                'default': 200,
                'required_if': ('hedge_enabled', True, 'hedge_method', 'offset'),
                'error': 'Hedge offset required (100-500 points)'
            },
            
            # SIGNAL SELECTION - Required for auto trading
            'active_signals': {
                'type': list,
                'min_items': 0,  # Can be empty but must be specified
                'max_items': 8,
                'valid_items': ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'],
                'default': [],
                'error': 'Active signals must be specified (can be empty)'
            }
        }
    
    @classmethod
    def validate(cls, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration
        Returns: (is_valid, list_of_errors)
        """
        errors = []
        mandatory_fields = cls.get_mandatory_fields()
        
        # Check absolutely mandatory fields (no defaults)
        absolutely_mandatory = ['num_lots']  # entry_timing has default now
        
        for field in absolutely_mandatory:
            if field not in config or config[field] is None:
                rule = mandatory_fields[field]
                errors.append(f"❌ {rule['error']}")
                continue
                
            # Validate type and range
            value = config[field]
            rule = mandatory_fields[field]
            
            # Type validation
            if rule['type'] == int:
                if not isinstance(value, int):
                    try:
                        value = int(value)
                        config[field] = value
                    except:
                        errors.append(f"❌ {field} must be a number")
                        continue
                        
                if 'min' in rule and value < rule['min']:
                    errors.append(f"❌ {field} must be at least {rule['min']}")
                if 'max' in rule and value > rule['max']:
                    errors.append(f"❌ {field} must be at most {rule['max']}")
                    
            elif rule['type'] == float:
                if not isinstance(value, (int, float)):
                    try:
                        value = float(value)
                        config[field] = value
                    except:
                        errors.append(f"❌ {field} must be a number")
                        continue
                        
                if 'min' in rule and value < rule['min']:
                    errors.append(f"❌ {field} must be at least {rule['min']}")
                if 'max' in rule and value > rule['max']:
                    errors.append(f"❌ {field} must be at most {rule['max']}")
                    
            elif rule['type'] == str:
                if 'values' in rule and value not in rule['values']:
                    errors.append(f"❌ {field} must be one of: {', '.join(rule['values'])}")
                    
            elif rule['type'] == list:
                if not isinstance(value, list):
                    errors.append(f"❌ {field} must be a list")
                    continue
                    
                if 'min_items' in rule and len(value) < rule['min_items']:
                    errors.append(f"❌ {field} must have at least {rule['min_items']} items")
                if 'max_items' in rule and len(value) > rule['max_items']:
                    errors.append(f"❌ {field} must have at most {rule['max_items']} items")
                if 'valid_items' in rule:
                    invalid = [item for item in value if item not in rule['valid_items']]
                    if invalid:
                        errors.append(f"❌ Invalid signals: {', '.join(invalid)}")
        
        # Conditional validations
        if config.get('hedge_enabled'):
            if not config.get('hedge_method'):
                errors.append("❌ Hedge method required when hedging is enabled")
            elif config['hedge_method'] == 'percentage':
                if not config.get('hedge_percent'):
                    errors.append("❌ Hedge percentage required")
            elif config['hedge_method'] == 'offset':
                if not config.get('hedge_offset'):
                    errors.append("❌ Hedge offset required")
        
        # Profit lock validation
        if config.get('profit_lock_enabled'):
            if not config.get('profit_target'):
                errors.append("❌ Profit target required when profit lock is enabled")
            if not config.get('profit_lock'):
                errors.append("❌ Profit lock level required when profit lock is enabled")
            if config.get('profit_target') and config.get('profit_lock'):
                if config['profit_lock'] >= config['profit_target']:
                    errors.append("❌ Profit lock must be less than profit target")
        
        # Trailing stop validation
        if config.get('trailing_stop_enabled'):
            if not config.get('trail_percent'):
                errors.append("❌ Trail percent required when trailing stop is enabled")
        
        return (len(errors) == 0, errors)
    
    @classmethod
    def apply_defaults(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values for non-mandatory fields"""
        defaults = {
            'entry_timing': 'immediate',  # Default to immediate
            'hedge_enabled': True,
            'hedge_method': 'percentage',
            'hedge_percent': 30.0,
            'hedge_offset': 200,
            'profit_lock_enabled': False,
            'profit_target': 10.0,
            'profit_lock': 5.0,
            'trailing_stop_enabled': False,
            'trail_percent': 1.0,
            'auto_trade_enabled': False,
            'active_signals': [],
            'telegram_enabled': False,
            'telegram_bot_token': '',
            'telegram_chat_id': '',
            'email_enabled': False,
            'email_from': '',
            'email_to': '',
            'alert_trade_entry': True,
            'alert_trade_exit': True,
            'alert_stop_loss': True,
            'alert_risk_warnings': True,
            'alert_daily_summary': False
        }
        
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value
                
        return config
    
    @classmethod
    def get_validation_summary(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of validation status"""
        is_valid, errors = cls.validate(config)
        
        mandatory_fields = cls.get_mandatory_fields()
        absolutely_mandatory = ['num_lots', 'entry_timing']
        
        filled_mandatory = []
        missing_mandatory = []
        
        for field in absolutely_mandatory:
            if field in config and config[field] is not None:
                filled_mandatory.append(field)
            else:
                missing_mandatory.append(field)
        
        return {
            'is_valid': is_valid,
            'errors': errors,
            'filled_mandatory': filled_mandatory,
            'missing_mandatory': missing_mandatory,
            'can_trade': is_valid and len(missing_mandatory) == 0,
            'message': 'Configuration is valid' if is_valid else f'{len(errors)} validation errors found'
        }