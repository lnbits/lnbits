import asyncio
import json
import re
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from lnurl import (
    LnAddress,
    LnurlAuthResponse,
    LnurlErrorResponse,
    LnurlException,
    LnurlPayActionResponse,
    LnurlPayResponse,
    LnurlResponseException,
)
from lnurl.models import MessageAction
from lnurl.types import CallbackUrl, LightningInvoice
from pydantic import TypeAdapter

from lnbits.core.crud.wallets import create_wallet, get_wallet, update_wallet
from lnbits.core.db import core_app_extra
from lnbits.core.models import Account, CreateInvoice
from lnbits.core.models.lnurl import CreateLnurlPayment, LnurlScan
from lnbits.core.models.wallets import KeyType, WalletTypeInfo
from lnbits.core.services.lightning_address import (
    ExtensionLnAddressStatus,
    check_extension_lightning_address,
    wallet_lightning_address_callback,
)
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.core.services.users import create_user_account
from lnbits.core.views.lnurl_api import (
    api_lnurlscan,
    api_lnurlscan_post,
    api_payments_pay_lnurl,
    api_perform_lnurlauth,
)
from tests.helpers import make_lnurl_pay_response

TEST_BOLT11 = (
    "lnbc1pnsu5z3pp57getmdaxhg5kc9yh2a2qsh7cjf4gnccgkw0qenm8vsqv50w7s"
    "ygqdqj0fjhymeqv9kk7atwwscqzzsxqyz5vqsp5e2yyqcp0a3ujeesp24ya0glej"
    "srh703md8mrx0g2lyvjxy5w27ss9qxpqysgqyjreasng8a086kpkczv48er5c6l5"
    "73aym6ynrdl9nkzqnag49vt3sjjn8qdfq5cr6ha0vrdz5c5r3v4aghndly0hplmv"
    "6hjxepwp93cq398l3s"
)


@pytest.mark.anyio
async def test_wallet_lightning_address_lookup_and_callback(
    client, to_user, settings, mocker
):
    settings.lnbits_ln_address_mode = "core_first"
    wallet = await create_wallet(user_id=to_user.id, wallet_name="ln address")
    assert wallet.lightning_address

    response = await client.get(f"/.well-known/lnurlp/{wallet.lightning_address}")
    assert response.status_code == 200
    data = response.json()
    metadata = data["metadata"]
    assert data["minSendable"] == 1000
    assert data["maxSendable"] == 2_100_000_000_000_000_000
    assert data["commentAllowed"] == 799
    assert f"{wallet.lightning_address}@" in metadata
    assert "text/identifier" in metadata

    tagged_response = await client.get(
        f"/.well-known/lnurlp/{wallet.lightning_address}+market"
    )
    assert tagged_response.status_code == 200
    tagged_data = tagged_response.json()
    tagged_metadata = json.loads(tagged_data["metadata"])
    assert ["text/tag", "market"] in tagged_metadata
    assert any(
        entry[0] == "text/identifier"
        and entry[1].startswith(f"{wallet.lightning_address}+market@")
        for entry in tagged_metadata
    )

    create_invoice_mock = mocker.patch(
        "lnbits.core.services.lightning_address.create_invoice",
        mocker.AsyncMock(return_value=SimpleNamespace(bolt11=TEST_BOLT11)),
    )
    callback = tagged_data["callback"].split("testserver")[-1]
    callback_response = await client.get(f"{callback}?amount=21000&comment=hello")
    assert callback_response.status_code == 200
    assert callback_response.json()["pr"] == TEST_BOLT11
    create_invoice_mock.assert_awaited_once()
    kwargs = create_invoice_mock.await_args.kwargs
    assert kwargs["wallet_id"] == wallet.id
    assert kwargs["amount"] == 21
    assert kwargs["extra"]["tag"] == "wallet_lightning_address"
    assert kwargs["extra"]["comment"] == "hello"
    assert kwargs["extra"]["lnaddress"].startswith(f"{wallet.lightning_address}+")
    assert kwargs["extra"]["lnaddress_tag"] == "market"


