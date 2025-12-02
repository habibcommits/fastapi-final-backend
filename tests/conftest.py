# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from PIL import Image
from io import BytesIO
from pypdf import PdfWriter

from app.main import app


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def sample_image() -> bytes:
    """Generate a sample image for testing."""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer.read()


@pytest.fixture
def sample_pdf() -> bytes:
    """Generate a sample PDF for testing."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    buffer = BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return buffer.read()
