"""
Database Base
SQLAlchemy declarative base for all models
"""
from sqlalchemy.ext.declarative import declarative_base

# Create the declarative base
Base = declarative_base()

# Export Base
__all__ = ['Base']