@pytest.mark.anyio
async def test_wallet_lightning_address_generation_settings(to_user, settings):
    settings.lnbits_ln_address_mode = "core_first"
    wallet = await create_wallet(user_id=to_user.id)
    assert wallet.lightning_address
    assert re.fullmatch(r"[a-z]+[a-z]+[0-9]", wallet.lightning_address)

    settings.lnbits_ln_address_mode = "extension_only"
    disabled_wallet = await create_wallet(user_id=to_user.id)
    assert disabled_wallet.lightning_address is None

    settings.lnbits_ln_address_mode = "core_first"
    backfilled = await get_wallet(disabled_wallet.id)
    assert backfilled
    assert backfilled.lightning_address


@pytest.mark.anyio
async def test_wallet_lightning_address_callback_validates_comment(
    to_user, settings, mocker
):
    settings.lnbits_ln_address_mode = "core_first"
    wallet = await create_wallet(user_id=to_user.id)
    assert wallet.lightning_address
    request = mocker.Mock()
    request.url.netloc = "example.com"
    request.query_params.get.return_value = "x" * 800

    result = await wallet_lightning_address_callback(
        wallet.lightning_address, request, amount=1000
    )
    assert isinstance(result, LnurlErrorResponse)
    assert "can only accept 799" in result.reason


@pytest.mark.anyio
async def test_lnurl_api_scan_routes_validate_and_forward(mocker):
    pay_response = make_lnurl_pay_response()
    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(return_value=pay_response),
    )

    scanned = await api_lnurlscan("lnurl1example")
    assert isinstance(scanned, LnurlPayResponse)
    assert scanned.callback == pay_response.callback

    scanned_post = await api_lnurlscan_post(
        scan=LnurlScan(lnurl=LnAddress("alice@example.com"))
    )
    assert isinstance(scanned_post, LnurlPayResponse)
    assert scanned_post.callback == pay_response.callback

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(return_value=LnurlErrorResponse(reason="blocked callback")),
    )
    with pytest.raises(HTTPException, match="blocked callback"):
        await api_lnurlscan("lnurl1blocked")

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurl_handle",
        mocker.AsyncMock(side_effect=LnurlException("invalid lnurl")),
    )
    with pytest.raises(HTTPException, match="invalid lnurl"):
        await api_lnurlscan("lnurl1invalid")


@pytest.mark.anyio
async def test_lnurl_api_auth_and_pay_flow(mocker):
    user = await create_user_account(
        Account(
            id=uuid4().hex,
            username=f"user_{uuid4().hex[:8]}",
            email=f"user_{uuid4().hex[:8]}@lnbits.com",
        )
    )
    wallet = user.wallets[0]
    wallet_info = WalletTypeInfo(key_type=KeyType.admin, wallet=wallet)
    pay_response = make_lnurl_pay_response()
    payment = await create_wallet_invoice(
        wallet.id, CreateInvoice(out=False, amount=21, memo="lnurl")
    )

    auth_response = LnurlAuthResponse(
        callback=TypeAdapter(CallbackUrl).validate_python("https://example.com/auth"),
        k1="k1-value",
    )
    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurlauth",
        mocker.AsyncMock(return_value=auth_response),
    )
    authenticated = await api_perform_lnurlauth(auth_response, wallet_info)
    assert isinstance(authenticated, LnurlAuthResponse)
    assert authenticated.k1 == "k1-value"

    mocker.patch(
        "lnbits.core.views.lnurl_api.lnurlauth",
        mocker.AsyncMock(side_effect=LnurlResponseException("denied")),
    )
    with pytest.raises(HTTPException, match="denied"):
        await api_perform_lnurlauth(auth_response, wallet_info)

    action_response = LnurlPayActionResponse(
        pr=cast(LightningInvoice, LightningInvoice(TEST_BOLT11)),
        disposable=False,
        successAction=TypeAdapter(MessageAction).validate_python({"message": "paid"}),
    )
    fetch_mock = mocker.patch(
        "lnbits.core.views.lnurl_api.fetch_lnurl_pay_request",
        mocker.AsyncMock(return_value=(pay_response, action_response)),
    )
    pay_mock = mocker.patch(
        "lnbits.core.views.lnurl_api.pay_invoice",
        mocker.AsyncMock(return_value=payment),
    )

    paid = await api_payments_pay_lnurl(
        CreateLnurlPayment(
            res=pay_response, amount=2_000, unit="USD", comment="thanks"
        ),
        wallet_info,
    )
    assert paid.payment_hash == payment.payment_hash
    fetch_mock.assert_awaited_once()
    pay_mock.assert_awaited_once()
    assert pay_mock.await_args is not None
    assert action_response.successAction is not None
    assert pay_mock.await_args.kwargs["extra"] == {
        "stored": True,
        "success_action": action_response.successAction.json(),
        "comment": "thanks",
        "fiat_currency": "USD",
        "fiat_amount": 2.0,
    }

    with pytest.raises(HTTPException, match="Missing LNURL or LnurlPayResponse data."):
        await api_payments_pay_lnurl(CreateLnurlPayment(amount=1), wallet_info)


