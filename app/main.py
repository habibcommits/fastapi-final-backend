from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog
import logging  # Add this import
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.api.routes import health, convert, merge, compress
from app.api.dependencies import limiter
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.exceptions import PDFServiceException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

settings = get_settings()

# Map string log levels to logging module constants
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug
        else structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        LOG_LEVELS.get(settings.log_level.upper(), logging.INFO)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(
        "application_startup",
        app_name=settings.app_name,
        version=settings.app_version,
        debug=settings.debug
    )
    yield
    logger.info("application_shutdown")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## PDF Processing Service

A professional-grade API for PDF operations:

- **Convert Images to PDF**: Convert multiple images into a single PDF document
- **Merge PDFs**: Combine multiple PDF files into one
- **Compress PDF**: Reduce PDF file size with various compression levels

### Features
- High-performance async processing
- Multiple compression levels
- Automatic file cleanup
- Detailed processing metrics
- Rate limiting
- Request logging
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "X-Processing-Time-Ms",
        "X-Original-Size",
        "X-Compressed-Size",
        "X-Compression-Ratio",
        "X-Pages-Count",
        "X-Total-Pages",
        "X-Files-Merged",
    ],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Serve static files (frontend)
frontend_path = os.path.join(os.path.dirname(
    os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/app", include_in_schema=False)
    async def serve_frontend():
        """Serve the frontend application."""
        return FileResponse(os.path.join(frontend_path, "index.html"))


# Exception handlers
@app.exception_handler(PDFServiceException)
async def pdf_service_exception_handler(
    request: Request,
    exc: PDFServiceException
):
    """Handle custom PDF service exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An unexpected error occurred",
        }
    )


# Include routers
app.include_router(
    health.router,
    tags=["Health"]
)

app.include_router(
    convert.router,
    prefix="/api/v1",
    tags=["Convert"]
)

app.include_router(
    merge.router,
    prefix="/api/v1",
    tags=["Merge"]
)

app.include_router(
    compress.router,
    prefix="/api/v1",
    tags=["Compress"]
)


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirect to docs."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers
    )
