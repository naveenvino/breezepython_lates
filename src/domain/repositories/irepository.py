"""
Base Repository Interface
Domain layer repository pattern interface
"""
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Any

T = TypeVar('T')

class IRepository(ABC, Generic[T]):
    """Base repository interface for all domain repositories"""
    
    @abstractmethod
    async def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by ID"""
        pass
    
    @abstractmethod
    async def get_all(self) -> List[T]:
        """Get all entities"""
        pass
    
    @abstractmethod
    async def add(self, entity: T) -> T:
        """Add new entity"""
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update existing entity"""
        pass
    
    @abstractmethod
    async def delete(self, id: Any) -> bool:
        """Delete entity by ID"""
        pass
    
    @abstractmethod
    async def exists(self, id: Any) -> bool:
        """Check if entity exists"""
        pass