"""
Base Entity and Value Object classes for Domain Layer
Following Domain-Driven Design principles
"""
from abc import ABC
from typing import Any, Dict
from datetime import datetime
import uuid


class Entity(ABC):
    """Base class for all domain entities"""
    
    def __init__(self, id: Any = None):
        self._id = id or self._generate_id()
        self._created_at = datetime.utcnow()
        self._updated_at = None
    
    @property
    def id(self) -> Any:
        return self._id
    
    @property
    def created_at(self) -> datetime:
        return self._created_at
    
    @property
    def updated_at(self) -> datetime:
        return self._updated_at
    
    def _generate_id(self) -> str:
        """Generate a unique ID for the entity"""
        return str(uuid.uuid4())
    
    def mark_updated(self):
        """Mark entity as updated"""
        self._updated_at = datetime.utcnow()
    
    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return self._id == other._id
    
    def __hash__(self):
        return hash(self._id)


class ValueObject(ABC):
    """Base class for value objects"""
    
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__
    
    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert value object to dictionary"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class AggregateRoot(Entity):
    """Base class for aggregate roots"""
    
    def __init__(self, id: Any = None):
        super().__init__(id)
        self._domain_events = []
    
    def add_domain_event(self, event: 'DomainEvent'):
        """Add a domain event"""
        self._domain_events.append(event)
    
    def clear_domain_events(self):
        """Clear all domain events"""
        self._domain_events.clear()
    
    @property
    def domain_events(self) -> list:
        """Get all domain events"""
        return self._domain_events.copy()


class DomainEvent:
    """Base class for domain events"""
    
    def __init__(self):
        self.occurred_at = datetime.utcnow()
        self.event_id = str(uuid.uuid4())
    
    @property
    def event_name(self) -> str:
        """Get event name"""
        return self.__class__.__name__