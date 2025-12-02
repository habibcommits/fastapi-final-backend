# app/services/pdf_compressor.py
import pikepdf
from pypdf import PdfReader, PdfWriter
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
from io import BytesIO
import structlog

from app.schemas.responses import CompressionLevel
from app.utils.exceptions import ProcessingException, InvalidPDFException

logger = structlog.get_logger()


class PDFCompressorService:
    """Service to compress PDF files."""

    # Compression settings for different levels
    COMPRESSION_SETTINGS = {
        CompressionLevel.LOW: {
            "image_quality": 90,
            "image_dpi": 200,
            "compress_streams": True,
        },
        CompressionLevel.MEDIUM: {
            "image_quality": 75,
            "image_dpi": 150,
            "compress_streams": True,
        },
        CompressionLevel.HIGH: {
            "image_quality": 60,
            "image_dpi": 120,
            "compress_streams": True,
        },
        CompressionLevel.MAXIMUM: {
            "image_quality": 40,
            "image_dpi": 96,
            "compress_streams": True,
        },
    }

    def __init__(self):
        pass

    def _validate_pdf(self, path: Path) -> None:
        """Validate PDF file."""
        try:
            with pikepdf.open(path) as pdf:
                _ = len(pdf.pages)
        except Exception as e:
            logger.error("invalid_pdf", path=str(path), error=str(e))
            raise InvalidPDFException(path.name)

    async def compress(
        self,
        input_path: Path,
        output_path: Path,
        level: CompressionLevel = CompressionLevel.MEDIUM,
        remove_metadata: bool = False,
        linearize: bool = True
    ) -> Tuple[int, int, int]:
        """
        Compress a PDF file.

        Args:
            input_path: Input PDF path
            output_path: Output PDF path
            level: Compression level
            remove_metadata: Whether to remove metadata
            linearize: Whether to linearize for web viewing

        Returns:
            Tuple of (original_size, compressed_size, pages_count)
        """
        try:
            self._validate_pdf(input_path)
            original_size = input_path.stat().st_size

            settings = self.COMPRESSION_SETTINGS[level]

            logger.info(
                "compressing_pdf",
                level=level.value,
                original_size=original_size,
                settings=settings
            )

            with pikepdf.open(input_path) as pdf:
                pages_count = len(pdf.pages)

                # Compress images in the PDF
                self._compress_images(pdf, settings)

                # Remove metadata if requested
                if remove_metadata:
                    self._remove_metadata(pdf)

                # Save with compression options
                pdf.save(
                    output_path,
                    linearize=linearize,
                    compress_streams=settings["compress_streams"],
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                    recompress_flate=True,
                )

            compressed_size = output_path.stat().st_size

            logger.info(
                "compression_complete",
                original_size=original_size,
                compressed_size=compressed_size,
                ratio=round(compressed_size / original_size * 100, 2),
                pages=pages_count
            )

            return original_size, compressed_size, pages_count

        except InvalidPDFException:
            raise
        except Exception as e:
            logger.error("compression_failed", error=str(e))
            raise ProcessingException(f"PDF compression failed: {str(e)}")

    def _compress_images(self, pdf: pikepdf.Pdf, settings: dict) -> None:
        """Compress images within the PDF."""
        quality = settings["image_quality"]
        target_dpi = settings["image_dpi"]

        for page in pdf.pages:
            try:
                self._process_page_images(page, quality, target_dpi)
            except Exception as e:
                logger.warning("image_compression_warning", error=str(e))
                continue

    def _process_page_images(
        self,
        page: pikepdf.Page,
        quality: int,
        target_dpi: int
    ) -> None:
        """Process and compress images on a page."""
        if "/Resources" not in page:
            return

        resources = page["/Resources"]
        if "/XObject" not in resources:
            return

        xobjects = resources["/XObject"]

        for key in list(xobjects.keys()):
            try:
                xobj = xobjects[key]
                if not hasattr(xobj, "keys"):
                    continue

                if xobj.get("/Subtype") == pikepdf.Name.Image:
                    self._compress_single_image(xobjects, key, xobj, quality)
            except Exception:
                continue

    def _compress_single_image(
        self,
        xobjects,
        key: str,
        xobj,
        quality: int
    ) -> None:
        """Compress a single image object."""
        try:
            # Skip if already highly compressed
            if xobj.get("/Filter") in [
                pikepdf.Name.DCTDecode,
                pikepdf.Name.JPXDecode
            ]:
                return

            width = int(xobj.get("/Width", 0))
            height = int(xobj.get("/Height", 0))

            if width == 0 or height == 0:
                return

            # Extract and recompress the image
            raw_data = xobj.read_raw_bytes()

            # Try to create image from raw data
            try:
                img = Image.frombytes('RGB', (width, height), raw_data)
            except Exception:
                # If RGB fails, try other modes
                try:
                    img = Image.frombytes('L', (width, height), raw_data)
                except Exception:
                    return

            # Compress to JPEG
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            buffer.seek(0)

            # Replace with compressed version
            xobjects[key] = pdf.make_stream(
                buffer.read(),
                {
                    pikepdf.Name.Type: pikepdf.Name.XObject,
                    pikepdf.Name.Subtype: pikepdf.Name.Image,
                    pikepdf.Name.Width: width,
                    pikepdf.Name.Height: height,
                    pikepdf.Name.ColorSpace: pikepdf.Name.DeviceRGB,
                    pikepdf.Name.BitsPerComponent: 8,
                    pikepdf.Name.Filter: pikepdf.Name.DCTDecode,
                }
            )
        except Exception as e:
            logger.debug("image_recompression_skipped", reason=str(e))

    def _remove_metadata(self, pdf: pikepdf.Pdf) -> None:
        """Remove metadata from PDF."""
        try:
            # Clear document info
            with pdf.open_metadata() as meta:
                for key in list(meta.keys()):
                    del meta[key]

            # Clear XMP metadata
            if "/Metadata" in pdf.Root:
                del pdf.Root["/Metadata"]

            logger.debug("metadata_removed")
        except Exception as e:
            logger.warning("metadata_removal_warning", error=str(e))


pdf_compressor_service = PDFCompressorService()
