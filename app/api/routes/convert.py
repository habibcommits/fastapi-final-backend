# app/api/routes/convert.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
from pathlib import Path
import time
import structlog

from app.config import get_settings
from app.services.image_to_pdf import image_to_pdf_service
from app.utils.file_handler import file_handler
from app.schemas.responses import ProcessingResponse

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger()


@router.post(
    "/images-to-pdf",
    response_class=StreamingResponse,
    summary="Convert Images to PDF",
    description="Convert multiple images to a single PDF document"
)
async def convert_images_to_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Image files to convert"),
    page_size: str = Form(
        default="A4", description="Page size: A4, A3, Letter, Legal"),
    orientation: str = Form(
        default="portrait", description="portrait or landscape"),
    margin: int = Form(default=0, ge=0, le=50, description="Margin in mm")
):
    """
    Convert multiple images to a single PDF.

    - **files**: Image files (JPEG, PNG, WebP, TIFF, BMP)
    - **page_size**: Output page size
    - **orientation**: Page orientation
    - **margin**: Page margin in millimeters
    """
    start_time = time.time()
    temp_files: List[Path] = []
    output_path: Path = None

    try:
        # Validate
        file_handler.validate_files_count(len(files))

        for f in files:
            file_handler.validate_image_type(f.content_type)

        # Save uploaded files
        saved_files = await file_handler.save_multiple_files(files)
        temp_files = [path for path, _ in saved_files]

        # Generate output path
        output_path = file_handler.generate_temp_path(".pdf")

        # Convert
        output_size, pages_count = await image_to_pdf_service.convert(
            image_paths=temp_files,
            output_path=output_path,
            page_size=page_size,
            orientation=orientation,
            margin=margin
        )

        processing_time = (time.time() - start_time) * 1000

        logger.info(
            "images_to_pdf_complete",
            images_count=len(files),
            output_size=output_size,
            processing_time_ms=processing_time
        )

        # Schedule cleanup
        background_tasks.add_task(file_handler.cleanup_files, temp_files)

        # Generate output filename based on first file
        if len(files) == 1 and files[0].filename:
            base_name = Path(files[0].filename).stem
            output_filename = f"{base_name}_converted.pdf"
        else:
            output_filename = "images_converted.pdf"

        # Return the PDF
        def iterfile():
            with open(output_path, 'rb') as f:
                yield from f
            # Cleanup output after streaming
            output_path.unlink(missing_ok=True)

        return StreamingResponse(
            iterfile(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}",
                "X-Processing-Time-Ms": str(round(processing_time, 2)),
                "X-Pages-Count": str(pages_count),
            }
        )

    except Exception as e:
        # Cleanup on error
        file_handler.cleanup_files(temp_files)
        if output_path and output_path.exists():
            output_path.unlink()
        raise
