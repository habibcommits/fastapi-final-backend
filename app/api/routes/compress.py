# app/api/routes/compress.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from pathlib import Path
import time
import structlog

from app.config import get_settings
from app.services.pdf_compressor import pdf_compressor_service
from app.utils.file_handler import file_handler
from app.schemas.responses import CompressionLevel

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger()


@router.post(
    "/compress-pdf",
    response_class=StreamingResponse,
    summary="Compress PDF",
    description="Compress a PDF file to reduce size"
)
async def compress_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to compress"),
    level: CompressionLevel = Form(
        default=CompressionLevel.MEDIUM,
        description="Compression level: low, medium, high, maximum"
    ),
    remove_metadata: bool = Form(
        default=False,
        description="Remove document metadata"
    ),
    linearize: bool = Form(
        default=True,
        description="Optimize for web viewing"
    )
):
    """
    Compress a PDF file.

    - **file**: PDF file to compress
    - **level**: Compression intensity
        - low: ~90% quality, minimal compression
        - medium: ~75% quality, balanced
        - high: ~60% quality, significant compression
        - maximum: ~40% quality, maximum compression
    - **remove_metadata**: Strip metadata from PDF
    - **linearize**: Optimize for progressive web loading
    """
    start_time = time.time()
    input_path: Path = None
    output_path: Path = None

    try:
        # Validate
        file_handler.validate_pdf_type(file.content_type, file.filename)

        # Save uploaded file
        saved = await file_handler.save_upload_file(file)
        input_path, original_size = saved

        # Validate file size
        if original_size > settings.max_file_size_bytes:
            from app.utils.exceptions import FileTooLargeException
            raise FileTooLargeException(settings.max_file_size_mb)

        # Generate output path
        output_path = file_handler.generate_temp_path(".pdf")

        # Compress
        original_size, compressed_size, pages_count = await pdf_compressor_service.compress(
            input_path=input_path,
            output_path=output_path,
            level=level,
            remove_metadata=remove_metadata,
            linearize=linearize
        )

        processing_time = (time.time() - start_time) * 1000
        compression_ratio = round(
            (1 - compressed_size / original_size) * 100, 2)

        logger.info(
            "compression_complete",
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=f"{compression_ratio}%",
            processing_time_ms=processing_time
        )

        # Schedule cleanup
        background_tasks.add_task(file_handler.cleanup_files, [input_path])

        # Generate output filename
        original_name = Path(
            file.filename).stem if file.filename else "document"
        output_filename = f"{original_name}_compressed.pdf"

        # Return the compressed PDF
        def iterfile():
            with open(output_path, 'rb') as f:
                yield from f
            output_path.unlink(missing_ok=True)

        return StreamingResponse(
            iterfile(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Processing-Time-Ms": str(round(processing_time, 2)),
                "X-Original-Size": str(original_size),
                "X-Compressed-Size": str(compressed_size),
                "X-Compression-Ratio": f"{compression_ratio}%",
                "X-Pages-Count": str(pages_count),
            }
        )

    except Exception as e:
        if input_path and input_path.exists():
            input_path.unlink()
        if output_path and output_path.exists():
            output_path.unlink()
        raise
