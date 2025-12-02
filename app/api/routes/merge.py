# app/api/routes/merge.py
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List
from pathlib import Path
import time
import structlog

from app.config import get_settings
from app.services.pdf_merger import pdf_merger_service
from app.utils.file_handler import file_handler

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger()


@router.post(
    "/merge-pdfs",
    response_class=StreamingResponse,
    summary="Merge PDFs",
    description="Merge multiple PDF files into one"
)
async def merge_pdfs(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...,
                                   description="PDF files to merge (in order)"),
    output_filename: str = Form(
        default="merged.pdf", description="Output filename"),
    add_bookmarks: bool = Form(
        default=True, description="Add bookmarks for each document")
):
    """
    Merge multiple PDF files into a single PDF.

    - **files**: PDF files to merge (order matters)
    - **output_filename**: Name for the merged PDF
    - **add_bookmarks**: Whether to add bookmarks/outline for each merged document
    """
    start_time = time.time()
    temp_files: List[Path] = []
    output_path: Path = None

    try:
        # Validate
        file_handler.validate_files_count(len(files))

        for f in files:
            file_handler.validate_pdf_type(f.content_type, f.filename)

        # Save uploaded files
        saved_files = await file_handler.save_multiple_files(files)
        temp_files = [path for path, _ in saved_files]

        # Generate output path
        output_path = file_handler.generate_temp_path(".pdf")

        # Merge
        output_size, total_pages = await pdf_merger_service.merge(
            pdf_paths=temp_files,
            output_path=output_path,
            add_bookmarks=add_bookmarks
        )

        processing_time = (time.time() - start_time) * 1000

        logger.info(
            "merge_complete",
            pdfs_count=len(files),
            total_pages=total_pages,
            output_size=output_size,
            processing_time_ms=processing_time
        )

        # Schedule cleanup
        background_tasks.add_task(file_handler.cleanup_files, temp_files)

        # Sanitize filename
        safe_filename = "".join(
            c for c in output_filename
            if c.isalnum() or c in "._-"
        )
        if not safe_filename.endswith('.pdf'):
            safe_filename += '.pdf'

        # Return the merged PDF
        def iterfile():
            with open(output_path, 'rb') as f:
                yield from f
            output_path.unlink(missing_ok=True)

        return StreamingResponse(
            iterfile(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={safe_filename}",
                "X-Processing-Time-Ms": str(round(processing_time, 2)),
                "X-Total-Pages": str(total_pages),
                "X-Files-Merged": str(len(files)),
            }
        )

    except Exception as e:
        file_handler.cleanup_files(temp_files)
        if output_path and output_path.exists():
            output_path.unlink()
        raise
