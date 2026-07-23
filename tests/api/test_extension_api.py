import json
import zipfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from lnbits.core.crud.db_versions import get_db_version, update_migration_version
from lnbits.core.crud.extensions import (
    create_installed_extension,
    delete_installed_extension,
    get_installed_extension,
    get_user_extension,
)
from lnbits.core.crud.users import get_account
from lnbits.core.crud.wallets import create_wallet
from lnbits.core.models import Account, CreateInvoice
from lnbits.core.models.extensions import (
    CreateExtension,
    CreateExtensionReview,
    ExplicitRelease,
    Extension,
    ExtensionConfig,
    ExtensionPermission,
    ExtensionPermissionsUpdate,
    ExtensionRelease,
    InstallableExtension,
    Manifest,
    PayToEnableInfo,
    ReleasePaymentInfo,
    UserExtensionInfo,
    WasmRuntimeLimitsUpdate,
    wasm_extension_icon_url,
)
from lnbits.core.models.users import AccountId
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.extension_api import (
    api_activate_extension,
    api_deactivate_extension,
    api_disable_extension,
    api_enable_extension,
    api_extension_details,
    api_get_user_extensions,
    api_get_wasm_runtime_limit_extensions,
    api_install_extension,
    api_uninstall_extension,
    api_update_extension_permissions,
    api_update_pay_to_enable,
    api_update_wasm_runtime_limits,
    create_extension_review,
    delete_extension_db,
    extensions,
    get_extension_release,
    get_extension_releases,
    get_extension_reviews,
    get_extension_reviews_tags,
    get_pay_to_enable_invoice,
    get_pay_to_install_invoice,
)
from tests.helpers import make_extension_release, make_installable_extension


class _MockHTTPResponse:
    def __init__(
        self,
        *,
        json_data=None,
        text: str = "",
        status_code: int = 200,
        is_error: bool = False,
    ):
        self._json_data = json_data
        self.text = text
        self.status_code = status_code
        self.is_error = is_error

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError(self.text or "request failed")


class _MockHTTPClient:
    def __init__(self, responses: dict[str, _MockHTTPResponse]):
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url: str):
        return self.responses[url]

    async def post(self, url: str, json=None):
        return self.responses[url]


@pytest.mark.anyio
async def test_extension_api_install_details_and_release_endpoints(mocker):
    ext_id = f"ext_{uuid4().hex[:8]}"
    release = make_extension_release(ext_id)
    create_data = CreateExtension(
        ext_id=ext_id,
        archive=release.archive,
        source_repo=release.source_repo,
        version=release.version,
    )

    mocker.patch.object(
        InstallableExtension,
        "get_extension_release",
        mocker.AsyncMock(return_value=release),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.install_extension",
        mocker.AsyncMock(return_value=Extension(code=ext_id, is_valid=True)),
    )
    activate_mock = mocker.patch(
        "lnbits.core.views.extension_api.activate_extension", mocker.AsyncMock()
    )

    installed = await api_install_extension(create_data)
    assert installed.code == ext_id
    activate_mock.assert_awaited_once()

    mocker.patch.object(
        InstallableExtension,
        "get_extension_releases",
        mocker.AsyncMock(return_value=[release]),
    )
    mocker.patch.object(
        ExtensionRelease,
        "fetch_release_details",
        mocker.AsyncMock(return_value={"description": "Extension details"}),
    )
    details = await api_extension_details(ext_id, release.details_link or "")
    assert details["description"] == "Extension details"
    assert details["icon"] == release.icon
    assert details["repo"] == release.repo

    installed_ext = make_installable_extension(
        ext_id,
        payments=[
            ReleasePaymentInfo(
                amount=55,
                pay_link=release.pay_link,
                payment_hash=f"payment_{uuid4().hex[:8]}",
            )
        ],
    )
    await create_installed_extension(installed_ext)
    releases = await get_extension_releases(ext_id)
    assert releases[0].paid_sats == 55

    config = ExtensionConfig(
        name=ext_id,
        short_description="Config",
        min_lnbits_version="0.1.0",
        max_lnbits_version=None,
    )
    mocker.patch.object(
        ExtensionConfig,
        "fetch_github_release_config",
        mocker.AsyncMock(return_value=config),
    )
    release_info = await get_extension_release("org", ext_id, "v1.0.0")
    assert release_info["is_version_compatible"] is True


