# app/services/image_to_pdf.py
import img2pdf
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Optional
from io import BytesIO
import structlog

from app.utils.exceptions import ProcessingException

logger = structlog.get_logger()


class ImageToPDFService:
    """Service to convert images to PDF."""

    # Page sizes in points (72 points = 1 inch)
    PAGE_SIZES = {
        "A4": (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297)),
        "A3": (img2pdf.mm_to_pt(297), img2pdf.mm_to_pt(420)),
        "Letter": (img2pdf.in_to_pt(8.5), img2pdf.in_to_pt(11)),
        "Legal": (img2pdf.in_to_pt(8.5), img2pdf.in_to_pt(14)),
    }

    def __init__(self):
        pass

    def _preprocess_image(self, image_path: Path) -> bytes:
        """
        Preprocess image for PDF conversion.
        Handles RGBA, palette images, and rotation.
        """
        try:
            with Image.open(image_path) as img:
                # Handle EXIF rotation
                img = self._apply_exif_rotation(img)

                # Convert RGBA to RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()
                                     [-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save to bytes
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=95)
                buffer.seek(0)
                return buffer.read()

        except Exception as e:
            logger.error("image_preprocessing_failed",
                         path=str(image_path), error=str(e))
            raise ProcessingException(
                f"Failed to process image: {image_path.name}")

    def _apply_exif_rotation(self, image: Image.Image) -> Image.Image:
        """Apply EXIF rotation to image."""
        try:
            exif = image._getexif()
            if exif:
                orientation = exif.get(274)  # 274 is the orientation tag
                rotations = {
                    3: 180,
                    6: 270,
                    8: 90
                }
                if orientation in rotations:
                    image = image.rotate(rotations[orientation], expand=True)
        except (AttributeError, KeyError, TypeError):
            pass
        return image

    def _get_layout_fun(
        self,
        page_size: str,
        orientation: str,
        margin: int = 0
    ):
        """Get img2pdf layout function."""
        if page_size not in self.PAGE_SIZES:
            page_size = "A4"

        width, height = self.PAGE_SIZES[page_size]

        if orientation.lower() == "landscape":
            width, height = height, width

        # Apply margin
        margin_pt = img2pdf.mm_to_pt(margin)

        layout_fun = img2pdf.get_layout_fun(
            pagesize=(width, height),
            fit=img2pdf.FitMode.into,
            auto_orient=True
        )

        return layout_fun

    async def convert(
        self,
        image_paths: List[Path],
        output_path: Path,
        page_size: str = "A4",
        orientation: str = "portrait",
        margin: int = 0
    ) -> Tuple[int, int]:
        """
        Convert multiple images to a single PDF.

        Returns:
            Tuple of (output_size, pages_count)
        """
        try:
            # Preprocess all images
            processed_images = []
            for path in image_paths:
                img_bytes = self._preprocess_image(path)
                processed_images.append(img_bytes)

            logger.info(
                "converting_images",
                count=len(processed_images),
                page_size=page_size,
                orientation=orientation
            )

            # Get layout function
            layout_fun = self._get_layout_fun(page_size, orientation, margin)

            # Convert to PDF
            pdf_bytes = img2pdf.convert(
                processed_images,
                layout_fun=layout_fun
            )

            # Write output
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)

            output_size = output_path.stat().st_size
            pages_count = len(image_paths)

            logger.info(
                "conversion_complete",
                output_size=output_size,
                pages=pages_count
            )

            return output_size, pages_count

        except Exception as e:
            logger.error("conversion_failed", error=str(e))
            raise ProcessingException(
                f"Image to PDF conversion failed: {str(e)}")


image_to_pdf_service = ImageToPDFService()
