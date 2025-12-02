# app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List
import os


class Settings(BaseSettings):
    """Application settings with validation."""

    # App Info
    app_name: str = Field(default="PDF Processing Service")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # File Processing
    max_file_size_mb: int = Field(default=50)
    max_files_count: int = Field(default=20)
    allowed_image_types: str = Field(
        default="image/jpeg,image/png,image/webp,image/tiff,image/bmp"
    )
    temp_dir: str = Field(default="/tmp/pdf-service")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=30)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=4)

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def allowed_image_types_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_image_types.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    settings = Settings()
    os.makedirs(settings.temp_dir, exist_ok=True)
    return settings
