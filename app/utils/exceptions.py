# app/utils/exceptions.py
from fastapi import HTTPException, status
from typing import Any, Optional, Dict


class PDFServiceException(HTTPException):
    """Base exception for PDF service."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class FileTooLargeException(PDFServiceException):
    def __init__(self, max_size_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )


class InvalidFileTypeException(PDFServiceException):
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{file_type}' not allowed. Allowed: {allowed_types}"
        )


class TooManyFilesException(PDFServiceException):
    def __init__(self, max_count: int):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many files. Maximum allowed: {max_count}"
        )


class ProcessingException(PDFServiceException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing error: {detail}"
        )


class InvalidPDFException(PDFServiceException):
    def __init__(self, filename: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or corrupted PDF file: {filename}"
        )
