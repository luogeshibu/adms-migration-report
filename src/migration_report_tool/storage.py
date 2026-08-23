"""Compatibility facade for infrastructure.database."""
from .infrastructure.database.sqlite_store import ProjectStore
__all__ = ["ProjectStore"]