@pytest.mark.anyio
async def test_explicit_wasm_release_loads_install_permissions(
    settings,
    mocker,
):
    ext_id = f"wasm_{uuid4().hex[:8]}"
    non_wasm_ext_id = f"python_{uuid4().hex[:8]}"
    manifest_url = "https://extensions.example/manifest.json"
    details_link = f"https://extensions.example/{ext_id}/config.json"
    explicit_release = ExplicitRelease(
        id=ext_id,
        name="Explicit WASM Extension",
        version="1.0.0",
        archive=f"https://extensions.example/{ext_id}.zip",
        hash="archive-hash",
        repo=f"https://github.com/example/{ext_id}",
        icon=None,
        short_description="Explicit WASM release",
        min_lnbits_version="0.1.0",
        max_lnbits_version=None,
        html_url=None,
        warning=None,
        info_notification=None,
        critical_notification=None,
        details_link=details_link,
        paid_features=None,
        pay_link=None,
        extension_type="wasm",
    )
    non_wasm_release = explicit_release.copy(
        update={
            "id": non_wasm_ext_id,
            "name": "Explicit Python Extension",
            "details_link": f"https://extensions.example/{non_wasm_ext_id}/config.json",
            "extension_type": None,
        }
    )
    config_permissions = [ExtensionPermission(id="wallet.list")]
    config = ExtensionConfig(
        name=ext_id,
        short_description="Explicit WASM release",
        min_lnbits_version="0.1.0",
        max_lnbits_version=None,
        extension_type="wasm",
        permissions=config_permissions,
    )

    async def fetch_manifest(url):
        if url == manifest_url:
            return Manifest(extensions=[explicit_release, non_wasm_release])
        return Manifest()

    mocker.patch.object(settings, "lnbits_extensions_manifests", [manifest_url])
    mocker.patch.object(
        settings,
        "lnbits_extensions_builder_manifest_url",
        "https://extensions.example/builder.json",
    )
    mocker.patch.object(
        InstallableExtension,
        "fetch_manifest",
        mocker.AsyncMock(side_effect=fetch_manifest),
    )
    fetch_config_mock = mocker.patch.object(
        ExtensionConfig,
        "fetch_release_config",
        mocker.AsyncMock(return_value=config),
    )

    releases = await InstallableExtension.get_extension_releases(ext_id)

    assert len(releases) == 1
    assert releases[0].extension_type == "wasm"
    assert releases[0].permissions == config_permissions
    fetch_config_mock.assert_awaited_once_with(details_link)

    fetch_config_mock.reset_mock()
    non_wasm_releases = await InstallableExtension.get_extension_releases(
        non_wasm_ext_id
    )
    assert len(non_wasm_releases) == 1
    assert non_wasm_releases[0].extension_type is None
    assert non_wasm_releases[0].permissions == []
    fetch_config_mock.assert_not_awaited()

    mocker.patch.object(
        InstallableExtension,
        "get_extension_releases",
        mocker.AsyncMock(return_value=releases),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.get_installed_extension",
        mocker.AsyncMock(return_value=None),
    )
    api_releases = await get_extension_releases(ext_id)
    assert api_releases[0].permissions == config_permissions


