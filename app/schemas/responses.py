# app/schemas/responses.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class CompressionLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAXIMUM = "maximum"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProcessingResponse(BaseModel):
    success: bool
    message: str
    filename: str
    original_size_bytes: Optional[int] = None
    processed_size_bytes: Optional[int] = None
    compression_ratio: Optional[float] = None
    pages_count: Optional[int] = None
    processing_time_ms: float


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversionRequest(BaseModel):
    page_size: str = Field(
        default="A4", description="Page size: A4, Letter, Legal")
    orientation: str = Field(
        default="portrait", description="portrait or landscape")
    margin: int = Field(default=0, ge=0, le=100,
                        description="Margin in pixels")


class MergeRequest(BaseModel):
    output_filename: str = Field(
        default="merged.pdf", description="Output filename")


class CompressionRequest(BaseModel):
    level: CompressionLevel = Field(
        default=CompressionLevel.MEDIUM,
        description="Compression level"
    )
    remove_metadata: bool = Field(default=False)
    linearize: bool = Field(
        default=True, description="Optimize for web viewing")
