import json
from pathlib import Path

import pytest

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.misc import WasmExtensionRegistry
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.wasm.loader import WasmExtension, load_wasm_extension
from lnbits.settings import Settings
from tests.helpers import make_installable_extension


def test_load_wasm_extension_rejects_missing_config_id(
    tmp_path: Path, settings: Settings
):
    ext_id = "demoext"
    _write_wasm_extension(settings, tmp_path, ext_id, config_id=None)

    with pytest.raises(ValueError, match="config must define id"):
        load_wasm_extension(ext_id)


def test_load_wasm_extension_rejects_mismatched_config_id(
    tmp_path: Path, settings: Settings
):
    ext_id = "demoext"
    _write_wasm_extension(settings, tmp_path, ext_id, config_id="otherext")

    with pytest.raises(ValueError, match="id mismatch"):
        load_wasm_extension(ext_id)


def test_load_wasm_extension_uses_canonical_extension_id(
    tmp_path: Path, settings: Settings
):
    ext_id = "demoext"
    _write_wasm_extension(settings, tmp_path, ext_id, config_id=ext_id)

    extension = load_wasm_extension(ext_id)

    assert extension.id == ext_id


def test_install_time_permission_validation_rejects_config_id_mismatch():
    ext_info = make_installable_extension("demoext")
    extension_config = {
        "id": "otherext",
        "extension_type": "wasm",
        "permissions": [{"id": "utils.basic"}],
    }

    with pytest.raises(ValueError, match="id mismatch"):
        validate_wasm_extension_permissions(
            ext_info,
            [ExtensionPermission(id="utils.basic")],
            extension_config,
        )


def test_wasm_extension_registry_rejects_same_id_from_different_root(tmp_path: Path):
    registry = WasmExtensionRegistry()
    first = _wasm_extension("demoext", tmp_path / "one")
    second_same_root = _wasm_extension("demoext", tmp_path / "one")
    second_different_root = _wasm_extension("demoext", tmp_path / "two")

    registry.register(first)
    registry.register(second_same_root)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(second_different_root)


def _write_wasm_extension(
    settings: Settings,
    tmp_path: Path,
    ext_id: str,
    *,
    config_id: str | None,
) -> None:
    settings.lnbits_extensions_path = str(tmp_path)
    ext_dir = tmp_path / "extensions" / ext_id
    ext_dir.mkdir(parents=True)
    (ext_dir / "extension.wasm").write_bytes(b"\0asm")
    config = {
        "name": "Demo",
        "version": "1.0.0",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
    }
    if config_id is not None:
        config["id"] = config_id
    (ext_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")


def _wasm_extension(ext_id: str, root_path: Path) -> WasmExtension:
    return WasmExtension(
        id=ext_id,
        name=ext_id,
        version="1.0.0",
        root_path=root_path,
        module_path=root_path / "extension.wasm",
        wit_path=None,
        world="",
        host_api="",
        exports=[],
        config={"id": ext_id, "extension_type": "wasm"},
    )
