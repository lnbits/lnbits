import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.extensions import InstallableExtension, Manifest
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_get_installable_extensions_loads_wasm_manifests(
    settings: Settings, mocker: MockerFixture
):
    regular_manifest_url = "https://example.com/extensions.json"
    wasm_manifest_url = "https://example.com/wasm-extensions.json"
    settings.lnbits_extensions_manifests = [regular_manifest_url]
    settings.lnbits_wasm_extensions_manifests = [
        wasm_manifest_url,
        regular_manifest_url,
    ]
    fetch_manifest = mocker.patch.object(
        InstallableExtension,
        "fetch_manifest",
        mocker.AsyncMock(
            side_effect=[
                Manifest(),
                Manifest.parse_obj(
                    {
                        "extensions": [
                            {
                                "id": "tips",
                                "name": "Tips",
                                "version": "0.1.4",
                                "archive": "https://example.com/tips.zip",
                                "hash": "tips-hash",
                            }
                        ]
                    }
                ),
            ]
        ),
    )

    extensions = await InstallableExtension._get_installable_extensions()

    assert [extension.id for extension in extensions] == ["tips"]
    assert [call.args[0] for call in fetch_manifest.await_args_list] == [
        regular_manifest_url,
        wasm_manifest_url,
    ]