@pytest.mark.anyio
async def test_extension_api_installs_wasm_with_granted_permissions(
    tmp_path,
    settings,
    mocker,
):
    ext_id = f"wasm_{uuid4().hex[:8]}"
    release = make_extension_release(ext_id)
    granted_permissions = [
        ExtensionPermission(
            id="http.request",
            policies=[{"host": "https://api.example.com"}],
        )
    ]
    create_data = CreateExtension(
        ext_id=ext_id,
        archive=release.archive,
        source_repo=release.source_repo,
        version=release.version,
        permissions=granted_permissions,
    )
    original_data_folder = settings.lnbits_data_folder
    original_extensions_path = settings.lnbits_extensions_path
    register_wasm_routes_mock = mocker.patch(
        "lnbits.core.services.extensions.core_app_extra.register_new_wasm_ext_routes"
    )
    mocker.patch.object(
        InstallableExtension,
        "get_extension_release",
        mocker.AsyncMock(return_value=release),
    )
    mocker.patch.object(
        InstallableExtension,
        "download_archive",
        mocker.AsyncMock(),
    )

    try:
        settings.lnbits_data_folder = str(tmp_path / "data")
        settings.lnbits_extensions_path = str(tmp_path / "code")
        _write_wasm_extension_archive(ext_id, release.version, settings)

        installed = await api_install_extension(create_data)
        stored = await get_installed_extension(ext_id)
    finally:
        await delete_installed_extension(ext_id=ext_id)
        settings.lnbits_data_folder = original_data_folder
        settings.lnbits_extensions_path = original_extensions_path

    assert installed.code == ext_id
    assert installed.is_wasm is True
    assert stored is not None
    assert stored.permissions == [
        ExtensionPermission(
            id="http.request",
            description="Call example API.",
            policies=[{"host": "https://api.example.com"}],
        )
    ]
    register_wasm_routes_mock.assert_called_once_with(ext_id)


@pytest.mark.anyio
async def test_extension_api_wasm_runtime_limits_and_catalog_use_installed_metadata(
    tmp_path,
    settings,
    mocker,
):
    ext_id = f"wasm_{uuid4().hex[:8]}"
    py_ext_id = f"py_{uuid4().hex[:8]}"
    granted_permissions = [
        ExtensionPermission(
            id="http.request",
            description="Call example API.",
            policies=[{"host": "https://api.example.com"}],
        )
    ]
    original_extensions_path = settings.lnbits_extensions_path

    try:
        settings.lnbits_extensions_path = str(tmp_path)
        _write_installed_wasm_config(ext_id, tmp_path)
        await create_installed_extension(
            InstallableExtension(
                id=ext_id,
                name="WASM Demo",
                version="1.0.0",
                active=True,
                permissions=granted_permissions,
                wasm_runtime_limits={"wasm_runtime_max_execution_ms": 1234},
            )
        )
        await create_installed_extension(make_installable_extension(py_ext_id))

        runtime_extensions = await api_get_wasm_runtime_limit_extensions()
        wasm_info = next(info for info in runtime_extensions if info.id == ext_id)

        updated_info = await api_update_wasm_runtime_limits(
            ext_id,
            WasmRuntimeLimitsUpdate(
                limits={
                    "wasm_runtime_max_execution_ms": "2345",
                    "wasm_runtime_max_fuel": 0,
                }
            ),
        )
        stored = await get_installed_extension(ext_id)

        mocker.patch.object(
            InstallableExtension,
            "get_installable_extensions",
            mocker.AsyncMock(
                return_value=[
                    make_installable_extension(ext_id),
                    make_installable_extension(py_ext_id),
                ]
            ),
        )
        catalog = await extensions(AccountId(id=uuid4().hex))
    finally:
        await delete_installed_extension(ext_id=ext_id)
        await delete_installed_extension(ext_id=py_ext_id)
        settings.lnbits_extensions_path = original_extensions_path

    assert wasm_info.wasm_runtime_limits == {"wasm_runtime_max_execution_ms": 1234}
    assert py_ext_id not in {info.id for info in runtime_extensions}
    assert updated_info.wasm_runtime_limits == {
        "wasm_runtime_max_execution_ms": 2345,
        "wasm_runtime_max_fuel": 0,
    }
    assert stored is not None
    assert stored.wasm_runtime_limits == updated_info.wasm_runtime_limits

    catalog_item = next(item for item in catalog if item["id"] == ext_id)
    assert catalog_item["isWasm"] is True
    assert catalog_item["icon"] == wasm_extension_icon_url(ext_id)
    assert catalog_item["permissions"] == [
        dict(permission) for permission in granted_permissions
    ]


