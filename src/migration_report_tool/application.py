"""Compatibility facade; new code imports migration_report_tool.app."""
from .app.application import main
__all__ = ["main"]
