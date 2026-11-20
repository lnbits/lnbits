import pytest
from pydantic import ValidationError

from lnbits.core.models.extensions import (
    CreateExtension,
    InstallableExtension,
    Manifest,
)
from tests.helpers import make_installable_extension


@pytest.mark.parametrize(
    "ext_id",
    ["", ".", "..", "../data", "/outside-extension-root", "a/b", "a\\b", "a\n"],
)
def test_extension_ids_are_rejected_before_installation(ext_id):
    with pytest.raises(ValidationError):
        CreateExtension(
            ext_id=ext_id,
            archive="https://example.com/ext.zip",
            source_repo="manifest",
            version="1.0.0",
        )
    with pytest.raises(ValidationError):
        InstallableExtension(id=ext_id, name="Extension", version="1.0.0")
    with pytest.raises(ValidationError):
        Manifest.model_validate(
            {
                "extensions": [
                    {
                        "id": ext_id,
                        "name": "Extension",
                        "version": "1.0.0",
                        "archive": "https://example.com/ext.zip",
                        "hash": "",
                    }
                ]
            }
        )
    with pytest.raises(ValidationError):
        Manifest.model_validate(
            {
                "repos": [
                    {"id": ext_id, "organisation": "lnbits", "repository": "extension"}
                ]
            }
        )


@pytest.mark.parametrize("ext_id", ["tips", "extension_name", "Extension-123"])
def test_extension_ids_preserve_supported_names(ext_id):
    assert (
        InstallableExtension(id=ext_id, name="Extension", version="1.0.0").id == ext_id
    )


@pytest.mark.parametrize(
    "path_name", ["zip_path", "ext_dir", "wasm_ext_dir", "ext_upgrade_dir"]
)
def test_extension_paths_revalidate_mutated_ids(tmp_path, settings, path_name):
    settings.lnbits_data_folder = str(tmp_path / "data")
    ext = make_installable_extension("valid")
    ext.id = str(tmp_path / "outside")
    with pytest.raises(ValueError, match="Invalid extension id"):
        getattr(ext, path_name)
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "cleanup", ["clean_extension_files", "clean_wasm_extension_files"]
)
def test_extension_cleanup_cannot_delete_outside_extension_roots(
    tmp_path, settings, cleanup
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep")
    ext = make_installable_extension("valid")
    ext.id = str(outside)
    with pytest.raises(ValueError, match="Invalid extension id"):
        getattr(ext, cleanup)()
    assert marker.read_text() == "keep"
