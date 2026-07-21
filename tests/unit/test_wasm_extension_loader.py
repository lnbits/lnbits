import json
import stat
import zipfile
from pathlib import Path
from typing import Any

import pytest

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.models.misc import WasmExtensionRegistry
from lnbits.core.wasm_ext.api.permissions import validate_wasm_extension_permissions
from lnbits.core.wasm_ext.wasm.config import parse_wasm_extension_config
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


def test_wasm_extension_config_ignores_unknown_fields():
    config = _wasm_config("demoext")
    config["unexpected"] = True

    parsed = parse_wasm_extension_config("demoext", config)

    assert not hasattr(parsed, "unexpected")


def test_wasm_extension_config_rejects_coerced_scalar_types():
    config = _wasm_config("demoext")
    config["wasm"] = {"module": 123}

    with pytest.raises(ValueError, match="str type expected"):
        parse_wasm_extension_config("demoext", config)


@pytest.mark.parametrize(
    "config_update",
    [
        {"wasm": {"module": "extension.wasm", "host_api": "custom.HostAPI"}},
        {
            "wasm": {
                "module": "extension.wasm",
                "resource_limits": {"max_response_bytes": 1024},
            }
        },
        {"build": {"source": "dev", "command": "npm run build"}},
    ],
)
def test_wasm_extension_config_ignores_removed_extension_control_fields(
    config_update: dict[str, Any],
):
    config = _wasm_config("demoext")
    config.update(config_update)

    parsed = parse_wasm_extension_config("demoext", config)

    assert parsed.wasm.module == "extension.wasm"
    assert not hasattr(parsed.wasm, "host_api")
    assert not hasattr(parsed.wasm, "resource_limits")
    assert not hasattr(parsed, "build")


def test_wasm_extension_config_accepts_supported_optional_sections():
    config = _wasm_config("demoext")
    config.update(
        {
            "tile": "static/icon.png",
            "min_lnbits_version": "1.0.0",
            "max_lnbits_version": "2.0.0",
            "wasm": {
                "module": "wasm/module.wasm",
                "wit": "wasm/lnbits-extension.wit",
                "world": "lnbits-extension",
                "exports": [
                    {"name": "render", "visibility": "public"},
                    {"name": "on_invoice_paid", "visibility": "event"},
                ],
            },
            "openapi": "wasm/openapi.json",
            "events": {"onInvoicePaid": "on_invoice_paid"},
            "ui": {"entrypoint": "static/index.html", "sandbox": True},
            "sdk": {"frontend_js": "static/lnbits-extension-sdk.js"},
            "ui_routes": [
                {
                    "path": "/demo/{item_id}",
                    "entrypoint": "static/index.html",
                    "auth": "user",
                    "path_params": {"item_id": "str"},
                }
            ],
            "api_routes": [
                {
                    "method": "GET",
                    "path": "/api/demo/{item_id}",
                    "export": "render",
                    "auth": "public",
                    "path_params": {"item_id": "str"},
                    "openapi": "#/routes/render",
                }
            ],
            "permissions": [{"id": "utils.basic", "description": "Basic utils"}],
        }
    )

    parsed = parse_wasm_extension_config("demoext", config)

    assert parsed.events.on_invoice_paid == "on_invoice_paid"
    assert parsed.wasm.world == "lnbits-extension"
    assert parsed.openapi == "wasm/openapi.json"
    assert parsed.api_routes[0].openapi == "#/routes/render"


def test_wasm_extension_config_ignores_unknown_permission_fields():
    config = _wasm_config("demoext")
    config["permissions"] = [
        {"id": "utils.basic", "label": "Basic utilities", "unknown": True}
    ]

    parsed = parse_wasm_extension_config("demoext", config)

    assert parsed.permissions == [ExtensionPermission(id="utils.basic")]


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


