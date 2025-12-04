# app/services/pdf_compressor.py
import pikepdf
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image
from io import BytesIO
import structlog
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

from app.utils.exceptions import ProcessingException, InvalidPDFException

logger = structlog.get_logger()

# Thread pool for parallel image processing
_executor = ThreadPoolExecutor(max_workers=4)


class PDFCompressorService:
    """Service to compress PDF files with optimized performance."""

    def __init__(self):
        self._processed_images: Dict[str, bytes] = {}  # Cache for duplicate images
        self._max_image_dimension = 2000  # Max dimension for downscaling large images

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
        image_quality: int = 75,
    ) -> Tuple[int, int, int]:
        """
        Compress a PDF file with optimized performance.

        Args:
            input_path: Input PDF path
            output_path: Output PDF path
            image_quality: JPEG quality (10-100). Lower = more compression

        Returns:
            Tuple of (original_size, compressed_size, pages_count)
        """
        try:
            self._validate_pdf(input_path)
            original_size = input_path.stat().st_size
            self._processed_images.clear()  # Clear cache for new file

            # Validate and clamp quality
            image_quality = max(10, min(100, image_quality))

            logger.info(
                "compressing_pdf",
                image_quality=image_quality,
                original_size=original_size
            )

            # Run compression in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            pages_count = await loop.run_in_executor(
                _executor,
                self._compress_sync,
                input_path,
                output_path,
                image_quality
            )

            compressed_size = output_path.stat().st_size

            logger.info(
                "compression_complete",
                original_size=original_size,
                compressed_size=compressed_size,
                ratio=round((1 - compressed_size / original_size) * 100, 2),
                pages=pages_count
            )

            return original_size, compressed_size, pages_count

        except InvalidPDFException:
            raise
        except Exception as e:
            logger.error("compression_failed", error=str(e))
            raise ProcessingException(f"PDF compression failed: {str(e)}")

    def _compress_sync(
        self,
        input_path: Path,
        output_path: Path,
        image_quality: int
    ) -> int:
        """Synchronous compression for thread pool execution."""
        with pikepdf.open(input_path) as pdf:
            pages_count = len(pdf.pages)

            # Collect all unique images first
            all_images = self._collect_all_images(pdf)

            # Process images in batches for better performance
            if all_images:
                self._process_images_batch(pdf, all_images, image_quality)

            # Save with compression options
            pdf.save(
                output_path,
                linearize=True,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=True,
            )

        return pages_count

    def _collect_all_images(self, pdf: pikepdf.Pdf) -> List[Dict[str, Any]]:
        """Collect all images from PDF for batch processing."""
        images = []
        seen_objgens = set()

        for page_num, page in enumerate(pdf.pages):
            try:
                if "/Resources" not in page:
                    continue
                resources = page["/Resources"]
                if "/XObject" not in resources:
                    continue

                xobjects = resources["/XObject"]
                for key in list(xobjects.keys()):
                    try:
                        xobj = xobjects[key]
                        if not hasattr(xobj, "keys"):
                            continue

                        # Skip if already processed (same object)
                        objgen = (xobj.objgen if hasattr(xobj, 'objgen') else None)
                        if objgen and objgen in seen_objgens:
                            continue
                        if objgen:
                            seen_objgens.add(objgen)

                        if xobj.get("/Subtype") == pikepdf.Name.Image:
                            images.append({
                                'page': page,
                                'xobjects': xobjects,
                                'key': key,
                                'xobj': xobj,
                            })
                    except Exception:
                        continue
            except Exception:
                continue

        return images

    def _process_images_batch(
        self,
        pdf: pikepdf.Pdf,
        images: List[Dict[str, Any]],
        quality: int
    ) -> None:
        """Process images in batch for better performance."""
        for img_info in images:
            try:
                self._compress_single_image(
                    pdf,
                    img_info['xobjects'],
                    img_info['key'],
                    img_info['xobj'],
                    quality
                )
            except Exception as e:
                logger.debug("image_batch_skip", error=str(e))
                continue

    def _compress_images(self, pdf: pikepdf.Pdf, quality: int) -> None:
        """Compress images within the PDF."""
        for page in pdf.pages:
            try:
                self._process_page_images(page, pdf, quality)
            except Exception as e:
                logger.warning("image_compression_warning", error=str(e))
                continue

    def _process_page_images(
        self,
        page: pikepdf.Page,
        pdf: pikepdf.Pdf,
        quality: int
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
                    self._compress_single_image(pdf, xobjects, key, xobj, quality)
            except Exception:
                continue

    def _compress_single_image(
        self,
        pdf: pikepdf.Pdf,
        xobjects,
        key: str,
        xobj,
        quality: int
    ) -> None:
        """Compress a single image object with optimizations."""
        try:
            width = int(xobj.get("/Width", 0))
            height = int(xobj.get("/Height", 0))

            if width == 0 or height == 0:
                return

            # Skip very small images (icons, etc.)
            if width < 50 or height < 50:
                return

            # Get original data for size comparison and caching
            try:
                original_data = xobj.read_raw_bytes()
                original_size = len(original_data)
            except Exception:
                return

            # Skip if already small enough (< 10KB)
            if original_size < 10240:
                return

            # Check cache using hash of original data
            data_hash = hashlib.md5(original_data[:1024]).hexdigest()  # Hash first 1KB for speed
            cache_key = f"{data_hash}_{quality}"

            if cache_key in self._processed_images:
                compressed_data, new_width, new_height, color_space = self._processed_images[cache_key]
                if len(compressed_data) < original_size:
                    xobjects[key] = pdf.make_stream(
                        compressed_data,
                        {
                            pikepdf.Name.Type: pikepdf.Name.XObject,
                            pikepdf.Name.Subtype: pikepdf.Name.Image,
                            pikepdf.Name.Width: new_width,
                            pikepdf.Name.Height: new_height,
                            pikepdf.Name.ColorSpace: color_space,
                            pikepdf.Name.BitsPerComponent: 8,
                            pikepdf.Name.Filter: pikepdf.Name.DCTDecode,
                        }
                    )
                return

            # Extract image
            pil_image = self._extract_image(xobj)
            if pil_image is None:
                return

            # Downscale very large images for faster processing
            new_width, new_height = width, height
            if width > self._max_image_dimension or height > self._max_image_dimension:
                ratio = min(self._max_image_dimension / width, self._max_image_dimension / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to RGB if needed for JPEG
            if pil_image.mode == "RGBA":
                background = Image.new("RGB", pil_image.size, (255, 255, 255))
                background.paste(pil_image, mask=pil_image.split()[3])
                pil_image = background
            elif pil_image.mode not in ["RGB", "L"]:
                pil_image = pil_image.convert("RGB")

            # Compress to JPEG
            buffer = BytesIO()
            if pil_image.mode == "L":
                pil_image.save(buffer, format='JPEG', quality=quality, optimize=True)
                color_space = pikepdf.Name.DeviceGray
            else:
                pil_image.save(buffer, format='JPEG', quality=quality, optimize=True)
                color_space = pikepdf.Name.DeviceRGB

            buffer.seek(0)
            compressed_data = buffer.read()

            # Cache the result
            self._processed_images[cache_key] = (compressed_data, new_width, new_height, color_space)

            # Only replace if compressed version is smaller
            if len(compressed_data) < original_size:
                xobjects[key] = pdf.make_stream(
                    compressed_data,
                    {
                        pikepdf.Name.Type: pikepdf.Name.XObject,
                        pikepdf.Name.Subtype: pikepdf.Name.Image,
                        pikepdf.Name.Width: new_width,
                        pikepdf.Name.Height: new_height,
                        pikepdf.Name.ColorSpace: color_space,
                        pikepdf.Name.BitsPerComponent: 8,
                        pikepdf.Name.Filter: pikepdf.Name.DCTDecode,
                    }
                )
        except Exception as e:
            logger.debug("image_recompression_skipped", reason=str(e))

    def _extract_image(self, xobj) -> Optional[Image.Image]:
        """Extract image from PDF XObject."""
        try:
            width = int(xobj.get("/Width", 0))
            height = int(xobj.get("/Height", 0))

            if width == 0 or height == 0:
                return None

            # Get the filter type
            filter_type = xobj.get("/Filter")

            # Handle DCTDecode (JPEG) images
            if filter_type == pikepdf.Name.DCTDecode:
                raw_data = xobj.read_raw_bytes()
                return Image.open(BytesIO(raw_data))

            # Handle FlateDecode images
            if filter_type == pikepdf.Name.FlateDecode or filter_type is None:
                raw_data = xobj.read_bytes()  # Decompress
                color_space = xobj.get("/ColorSpace")
                bits = int(xobj.get("/BitsPerComponent", 8))

                if color_space == pikepdf.Name.DeviceRGB:
                    if len(raw_data) == width * height * 3:
                        return Image.frombytes('RGB', (width, height), raw_data)
                elif color_space == pikepdf.Name.DeviceGray:
                    if len(raw_data) == width * height:
                        return Image.frombytes('L', (width, height), raw_data)
                elif color_space == pikepdf.Name.DeviceCMYK:
                    if len(raw_data) == width * height * 4:
                        img = Image.frombytes('CMYK', (width, height), raw_data)
                        return img.convert('RGB')

                # Try RGB as fallback
                try:
                    return Image.frombytes('RGB', (width, height), raw_data)
                except Exception:
                    try:
                        return Image.frombytes('L', (width, height), raw_data)
                    except Exception:
                        return None

            # Handle JPXDecode (JPEG2000)
            if filter_type == pikepdf.Name.JPXDecode:
                raw_data = xobj.read_raw_bytes()
                return Image.open(BytesIO(raw_data))

            return None
        except Exception as e:
            logger.debug("image_extraction_failed", error=str(e))
            return None

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
