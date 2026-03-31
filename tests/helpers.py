import random
import string
from io import BytesIO

from bolt11.types import MilliSatoshi
from fastapi import UploadFile
from httpx import AsyncClient
from lnurl import LnurlPayResponse
from lnurl.types import CallbackUrl, LnurlPayMetadata
from PIL import Image
from pydantic import BaseModel, parse_obj_as
from starlette.datastructures import Headers

from lnbits.core.models.extensions import (
    ExtensionMeta,
    ExtensionRelease,
    InstallableExtension,
    PayToEnableInfo,
    ReleasePaymentInfo,
)
from lnbits.core.models.extensions_builder import (
    ActionFields,
    ClientDataFields,
    DataField,
    DataFields,
    ExtensionData,
    OwnerDataFields,
    PublicPageFields,
    SettingsFields,
)
from lnbits.wallets import get_funding_source, set_funding_source


class DbTestModel(BaseModel):
    id: int
    name: str
    value: str | None = None


class DbTestModel2(BaseModel):
    id: int
    label: str
    description: str | None = None
    child: DbTestModel
    child_list: list[DbTestModel]


class DbTestModel3(BaseModel):
    id: int
    user: str
    child: DbTestModel2
    active: bool = False
    children: list[DbTestModel]
    children_ids: list[int] = []


def get_random_string(iterations: int = 10):
    return "".join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(iterations)
    )


async def get_random_invoice_data():
    return {"out": False, "amount": 10, "memo": f"test_memo_{get_random_string(10)}"}


def get_png_bytes(*, color: str = "blue", size: tuple[int, int] = (32, 32)) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_upload_file(
    contents: bytes,
    *,
    filename: str,
    content_type: str | None,
) -> UploadFile:
    headers = (
        Headers({"content-type": content_type}) if content_type is not None else None
    )
    return UploadFile(BytesIO(contents), filename=filename, headers=headers)


async def get_user_token_headers(client: AsyncClient, user_id: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/usr", json={"usr": user_id})
    client.cookies.clear()
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "Content-type": "application/json",
    }


def make_extension_data(ext_id: str = "demoext") -> ExtensionData:
    return ExtensionData(
        id=ext_id,
        name="Demo Extension",
        stub_version="0.1.0",
        short_description="Generated extension",
        owner_data=DataFields(
            name="OwnerData",
            fields=[DataField(name="wallet_id", type="wallet")],
        ),
        client_data=DataFields(
            name="ClientData",
            fields=[DataField(name="amount", type="int")],
        ),
        settings_data=SettingsFields(name="SettingsData", fields=[]),
        public_page=PublicPageFields(
            owner_data_fields=OwnerDataFields(),
            client_data_fields=ClientDataFields(),
            action_fields=ActionFields(),
        ),
    )


def make_extension_release(ext_id: str, version: str = "1.0.0") -> ExtensionRelease:
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
        is_github_release=False,
        is_version_compatible=True,
    )


def make_installable_extension(
    ext_id: str,
    *,
    version: str = "1.0.0",
    compatible: bool = True,
    active: bool = True,
    pay_to_enable: PayToEnableInfo | None = None,
    dependencies: list[str] | None = None,
    payments: list[ReleasePaymentInfo] | None = None,
) -> InstallableExtension:
    release = make_extension_release(ext_id, version)
    release.is_version_compatible = compatible
    return InstallableExtension(
        id=ext_id,
        name=f"Extension {ext_id}",
        version=version,
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


def make_lnurl_pay_response(
    *,
    min_sendable_msat: int = 1_000,
    max_sendable_msat: int = 10_000,
    text: str = "Test payment",
    identifier: str = "alice@example.com",
    callback: str = "https://example.com/callback",
) -> LnurlPayResponse:
    return LnurlPayResponse(
        callback=parse_obj_as(CallbackUrl, callback),
        minSendable=MilliSatoshi(min_sendable_msat),
        maxSendable=MilliSatoshi(max_sendable_msat),
        metadata=LnurlPayMetadata(
            f"[["
            f'"text/plain","{text}"'
            f"],["
            f'"text/identifier","{identifier}"'
            f"]]"
        ),
    )


set_funding_source()

funding_source = get_funding_source()
is_fake: bool = funding_source.__class__.__name__ == "FakeWallet"
is_regtest: bool = not is_fake
