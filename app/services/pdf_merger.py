# app/services/pdf_merger.py
from pypdf import PdfReader, PdfWriter
from pathlib import Path
from typing import List, Tuple
import structlog

from app.utils.exceptions import ProcessingException, InvalidPDFException

logger = structlog.get_logger()


class PDFMergerService:
    """Service to merge multiple PDF files."""

    def __init__(self):
        pass

    def _validate_pdf(self, path: Path) -> PdfReader:
        """Validate and open PDF file."""
        try:
            reader = PdfReader(str(path))
            # Try to access pages to verify PDF is valid
            _ = len(reader.pages)
            return reader
        except Exception as e:
            logger.error("invalid_pdf", path=str(path), error=str(e))
            raise InvalidPDFException(path.name)

    async def merge(
        self,
        pdf_paths: List[Path],
        output_path: Path,
        add_bookmarks: bool = True
    ) -> Tuple[int, int]:
        """
        Merge multiple PDFs into one.

        Args:
            pdf_paths: List of PDF file paths in order
            output_path: Output PDF path
            add_bookmarks: Whether to add bookmarks for each merged PDF

        Returns:
            Tuple of (output_size, total_pages)
        """
        try:
            writer = PdfWriter()
            total_pages = 0

            for idx, pdf_path in enumerate(pdf_paths):
                logger.debug("processing_pdf", index=idx, path=str(pdf_path))

                reader = self._validate_pdf(pdf_path)
                pages_in_file = len(reader.pages)

                # Add bookmark at the start of each document
                if add_bookmarks:
                    bookmark_title = pdf_path.stem or f"Document {idx + 1}"
                    writer.add_outline_item(
                        title=bookmark_title,
                        page_number=total_pages
                    )

                # Add all pages from this PDF
                for page in reader.pages:
                    writer.add_page(page)

                total_pages += pages_in_file

            # Write the merged PDF
            with open(output_path, 'wb') as f:
                writer.write(f)

            output_size = output_path.stat().st_size

            logger.info(
                "merge_complete",
                files_merged=len(pdf_paths),
                total_pages=total_pages,
                output_size=output_size
            )

            return output_size, total_pages

        except InvalidPDFException:
            raise
        except Exception as e:
            logger.error("merge_failed", error=str(e))
            raise ProcessingException(f"PDF merge failed: {str(e)}")


pdf_merger_service = PDFMergerService()
