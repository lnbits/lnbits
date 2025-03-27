from pathlib import Path

import pytest

from lnbits.helpers import safe_upload_file_path
from lnbits.settings import settings


@pytest.mark.parametrize(
    "filepath",
    [
        "test.txt",
        "test/test.txt",
        "test/test/test.txt",
        "test/../test.txt",
        "*/test.txt",
        "test/**/test.txt",
        "./test.txt",
    ],
)
def test_safe_upload_file_path(filepath: str):
    safe_path = safe_upload_file_path(filepath)
    assert safe_path.name == "test.txt"

    # check if subdirectories got removed
    images_folder = Path(settings.lnbits_data_folder) / "images"
    assert images_folder.resolve() / "test.txt" == safe_path


@pytest.mark.parametrize(
    "filepath",
    [
        "../test.txt",
        "test/../../test.txt",
        "../../test.txt",
        "test/../../../test.txt",
        "../../../test.txt",
    ],
)
def test_unsafe_upload_file_path(filepath: str):
    with pytest.raises(ValueError):
        safe_upload_file_path(filepath)
