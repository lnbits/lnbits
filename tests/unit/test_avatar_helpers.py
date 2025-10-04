"""Tests for avatar upload helper functions."""
import io
from tempfile import NamedTemporaryFile

import pytest
from fastapi import HTTPException, UploadFile

from lnbits.core.views.auth_api import _save_avatar_file, _validate_avatar_file


def test_validate_avatar_file_jpeg():
    """Test JPEG file validation succeeds."""
    jpeg_data = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
        b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
        b"\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01"
        b"\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\t\xff\xc4\x00\x14\x10\x01\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01"
        b"\x01\x00\x00?\x00T\xff\xd9"
    )
    file = UploadFile(filename="test.jpg", file=io.BytesIO(jpeg_data))

    extension = _validate_avatar_file(file)
    assert extension == "jpg"


def test_validate_avatar_file_png():
    """Test PNG file validation succeeds."""
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    file = UploadFile(filename="test.png", file=io.BytesIO(png_data))

    extension = _validate_avatar_file(file)
    assert extension == "png"


def test_validate_avatar_file_no_filename():
    """Test validation fails when no filename provided."""
    file = UploadFile(filename=None, file=io.BytesIO(b"data"))

    with pytest.raises(HTTPException) as exc_info:
        _validate_avatar_file(file)

    assert exc_info.value.status_code == 400
    assert "No filename provided" in str(exc_info.value.detail)


def test_validate_avatar_file_invalid_type():
    """Test validation fails for unsupported file types."""
    text_data = b"This is not an image file"
    file = UploadFile(filename="test.txt", file=io.BytesIO(text_data))

    with pytest.raises(HTTPException) as exc_info:
        _validate_avatar_file(file)

    assert exc_info.value.status_code == 415
    # Error message can be either "Unable to determine file type" or "Unsupported file type"
    detail = str(exc_info.value.detail)
    assert "file type" in detail.lower()


def test_save_avatar_file_success():
    """Test file save succeeds for small files."""
    small_data = b"x" * 1000  # 1KB
    file = UploadFile(filename="test.txt", file=io.BytesIO(small_data))

    temp = _save_avatar_file(file, max_size_mb=1)

    assert temp.name is not None
    # Read back and verify
    with open(temp.name, 'rb') as f:
        assert f.read() == small_data
    # Cleanup
    import os
    os.unlink(temp.name)


def test_save_avatar_file_too_large():
    """Test file save fails when file exceeds size limit."""
    # Create 2MB of data
    large_data = b"x" * (2 * 1024 * 1024)
    file = UploadFile(filename="large.txt", file=io.BytesIO(large_data))

    with pytest.raises(HTTPException) as exc_info:
        _save_avatar_file(file, max_size_mb=1)

    assert exc_info.value.status_code == 413
    assert "File too large" in str(exc_info.value.detail)
    assert "MB" in str(exc_info.value.detail)


def test_save_avatar_file_exactly_at_limit():
    """Test file save succeeds at exact size limit."""
    # Exactly 1MB
    exact_size_data = b"x" * (1024 * 1024)
    file = UploadFile(filename="exact.txt", file=io.BytesIO(exact_size_data))

    temp = _save_avatar_file(file, max_size_mb=1)

    assert temp.name is not None
    # Cleanup
    import os
    os.unlink(temp.name)
