from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from lnbits.core.crud.db_versions import get_db_version, update_migration_version
from lnbits.core.crud.extensions import (
    create_installed_extension,
    get_installed_extension,
    get_user_extension,
)
from lnbits.core.crud.users import get_account
from lnbits.core.crud.wallets import create_wallet
from lnbits.core.models import Account, CreateInvoice
from lnbits.core.models.extensions import (
    CreateExtension,
    CreateExtensionReview,
    Extension,
    ExtensionConfig,
    ExtensionMeta,
    ExtensionRelease,
    InstallableExtension,
    PayToEnableInfo,
    ReleasePaymentInfo,
    UserExtensionInfo,
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
    api_install_extension,
    api_uninstall_extension,
    api_update_pay_to_enable,
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


def _release(ext_id: str, version: str = "1.0.0") -> ExtensionRelease:
    return ExtensionRelease(
        name=ext_id,
        version=version,
        archive=f"https://example.com/{ext_id}.zip",
        source_repo="org/repo",
        hash=f"hash-{ext_id}",
        details_link=f"https://example.com/{ext_id}/details.json",
        repo=f"https://github.com/org/{ext_id}",
        icon=f"/{ext_id}/static/icon.png",
        pay_link=f"https://pay.example/{ext_id}",
    )


def _installable_extension(
    ext_id: str,
    *,
    active: bool = True,
    pay_to_enable: PayToEnableInfo | None = None,
    dependencies: list[str] | None = None,
    payments: list[ReleasePaymentInfo] | None = None,
) -> InstallableExtension:
    release = _release(ext_id)
    return InstallableExtension(
        id=ext_id,
        name=f"Extension {ext_id}",
        version=release.version,
        active=active,
        short_description="Demo extension",
        icon=release.icon,
        meta=ExtensionMeta(
            installed_release=release,
            pay_to_enable=pay_to_enable,
            dependencies=dependencies or [],
            payments=payments or [],
        ),
    )


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
    release = _release(ext_id)
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

    installed_ext = _installable_extension(
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
        _installable_extension(
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

    catalog_entry = _installable_extension(
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

    await create_installed_extension(_installable_extension(base_ext))
    await create_installed_extension(
        _installable_extension(dependent_ext, dependencies=[base_ext])
    )
    await create_installed_extension(_installable_extension(uninstall_ext))

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
    release = _release(base_ext, version="2.0.0")
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