@pytest.mark.anyio
async def test_extension_api_admin_updates_wasm_extension_permission_limits(
    tmp_path,
    settings,
):
    ext_id = f"wasm_{uuid4().hex[:8]}"
    original_extensions_path = settings.lnbits_extensions_path
    manifest_permissions = [
        {
            "id": "ext.storage.append_public",
            "description": "Append public messages.",
            "policies": [
                {
                    "table": "messages",
                    "source_table": "conversations",
                    "source_id_field": "conversation_id",
                    "allowed_fields": ["body"],
                    "max_rows_per_source": 100,
                }
            ],
        }
    ]
    installed_permissions = [
        ExtensionPermission.parse_obj(permission) for permission in manifest_permissions
    ]
    updated_permissions = [
        ExtensionPermission(
            id="ext.storage.append_public",
            policies=[
                {
                    "table": "messages",
                    "source_table": "conversations",
                    "source_id_field": "conversation_id",
                    "allowed_fields": ["body"],
                    "max_rows_per_source": 1000,
                }
            ],
        )
    ]

    try:
        settings.lnbits_extensions_path = str(tmp_path)
        _write_installed_wasm_config(
            ext_id,
            tmp_path,
            permissions=manifest_permissions,
        )
        await create_installed_extension(
            InstallableExtension(
                id=ext_id,
                name="WASM Demo",
                version="1.0.0",
                active=True,
                permissions=installed_permissions,
            )
        )

        response = await api_update_extension_permissions(
            ext_id,
            ExtensionPermissionsUpdate(permissions=updated_permissions),
        )
        stored = await get_installed_extension(ext_id)
    finally:
        await delete_installed_extension(ext_id=ext_id)
        settings.lnbits_extensions_path = original_extensions_path

    assert response.extension_permissions == [
        ExtensionPermission(
            id="ext.storage.append_public",
            description="Append public messages.",
            policies=[
                {
                    "table": "messages",
                    "source_table": "conversations",
                    "source_id_field": "conversation_id",
                    "allowed_fields": ["body"],
                    "max_rows_per_source": 1000,
                }
            ],
        )
    ]
    assert stored is not None
    assert stored.permissions == response.extension_permissions


@pytest.mark.anyio
async def test_extension_api_pay_to_enable_and_catalog_views(mocker, admin_user):
    regular_user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    admin_account = await get_account(admin_user.id)
    assert admin_account is not None
    admin_wallet = await create_wallet(
        user_id=admin_account.id, wallet_name="extension sales"
    )

    ext_id = f"paid_{uuid4().hex[:8]}"
    await create_installed_extension(
        make_installable_extension(
            ext_id,
            pay_to_enable=PayToEnableInfo(
                required=True, amount=10, wallet=admin_wallet.id
            ),
        )
    )

    updated = await api_update_pay_to_enable(
        ext_id,
        PayToEnableInfo(required=True, amount=21, wallet=admin_wallet.id),
        account=admin_account,
    )
    assert updated.success is True
    stored_extension = await get_installed_extension(ext_id)
    assert stored_extension is not None
    assert stored_extension.meta is not None
    assert stored_extension.meta.pay_to_enable is not None
    assert stored_extension.meta.pay_to_enable.amount == 21

    enable_invoice = await create_wallet_invoice(
        admin_wallet.id, CreateInvoice(out=False, amount=21, memo="enable extension")
    )
    mocker.patch(
        "lnbits.core.views.extension_api.create_invoice",
        mocker.AsyncMock(return_value=enable_invoice),
    )
    invoice_response = await get_pay_to_enable_invoice(
        ext_id,
        PayToEnableInfo(amount=21),
        account_id=AccountId(id=regular_user.id),
    )
    assert invoice_response["payment_hash"] == enable_invoice.payment_hash

    user_ext = await get_user_extension(regular_user.id, ext_id)
    assert user_ext is not None
    assert user_ext.extra is not None
    assert user_ext.extra.payment_hash_to_enable == enable_invoice.payment_hash

    mocker.patch(
        "lnbits.core.views.extension_api.get_valid_extensions",
        mocker.AsyncMock(return_value=[Extension(code=ext_id, is_valid=True)]),
    )
    mocker.patch(
        "lnbits.core.views.extension_api.check_transaction_status",
        mocker.AsyncMock(return_value=SimpleNamespace(paid=True)),
    )

    enabled = await api_enable_extension(ext_id, AccountId(id=regular_user.id))
    assert enabled.success is True
    user_ext = await get_user_extension(regular_user.id, ext_id)
    assert user_ext is not None
    assert user_ext.active is True
    assert user_ext.extra == UserExtensionInfo(
        payment_hash_to_enable=enable_invoice.payment_hash,
        paid_to_enable=True,
    )

    disabled = await api_disable_extension(ext_id, AccountId(id=regular_user.id))
    assert disabled.success is True
    disabled_again = await api_disable_extension(ext_id, AccountId(id=regular_user.id))
    assert disabled_again.success is True
    assert "already disabled" in disabled_again.message

    mocker.patch(
        "lnbits.core.views.extension_api.get_valid_extensions",
        mocker.AsyncMock(
            return_value=[
                Extension(code=ext_id, is_valid=True, name="Paid Extension"),
                Extension(code="other", is_valid=True),
            ]
        ),
    )
    visible_extensions = await api_get_user_extensions(AccountId(id=regular_user.id))
    assert [ext.code for ext in visible_extensions] == [ext_id]

    catalog_entry = make_installable_extension(
        ext_id,
        pay_to_enable=PayToEnableInfo(required=True, amount=21, wallet=admin_wallet.id),
    )
    mocker.patch.object(
        InstallableExtension,
        "get_installable_extensions",
        mocker.AsyncMock(return_value=[catalog_entry]),
    )
    catalog = await extensions(AccountId(id=regular_user.id))
    catalog_item = next(item for item in catalog if item["id"] == ext_id)
    assert catalog_item["payToEnable"]["wallet"] is None


