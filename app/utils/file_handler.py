# app/utils/file_handler.py
import os
import uuid
import aiofiles
import asyncio
from pathlib import Path
from typing import List, Tuple, BinaryIO
from fastapi import UploadFile
from contextlib import asynccontextmanager
import structlog

from app.config import get_settings
from app.utils.exceptions import (
    FileTooLargeException,
    InvalidFileTypeException,
    TooManyFilesException
)

logger = structlog.get_logger()
settings = get_settings()


class FileHandler:
    """Handles file operations with validation and cleanup."""

    def __init__(self):
        self.temp_dir = Path(settings.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def generate_temp_path(self, extension: str = "") -> Path:
        """Generate a unique temporary file path."""
        filename = f"{uuid.uuid4()}{extension}"
        return self.temp_dir / filename

    async def validate_file_size(self, file: UploadFile) -> int:
        """Validate and return file size."""
        # Read file to get size
        content = await file.read()
        size = len(content)

        if size > settings.max_file_size_bytes:
            raise FileTooLargeException(settings.max_file_size_mb)

        # Reset file position
        await file.seek(0)
        return size

    def validate_image_type(self, content_type: str) -> None:
        """Validate image content type."""
        if content_type not in settings.allowed_image_types_list:
            raise InvalidFileTypeException(
                content_type,
                settings.allowed_image_types_list
            )

    def validate_pdf_type(self, content_type: str, filename: str) -> None:
        """Validate PDF content type."""
        valid_types = ["application/pdf"]
        if content_type not in valid_types and not filename.lower().endswith('.pdf'):
            raise InvalidFileTypeException(content_type, valid_types)

    def validate_files_count(self, count: int) -> None:
        """Validate number of files."""
        if count > settings.max_files_count:
            raise TooManyFilesException(settings.max_files_count)
        if count == 0:
            raise TooManyFilesException(0)

    async def save_upload_file(self, file: UploadFile) -> Tuple[Path, int]:
        """Save uploaded file to temp directory."""
        ext = Path(file.filename).suffix if file.filename else ""
        temp_path = self.generate_temp_path(ext)

        content = await file.read()
        size = len(content)

        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content)

        logger.info("file_saved", path=str(temp_path), size=size)
        return temp_path, size

    async def save_multiple_files(
        self,
        files: List[UploadFile]
    ) -> List[Tuple[Path, int]]:
        """Save multiple files concurrently."""
        tasks = [self.save_upload_file(f) for f in files]
        return await asyncio.gather(*tasks)

    def cleanup_files(self, paths: List[Path]) -> None:
        """Remove temporary files."""
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
                    logger.debug("file_cleaned", path=str(path))
            except Exception as e:
                logger.warning("cleanup_failed", path=str(path), error=str(e))

    @asynccontextmanager
    async def temp_file_context(self, extension: str = ""):
        """Context manager for temporary files with automatic cleanup."""
        temp_path = self.generate_temp_path(extension)
        try:
            yield temp_path
        finally:
            self.cleanup_files([temp_path])


file_handler = FileHandler()
