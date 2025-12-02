# tests/test_endpoints.py
import pytest
from io import BytesIO


def test_health_check(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_images_to_pdf(client, sample_image):
    """Test image to PDF conversion."""
    files = [
        ("files", ("image1.jpg", BytesIO(sample_image), "image/jpeg")),
        ("files", ("image2.jpg", BytesIO(sample_image), "image/jpeg")),
    ]

    response = client.post(
        "/api/v1/images-to-pdf",
        files=files,
        data={"page_size": "A4", "orientation": "portrait"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "X-Pages-Count" in response.headers


def test_merge_pdfs(client, sample_pdf):
    """Test PDF merging."""
    files = [
        ("files", ("doc1.pdf", BytesIO(sample_pdf), "application/pdf")),
        ("files", ("doc2.pdf", BytesIO(sample_pdf), "application/pdf")),
    ]

    response = client.post(
        "/api/v1/merge-pdfs",
        files=files,
        data={"output_filename": "merged.pdf"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "X-Files-Merged" in response.headers


def test_compress_pdf(client, sample_pdf):
    """Test PDF compression."""
    response = client.post(
        "/api/v1/compress-pdf",
        files=[("file", ("doc.pdf", BytesIO(sample_pdf), "application/pdf"))],
        data={"level": "medium"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "X-Compression-Ratio" in response.headers


def test_invalid_file_type(client):
    """Test invalid file type handling."""
    response = client.post(
        "/api/v1/images-to-pdf",
        files=[("files", ("test.txt", b"text content", "text/plain"))]
    )

    assert response.status_code == 415