@pytest.mark.anyio
async def test_extension_api_activate_uninstall_install_invoice_and_cleanup(mocker):
    base_ext = f"base_{uuid4().hex[:8]}"
    dependent_ext = f"dependent_{uuid4().hex[:8]}"
    uninstall_ext = f"uninstall_{uuid4().hex[:8]}"
    db_ext = f"db_{uuid4().hex[:8]}"

    await create_installed_extension(make_installable_extension(base_ext))
    await create_installed_extension(
        make_installable_extension(dependent_ext, dependencies=[base_ext])
    )
    await create_installed_extension(make_installable_extension(uninstall_ext))

    mocker.patch(
        "lnbits.core.views.extension_api.get_valid_extensions",
        mocker.AsyncMock(
            return_value=[
                Extension(code=base_ext, is_valid=True, name="Base"),
                Extension(code=dependent_ext, is_valid=True, name="Dependent"),
                Extension(code=uninstall_ext, is_valid=True, name="Remove"),
            ]
        ),
    )

    with pytest.raises(HTTPException, match="depends on this one"):
        await api_uninstall_extension(base_ext)

    uninstall_mock = mocker.patch(
        "lnbits.core.views.extension_api.uninstall_extension", mocker.AsyncMock()
    )
    uninstalled = await api_uninstall_extension(uninstall_ext)
    assert uninstalled.success is True
    uninstall_mock.assert_awaited_once_with(uninstall_ext)

    mocker.patch(
        "lnbits.core.views.extension_api.get_valid_extension",
        mocker.AsyncMock(return_value=Extension(code=base_ext, is_valid=True)),
    )
    activate_mock = mocker.patch(
        "lnbits.core.views.extension_api.activate_extension", mocker.AsyncMock()
    )
    deactivate_mock = mocker.patch(
        "lnbits.core.views.extension_api.deactivate_extension", mocker.AsyncMock()
    )
    activated = await api_activate_extension(base_ext)
    assert activated.success is True
    deactivated = await api_deactivate_extension(base_ext)
    assert deactivated.success is True
    activate_mock.assert_awaited_once()
    deactivate_mock.assert_awaited_once()

    owner = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = owner.wallets[0]
    install_invoice = await create_wallet_invoice(
        wallet.id, CreateInvoice(out=False, amount=33, memo="install extension")
    )
    release = make_extension_release(base_ext, version="2.0.0")
    payment_info = ReleasePaymentInfo(
        amount=33,
        pay_link=release.pay_link,
        payment_hash=install_invoice.payment_hash,
        payment_request=install_invoice.bolt11,
    )
    mocker.patch.object(
        InstallableExtension,
        "get_extension_release",
        mocker.AsyncMock(return_value=release),
    )
    mocker.patch.object(
        ExtensionRelease,
        "fetch_release_payment_info",
        mocker.AsyncMock(return_value=payment_info),
    )
    invoice = await get_pay_to_install_invoice(
        base_ext,
        CreateExtension(
            ext_id=base_ext,
            archive=release.archive,
            source_repo=release.source_repo,
            version=release.version,
            cost_sats=33,
        ),
    )
    assert invoice.payment_hash == install_invoice.payment_hash

    await update_migration_version(None, db_ext, 1)
    drop_mock = mocker.patch(
        "lnbits.core.views.extension_api.drop_extension_db", mocker.AsyncMock()
    )
    deleted = await delete_extension_db(db_ext)
    assert deleted.success is True
    drop_mock.assert_awaited_once_with(ext_id=db_ext)
    assert await get_db_version(db_ext) is None