def test_wasm_archive_config_rejects_multiple_top_level_directories(
    tmp_path: Path,
    settings: Settings,
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    ext_info = make_installable_extension("demoext")
    with zipfile.ZipFile(ext_info.zip_path, "w") as archive:
        archive.writestr("safe/config.json", json.dumps(_wasm_config("demoext")))
        archive.writestr("safe/extension.wasm", b"\0asm")
        archive.writestr("other/readme.txt", "extra top-level directory")

    with pytest.raises(ValueError, match="one top-level directory"):
        ext_info.load_wasm_archive_config()


def test_wasm_archive_rejects_native_python_files(
    tmp_path: Path,
    settings: Settings,
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    settings.lnbits_extensions_path = str(tmp_path / "native")
    ext_info = make_installable_extension("demoext")
    _write_wasm_archive(
        ext_info,
        _wasm_config("demoext"),
        extra_files={"demoext-1.0.0/__init__.py": "raise RuntimeError('imported')"},
    )

    with pytest.raises(ValueError, match="native Python file"):
        ext_info.load_wasm_archive_config()

    assert not ext_info.ext_dir.exists()
    assert not ext_info.wasm_ext_dir.exists()


def test_wasm_archive_rejects_symlinks(
    tmp_path: Path,
    settings: Settings,
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    ext_info = make_installable_extension("demoext")
    root = "demoext-1.0.0"
    symlink_info = zipfile.ZipInfo(f"{root}/linked")
    symlink_info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(ext_info.zip_path, "w") as archive:
        archive.writestr(f"{root}/config.json", json.dumps(_wasm_config("demoext")))
        archive.writestr(f"{root}/extension.wasm", b"\0asm")
        archive.writestr(symlink_info, "extension.wasm")

    with pytest.raises(ValueError, match="symlink"):
        ext_info.load_wasm_archive_config()


def test_extract_wasm_archive_publishes_to_wasm_root_only(
    tmp_path: Path,
    settings: Settings,
):
    settings.lnbits_data_folder = str(tmp_path / "data")
    settings.lnbits_extensions_path = str(tmp_path / "native")
    ext_info = make_installable_extension("demoext")
    config = _wasm_config("demoext")
    _write_wasm_archive(ext_info, config)

    ext_info.extract_wasm_archive(ext_info.load_wasm_archive_config())

    assert (ext_info.wasm_ext_dir / "config.json").is_file()
    assert (ext_info.wasm_ext_dir / "extension.wasm").is_file()
    assert not ext_info.ext_dir.exists()


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
    settings.lnbits_data_folder = str(tmp_path / "data")
    ext_dir = Path(settings.lnbits_wasm_extensions_path) / ext_id
    ext_dir.mkdir(parents=True)
    (ext_dir / "extension.wasm").write_bytes(b"\0asm")
    config = {
        "name": "Demo",
        "short_description": "Demo extension",
        "version": "1.0.0",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
    }
    if config_id is not None:
        config["id"] = config_id
    (ext_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")


def _wasm_extension(ext_id: str, root_path: Path) -> WasmExtension:
    config = parse_wasm_extension_config(ext_id, _wasm_config(ext_id))
    return WasmExtension(
        id=ext_id,
        name=ext_id,
        version="1.0.0",
        root_path=root_path,
        module_path=root_path / "extension.wasm",
        wit_path=None,
        world="",
        exports=[],
        config=config,
    )


def _wasm_config(ext_id: str) -> dict[str, Any]:
    return {
        "id": ext_id,
        "name": ext_id,
        "short_description": "Demo extension",
        "version": "1.0.0",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
    }


def _write_wasm_archive(
    ext_info,
    config: dict[str, Any],
    *,
    extra_files: dict[str, str | bytes] | None = None,
) -> None:
    root = f"{ext_info.id}-1.0.0"
    with zipfile.ZipFile(ext_info.zip_path, "w") as archive:
        archive.writestr(f"{root}/config.json", json.dumps(config))
        archive.writestr(f"{root}/{config['wasm']['module']}", b"\0asm")
        for path, content in (extra_files or {}).items():
            archive.writestr(path, content)
