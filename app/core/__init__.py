"""Core application package.

This package contains shared application configuration and low-level utilities
used across routers, services, clients, and schemas.
"""

from app.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]