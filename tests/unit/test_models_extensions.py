import httpx
import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.core.models.extensions import (
    ExtensionConfig,
    ExtensionManifestType,
    ExtensionMeta,
    ExtensionRelease,
    InstallableExtension,
    Manifest,
    github_api_get,
)
from lnbits.settings import Settings


def _mock_json_response(mocker: MockerFixture, url: str, payload: dict):
    response = httpx.Response(
        200,
        json=payload,
        request=httpx.Request("GET", url),
    )
    client = mocker.AsyncMock()
    client.get.return_value = response
    client_context = mocker.MagicMock()
    client_context.__aenter__ = mocker.AsyncMock(return_value=client)
    client_context.__aexit__ = mocker.AsyncMock(return_value=None)
    client_factory = mocker.patch(
        "lnbits.core.models.extensions.httpx.AsyncClient",
        return_value=client_context,
    )
    return client_factory, client


def _extension_config_payload() -> dict:
    return {
        "name": "Test Extension",
        "short_description": "Test extension metadata",
        "min_lnbits_version": None,
        "max_lnbits_version": None,
    }


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
    assert extensions[0].meta
    assert extensions[0].meta.latest_release
    assert extensions[0].meta.latest_release.manifest_type == ExtensionManifestType.WASM
    assert [call.args[0] for call in fetch_manifest.await_args_list] == [
        regular_manifest_url,
        wasm_manifest_url,
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "release_order",
    [
        ("old", "latest"),
        ("latest", "old"),
        ("future", "latest"),
        ("latest", "future"),
        ("old", "latest", "same_version"),
        ("paid", "latest"),
        ("latest", "paid"),
    ],
)
async def test_installable_extension_display_uses_selected_release(
    settings: Settings, mocker: MockerFixture, release_order: tuple[str, ...]
):
    manifest_url = "https://example.com/extensions.json"
    settings.version = "1.6.2"
    settings.lnbits_extensions_manifests = [manifest_url]
    settings.lnbits_wasm_extensions_manifests = []
    releases = {
        "old": {"version": "0.3.1", "max_lnbits_version": "0.11.0"},
        "latest": {"version": "1.3.2"},
        "future": {"version": "2.0.0", "min_lnbits_version": "99.0.0"},
        "same_version": {"version": "1.3.2"},
        "paid": {"version": "1.0.0", "pay_link": "https://example.com/pay"},
    }
    manifest = Manifest.parse_obj(
        {
            "featured": ["lnurlp"],
            "categories": {"tools": ["lnurlp"]},
            "extensions": [
                {
                    "id": "lnurlp",
                    "name": f"{key} name",
                    "short_description": f"{key} description",
                    "icon": f"https://example.com/{key}.png",
                    "archive": f"https://example.com/{key}.zip",
                    "hash": f"{key}-hash",
                    **releases[key],
                }
                for key in release_order
            ],
        }
    )
    mocker.patch.object(
        InstallableExtension, "fetch_manifest", mocker.AsyncMock(return_value=manifest)
    )

    extensions = await InstallableExtension._get_installable_extensions()

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.meta
    assert extension.meta.latest_release
    assert extension.meta.latest_release.version == "1.3.2"
    assert extension.meta.latest_release.archive == "https://example.com/latest.zip"
    assert extension.name == "latest name"
    assert extension.short_description == "latest description"
    assert extension.icon == "https://example.com/latest.png"
    assert extension.meta.featured is True
    assert extension.meta.categories == ["tools"]
    assert extension.meta.has_free_release is True
    assert bool(extension.meta.has_paid_release) == ("paid" in release_order)


