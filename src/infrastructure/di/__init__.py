"""
Dependency Injection Infrastructure
Container and dependency management
"""
from .container import ServiceContainer, get_container, get_service, inject

__all__ = [
    'ServiceContainer',
    'get_container',
    'get_service',
    'inject'
]