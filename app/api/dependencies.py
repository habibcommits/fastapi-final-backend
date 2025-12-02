# app/api/dependencies.py
from fastapi import Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings, Settings


def get_limiter() -> Limiter:
    """Get rate limiter instance."""
    return Limiter(key_func=get_remote_address)


limiter = get_limiter()


async def get_settings_dependency() -> Settings:
    """Dependency to get settings."""
    return get_settings()
