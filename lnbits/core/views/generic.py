import trio  # type: ignore
import httpx
from os import path
from http import HTTPStatus
from quart import (
    g,
    abort,
    redirect,
    request,
    render_template,
    send_from_directory,
    url_for,
)
from lnurl import LnurlResponse, LnurlWithdrawResponse, decode as decode_lnurl  # type: ignore

from lnbits.core import core_app
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.settings import LNBITS_ALLOWED_USERS, SERVICE_FEE

from .. import db
from ..crud import (
    create_account,
    get_user,
    update_user_extension,
    create_wallet,
    delete_wallet,
)
from ..services import redeem_lnurl_withdraw


@core_app.route("/favicon.ico")
async def favicon():
    return await send_from_directory(
        path.join(core_app.root_path, "static"), "favicon.ico"
    )


@core_app.route("/")
async def home():
    return await render_template(
        "core/index.html", lnurl=request.args.get("lightning", None)
    )


@core_app.route("/extensions")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def extensions():
    extension_to_enable = request.args.get("enable", type=str)
    extension_to_disable = request.args.get("disable", type=str)

    if extension_to_enable and extension_to_disable:
        abort(
            HTTPStatus.BAD_REQUEST, "You can either `enable` or `disable` an extension."
        )

    if extension_to_enable:
        await update_user_extension(
            user_id=g.user.id, extension=extension_to_enable, active=1
        )
    elif extension_to_disable:
        await update_user_extension(
            user_id=g.user.id, extension=extension_to_disable, active=0
        )

    return await render_template("core/extensions.html", user=await get_user(g.user.id))


@core_app.route("/wallet")
@validate_uuids(["usr", "wal"])
async def wallet():
    user_id = request.args.get("usr", type=str)
    wallet_id = request.args.get("wal", type=str)
    wallet_name = request.args.get("nme", type=str)
    service_fee = int(SERVICE_FEE) if int(SERVICE_FEE) == SERVICE_FEE else SERVICE_FEE

    # just wallet_name: create a new user, then create a new wallet for user with wallet_name
    # just user_id: return the first user wallet or create one if none found (with default wallet_name)
    # user_id and wallet_name: create a new wallet for user with wallet_name
    # user_id and wallet_id: return that wallet if user is the owner
    # nothing: create everything

    if not user_id:
        user = await get_user((await create_account()).id)
    else:
        user = await get_user(user_id)
        if not user:
            abort(HTTPStatus.NOT_FOUND, "User does not exist.")
            return

        if LNBITS_ALLOWED_USERS and user_id not in LNBITS_ALLOWED_USERS:
            abort(HTTPStatus.UNAUTHORIZED, "User not authorized.")

    if not wallet_id:
        if user.wallets and not wallet_name:
            wallet = user.wallets[0]
        else:
            wallet = await create_wallet(user_id=user.id, wallet_name=wallet_name)

        return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))

    wallet = user.get_wallet(wallet_id)
    if not wallet:
        abort(HTTPStatus.FORBIDDEN, "Not your wallet.")

    return await render_template(
        "core/wallet.html", user=user, wallet=wallet, service_fee=service_fee
    )


@core_app.route("/deletewallet")
@validate_uuids(["usr", "wal"], required=True)
@check_user_exists()
async def deletewallet():
    wallet_id = request.args.get("wal", type=str)
    user_wallet_ids = g.user.wallet_ids

    if wallet_id not in user_wallet_ids:
        abort(HTTPStatus.FORBIDDEN, "Not your wallet.")
    else:
        await delete_wallet(user_id=g.user.id, wallet_id=wallet_id)
        user_wallet_ids.remove(wallet_id)

    if user_wallet_ids:
        return redirect(url_for("core.wallet", usr=g.user.id, wal=user_wallet_ids[0]))

    return redirect(url_for("core.home"))


@core_app.route("/lnurlwallet")
async def lnurlwallet():
    async with httpx.AsyncClient() as client:
        try:
            lnurl = decode_lnurl(request.args.get("lightning"))
            r = await client.get(str(lnurl))
            withdraw_res = LnurlResponse.from_dict(r.json())

            if not withdraw_res.ok:
                return (
                    f"Could not process lnurl-withdraw: {withdraw_res.error_msg}",
                    HTTPStatus.BAD_REQUEST,
                )

            if not isinstance(withdraw_res, LnurlWithdrawResponse):
                return (
                    f"Expected an lnurl-withdraw code, got {withdraw_res.tag}",
                    HTTPStatus.BAD_REQUEST,
                )
        except Exception as exc:
            return (
                f"Could not process lnurl-withdraw: {exc}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    account = await create_account()
    user = await get_user(account.id)
    wallet = await create_wallet(user_id=user.id)
    await db.commit()

    g.nursery.start_soon(
        redeem_lnurl_withdraw,
        wallet.id,
        withdraw_res,
        "LNbits initial funding: voucher redeem.",
    )
    await trio.sleep(3)

    return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))