@pytest.mark.anyio
@pytest.mark.parametrize("first_source", ["explicit", "github"])
@pytest.mark.parametrize("latest_source", ["explicit", "github"])
async def test_installable_extension_display_merges_manifest_sources(
    settings: Settings,
    mocker: MockerFixture,
    first_source: str,
    latest_source: str,
):
    second_source = "github" if first_source == "explicit" else "explicit"
    manifest_urls = {
        source: f"https://example.com/{source}.json"
        for source in [first_source, second_source]
    }
    settings.lnbits_extensions_manifests = list(manifest_urls.values())
    settings.lnbits_wasm_extensions_manifests = []
    versions = {
        source: "1.3.2" if source == latest_source else "1.0.0"
        for source in manifest_urls
    }
    manifests = {
        manifest_urls["explicit"]: Manifest.parse_obj(
            {
                "extensions": [
                    {
                        "id": "lnurlp",
                        "name": "explicit name",
                        "short_description": "explicit description",
                        "icon": "https://example.com/explicit.png",
                        "version": versions["explicit"],
                        "archive": "https://example.com/explicit.zip",
                        "hash": "explicit-hash",
                    }
                ]
            }
        ),
        manifest_urls["github"]: Manifest.parse_obj(
            {
                "repos": [
                    {"id": "lnurlp", "organisation": "example", "repository": "lnurlp"}
                ]
            }
        ),
    }
    mocker.patch.object(
        InstallableExtension,
        "fetch_manifest",
        mocker.AsyncMock(side_effect=lambda url: manifests[url]),
    )
    mocker.patch.object(
        InstallableExtension,
        "from_github_release",
        mocker.AsyncMock(
            return_value=InstallableExtension(
                id="lnurlp",
                name="github name",
                short_description="github description",
                icon="https://example.com/github.png",
                version=versions["github"],
                meta=ExtensionMeta(
                    latest_release=ExtensionRelease(
                        name="GitHub release title",
                        description="Release notes, not the extension description",
                        version=versions["github"],
                        archive="https://example.com/github.zip",
                        source_repo="example/lnurlp",
                        is_github_release=True,
                    )
                ),
            )
        ),
    )

    extensions = await InstallableExtension._get_installable_extensions()

    assert len(extensions) == 1
    extension = extensions[0]
    assert extension.meta
    assert extension.meta.latest_release
    assert extension.meta.latest_release.version == "1.3.2"
    assert extension.name == f"{latest_source} name"
    assert extension.short_description == f"{latest_source} description"
    assert extension.icon == f"https://example.com/{latest_source}.png"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://api.github.com/repos/example/extension",
        "https://raw.githubusercontent.com/example/extension/main/config.json",
    ],
)
async def test_release_config_sends_token_only_to_trusted_github_origins(
    settings: Settings,
    mocker: MockerFixture,
    url: str,
):
    settings.lnbits_ext_github_token = "github-secret"
    client_factory, client = _mock_json_response(
        mocker, url, _extension_config_payload()
    )

    await ExtensionConfig.fetch_release_config(url)

    assert client_factory.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer github-secret"
    )
    assert client_factory.call_args.kwargs["follow_redirects"] is False
    client.get.assert_awaited_once_with(url)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://extensions.example/config.json",
        "https://api.github.com.evil.example/config.json",
        "https://api.github.com./config.json",
        "https://raw.githubusercontent.com.evil.example/config.json",
        "http://api.github.com/config.json",
        "https://api.github.com:444/config.json",
    ],
)
async def test_release_config_does_not_send_token_to_untrusted_origins(
    settings: Settings,
    mocker: MockerFixture,
    url: str,
):
    settings.lnbits_ext_github_token = "github-secret"
    client_factory, client = _mock_json_response(
        mocker, url, _extension_config_payload()
    )

    await ExtensionConfig.fetch_release_config(url)

    assert "Authorization" not in client_factory.call_args.kwargs["headers"]
    assert client_factory.call_args.kwargs["follow_redirects"] is False
    client.get.assert_awaited_once_with(url)


@pytest.mark.anyio
async def test_manifest_does_not_send_token_to_untrusted_origin(
    settings: Settings,
    mocker: MockerFixture,
):
    url = "https://extensions.example/manifest.json"
    settings.lnbits_ext_github_token = "github-secret"
    client_factory, client = _mock_json_response(mocker, url, {})

    await InstallableExtension.fetch_manifest(url)

    assert "Authorization" not in client_factory.call_args.kwargs["headers"]
    assert client_factory.call_args.kwargs["follow_redirects"] is False
    client.get.assert_awaited_once_with(url)


@pytest.mark.anyio
async def test_release_config_rejects_url_credentials(
    settings: Settings,
    mocker: MockerFixture,
):
    settings.lnbits_ext_github_token = "github-secret"
    client_factory = mocker.patch("lnbits.core.models.extensions.httpx.AsyncClient")

    with pytest.raises(ValueError, match="must not contain credentials"):
        await ExtensionConfig.fetch_release_config(
            "https://github-secret@api.github.com/config.json"
        )

    client_factory.assert_not_called()


@pytest.mark.anyio
async def test_github_api_get_rejects_untrusted_origin(
    settings: Settings,
    mocker: MockerFixture,
):
    settings.lnbits_ext_github_token = "github-secret"
    client_factory = mocker.patch("lnbits.core.models.extensions.httpx.AsyncClient")

    with pytest.raises(ValueError, match="untrusted origin"):
        await github_api_get("https://api.github.com.evil.example/", "Cannot fetch")

    client_factory.assert_not_called()