@pytest.mark.anyio
async def test_extension_lightning_address_probe_statuses(
    app: FastAPI, settings, monkeypatch
):
    assert (
        await check_extension_lightning_address("alice")
        == ExtensionLnAddressStatus.AVAILABLE
    )

    ext_id = "lnurlp"
    ext_router = APIRouter(prefix=f"/{ext_id}")

    @ext_router.get(
        "/api/v1/well-known/{username}",
        name="test_lnurlp.well_known_probe",
    )
    async def ext_well_known(username: str, request: Request):
        if username == "taken":
            callback_url = str(
                request.url_for("test_lnurlp.well_known_probe", username="taken")
            )
            pay_resp = make_lnurl_pay_response(
                identifier="taken@example.com",
                callback=callback_url,
            )
            pay_resp.allowsNostr = True
            pay_resp.nostrPubkey = "ab" * 32
            return pay_resp
        if username == "lnurlerr":
            return LnurlErrorResponse(reason="Pay link does not exist.")
        if username == "servererr":
            return JSONResponse({"detail": "rate lookup failed"}, status_code=500)
        if username == "badjson":
            return Response(
                content="not-json", media_type="text/plain", status_code=200
            )
        if username == "badschema":
            return JSONResponse({"unexpected": True}, status_code=200)
        if username == "slow":
            await asyncio.sleep(0.2)
            return LnurlErrorResponse(reason="too slow")
        raise HTTPException(status_code=404, detail="Pay link not found.")

    with _mounted_lnurlp_extension(app, settings, ext_router, ext_id):
        assert (
            await check_extension_lightning_address("missing")
            == ExtensionLnAddressStatus.AVAILABLE
        )
        assert (
            await check_extension_lightning_address("lnurlerr")
            == ExtensionLnAddressStatus.AVAILABLE
        )
        assert (
            await check_extension_lightning_address("  Taken  ")
            == ExtensionLnAddressStatus.TAKEN
        )
        assert (
            await check_extension_lightning_address("servererr")
            == ExtensionLnAddressStatus.UNAVAILABLE
        )
        assert (
            await check_extension_lightning_address("badjson")
            == ExtensionLnAddressStatus.UNAVAILABLE
        )
        assert (
            await check_extension_lightning_address("badschema")
            == ExtensionLnAddressStatus.UNAVAILABLE
        )

        monkeypatch.setattr(
            "lnbits.core.services.lightning_address.EXTENSION_LNURL_PROBE_TIMEOUT_SECONDS",
            0.02,
        )
        assert (
            await check_extension_lightning_address("slow")
            == ExtensionLnAddressStatus.UNAVAILABLE
        )

        monkeypatch.setattr(core_app_extra, "local_lnurl_app", None)
        assert (
            await check_extension_lightning_address("taken")
            == ExtensionLnAddressStatus.AVAILABLE
        )