@pytest.mark.anyio
async def test_extension_api_review_endpoints(mocker):
    ext_id = f"review_{uuid4().hex[:8]}"
    reviews_base = "https://demo.lnbits.com/paidreviews/api/v1/AdFzLjzuKFLsdk4Bcnff6r"
    tags_url = f"{reviews_base}/tags"
    reviews_url = f"{reviews_base}/reviews/{ext_id}?offset=0&limit=5"
    create_review_url = f"{reviews_base}/reviews"
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/api/v1/extension/reviews/{ext_id}",
            "query_string": b"offset=0&limit=5",
            "headers": [],
        }
    )
    mock_client = _MockHTTPClient(
        {
            tags_url: _MockHTTPResponse(
                json_data=[{"tag": "good", "avg_rating": 900, "review_count": 3}]
            ),
            reviews_url: _MockHTTPResponse(
                json_data={
                    "data": [
                        {
                            "id": "1",
                            "name": "Alice",
                            "tag": "good",
                            "rating": 950,
                            "comment": "solid",
                        }
                    ],
                    "total": 1,
                }
            ),
            create_review_url: _MockHTTPResponse(
                json_data={
                    "payment_hash": f"hash_{uuid4().hex[:8]}",
                    "payment_request": "lnbc1review",
                }
            ),
        }
    )
    mocker.patch(
        "lnbits.core.views.extension_api.httpx.AsyncClient", return_value=mock_client
    )

    tags = await get_extension_reviews_tags()
    assert tags[0].tag == "good"

    reviews = await get_extension_reviews(ext_id, request)
    assert reviews.total == 1
    assert reviews.data[0].comment == "solid"

    payment_request = await create_extension_review(
        CreateExtensionReview(tag=ext_id, name="Alice", rating=900, comment="Great")
    )
    assert payment_request.payment_hash.startswith("hash_")


def _write_wasm_extension_archive(
    ext_id: str,
    version: str,
    settings,
    permissions: list[dict] | None = None,
) -> None:
    zip_path = Path(settings.lnbits_data_folder, "zips", f"{ext_id}.zip")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    config = _wasm_config(ext_id, permissions=permissions)
    root = f"{ext_id}-{version}"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(f"{root}/config.json", json.dumps(config))
        archive.writestr(f"{root}/{config['wasm']['module']}", b"\0asm")


def _write_installed_wasm_config(
    ext_id: str,
    extensions_path,
    permissions: list[dict] | None = None,
) -> None:
    config_dir = extensions_path / "extensions" / ext_id
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        json.dumps(_wasm_config(ext_id, permissions=permissions)),
        encoding="utf-8",
    )


def _wasm_config(ext_id: str, permissions: list[dict] | None = None) -> dict:
    return {
        "id": ext_id,
        "name": "WASM Demo",
        "short_description": "WASM extension",
        "version": "1.0.0",
        "extension_type": "wasm",
        "wasm": {"module": "extension.wasm"},
        "permissions": permissions
        or [
            {
                "id": "http.request",
                "description": "Call example API.",
                "policies": [{"host": "https://api.example.com"}],
            }
        ],
    }