@pytest.mark.anyio
async def test_lnurlp_routing_modes_case_and_tag_split_brain(
    app: FastAPI, client, to_user, settings
):
    nostr_pubkey = "cd" * 32
    legacy_collision_wallet = await create_wallet(
        user_id=to_user.id, wallet_name="legacy-collision"
    )
    legacy_collision_wallet.lightning_address = "alice"
    await update_wallet(legacy_collision_wallet)

    legacy_err_tag_wallet = await create_wallet(
        user_id=to_user.id, wallet_name="legacy-err-tag"
    )
    legacy_err_tag_wallet.lightning_address = "errtag"
    await update_wallet(legacy_err_tag_wallet)

    legacy_broken_wallet = await create_wallet(
        user_id=to_user.id, wallet_name="legacy-broken"
    )
    legacy_broken_wallet.lightning_address = "extbroken"
    await update_wallet(legacy_broken_wallet)

    core_only_wallet = await create_wallet(user_id=to_user.id, wallet_name="core-only")
    core_only_wallet.lightning_address = "coreonly"
    await update_wallet(core_only_wallet)

    # Without an extension redirect, extension_only rejects lookups and
    # extension_first serves core wallets (including +tag).
    settings.lnbits_ln_address_mode = "extension_only"
    no_ext_only = await client.get("/.well-known/lnurlp/coreonly")
    assert no_ext_only.status_code == 200
    assert no_ext_only.json()["status"] == "ERROR"
    assert "not supported" in no_ext_only.json()["reason"]

    settings.lnbits_ln_address_mode = "extension_first"
    no_ext_first_tagged = await client.get("/.well-known/lnurlp/coreonly+promo")
    assert no_ext_first_tagged.status_code == 200
    assert "coreonly+promo@" in no_ext_first_tagged.json()["metadata"]

    ext_id = "lnurlp"
    ext_router = APIRouter(prefix=f"/{ext_id}")

    @ext_router.get("/api/v1/well-known/{username}")
    async def ext_well_known(username: str):
        if username in {"alice", "extonly", "errtag", "exttagged+vip"}:
            pay_resp = make_lnurl_pay_response(
                identifier=f"{username}@ext.example",
                callback=f"https://ext.example/cb/{username}",
            )
            pay_resp.allowsNostr = True
            pay_resp.nostrPubkey = nostr_pubkey
            return pay_resp
        if username == "errtag+vip":
            return LnurlErrorResponse(reason="Tag not supported by extension.")
        if username == "extbroken":
            return JSONResponse({"detail": "rate error"}, status_code=500)
        raise HTTPException(status_code=404, detail="Not found")

    with _mounted_lnurlp_extension(app, settings, ext_router, ext_id):
        # 1. extension_first: case-insensitive match, nostr preserved, +tag blocked
        settings.lnbits_ln_address_mode = "extension_first"

        ext_upper = await client.get("/.well-known/lnurlp/Alice")
        assert ext_upper.status_code == 200
        assert ext_upper.json()["callback"] == "https://ext.example/cb/alice"
        assert ext_upper.json()["allowsNostr"] is True
        assert ext_upper.json()["nostrPubkey"] == nostr_pubkey

        ext_tag_404 = await client.get("/.well-known/lnurlp/alice+vip")
        assert ext_tag_404.status_code == 200
        assert ext_tag_404.json()["status"] == "ERROR"

        ext_empty_tag = await client.get("/.well-known/lnurlp/alice+")
        assert ext_empty_tag.status_code == 200
        assert ext_empty_tag.json()["status"] == "ERROR"

        ext_tag_err_json = await client.get("/.well-known/lnurlp/errtag+vip")
        assert ext_tag_err_json.status_code == 200
        assert ext_tag_err_json.json()["status"] == "ERROR"
        assert ext_tag_err_json.json()["reason"] == "Tag not supported by extension."

        ext_tag_supported = await client.get("/.well-known/lnurlp/ExtTagged+VIP")
        assert ext_tag_supported.status_code == 200
        assert (
            ext_tag_supported.json()["callback"]
            == "https://ext.example/cb/exttagged+vip"
        )

        ext_broken_direct = await client.get("/.well-known/lnurlp/extbroken")
        assert ext_broken_direct.status_code == 200
        assert ext_broken_direct.json()["status"] == "ERROR"

        ext_broken_tagged = await client.get("/.well-known/lnurlp/extbroken+vip")
        assert ext_broken_tagged.status_code == 200
        assert ext_broken_tagged.json()["status"] == "ERROR"

        core_fallback = await client.get("/.well-known/lnurlp/coreonly+shop")
        assert core_fallback.status_code == 200
        assert "coreonly+shop@" in core_fallback.json()["metadata"]

        # 2. core_first: core wallet wins if present, else extension fallback
        settings.lnbits_ln_address_mode = "core_first"

        core_wins = await client.get("/.well-known/lnurlp/alice")
        assert core_wins.status_code == 200
        assert "/api/v1/lnurl/wallet/alice/cb" in core_wins.json()["callback"]

        ext_fallback = await client.get("/.well-known/lnurlp/ExtOnly")
        assert ext_fallback.status_code == 200
        assert ext_fallback.json()["callback"] == "https://ext.example/cb/extonly"
        assert ext_fallback.json()["allowsNostr"] is True
        assert ext_fallback.json()["nostrPubkey"] == nostr_pubkey

        core_first_missing = await client.get("/.well-known/lnurlp/nobody")
        assert core_first_missing.status_code == 200
        assert core_first_missing.json()["status"] == "ERROR"

        # 3. extension_only: extension resolves, core wallets never resolve
        settings.lnbits_ln_address_mode = "extension_only"

        ext_only_ok = await client.get("/.well-known/lnurlp/ExtOnly")
        assert ext_only_ok.status_code == 200
        assert ext_only_ok.json()["callback"] == "https://ext.example/cb/extonly"

        ext_only_core_blocked = await client.get("/.well-known/lnurlp/coreonly")
        assert ext_only_core_blocked.status_code == 200
        assert ext_only_core_blocked.json()["status"] == "ERROR"
        assert "not supported" in ext_only_core_blocked.json()["reason"]

        for unsafe_name in ("extonly%3Fsmuggled=1", "extonly+bad%3Ftag", ".."):
            unsafe_resp = await client.get(f"/.well-known/lnurlp/{unsafe_name}")
            assert unsafe_resp.status_code in {200, 404}
            if unsafe_resp.status_code == 200:
                assert unsafe_resp.json()["status"] == "ERROR"


@contextmanager
def _mounted_lnurlp_extension(_app, settings, ext_router: APIRouter, ext_id: str):
    fastapi_app = cast(FastAPI, core_app_extra.local_lnurl_app)
    settings.activate_extension_paths(
        ext_id,
        [
            {
                "from_path": "/.well-known/lnurlp",
                "redirect_to_path": "/api/v1/well-known",
            }
        ],
    )
    fastapi_app.include_router(ext_router)
    try:
        yield
    finally:
        fastapi_app.router.routes = [
            route
            for route in fastapi_app.router.routes
            if not (
                getattr(route, "path", "") == f"/{ext_id}"
                or getattr(route, "path", "").startswith(f"/{ext_id}/")
            )
        ]
        fastapi_app.openapi_schema = None
        settings.deactivate_extension_paths(ext_id)
        settings.lnbits_deactivated_extensions.discard(ext_id)
        settings.lnbits_installed_extensions_ids.discard(ext_id)
