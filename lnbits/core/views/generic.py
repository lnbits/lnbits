from os import path
from http import HTTPStatus
from quart import (
    g,
    abort,
    jsonify,
    request,
    redirect,
    render_template,
    send_from_directory,
    url_for,
)

from lnbits.core import core_app, db
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.settings import LNBITS_ALLOWED_USERS, SERVICE_FEE, LNBITS_SITE_TITLE

from ..crud import (
    create_account,
    get_user,
    update_user_extension,
    create_wallet,
    delete_wallet,
    get_balance_check,
    save_balance_notify,
)
from ..services import redeem_lnurl_withdraw, pay_invoice


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


@core_app.route("/withdraw")
@validate_uuids(["usr", "wal"], required=True)
async def lnurl_full_withdraw():
    user = await get_user(request.args.get("usr"))
    if not user:
        return jsonify({"status": "ERROR", "reason": "User does not exist."})

    wallet = user.get_wallet(request.args.get("wal"))
    if not wallet:
        return jsonify({"status": "ERROR", "reason": "Wallet does not exist."})

    return jsonify(
        {
            "tag": "withdrawRequest",
            "callback": url_for(
                "core.lnurl_full_withdraw_callback",
                usr=user.id,
                wal=wallet.id,
                _external=True,
            ),
            "k1": "0",
            "minWithdrawable": 1 if wallet.withdrawable_balance else 0,
            "maxWithdrawable": wallet.withdrawable_balance,
            "defaultDescription": f"{LNBITS_SITE_TITLE} balance withdraw from {wallet.id[0:5]}",
            "balanceCheck": url_for(
                "core.lnurl_full_withdraw", usr=user.id, wal=wallet.id, _external=True
            ),
        }
    )


@core_app.route("/withdraw/cb")
@validate_uuids(["usr", "wal"], required=True)
async def lnurl_full_withdraw_callback():
    user = await get_user(request.args.get("usr"))
    if not user:
        return jsonify({"status": "ERROR", "reason": "User does not exist."})

    wallet = user.get_wallet(request.args.get("wal"))
    if not wallet:
        return jsonify({"status": "ERROR", "reason": "Wallet does not exist."})

    pr = request.args.get("pr")

    async def pay():
        await pay_invoice(wallet_id=wallet.id, payment_request=pr)

    g.nursery.start_soon(pay)

    balance_notify = request.args.get("balanceNotify")
    if balance_notify:
        await save_balance_notify(wallet.id, balance_notify)

    return jsonify({"status": "OK"})


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


@core_app.route("/withdraw/notify/<service>")
@validate_uuids(["wal"], required=True)
async def lnurl_balance_notify(service: str):
    bc = await get_balance_check(request.args.get("wal"), service)
    if bc:
        redeem_lnurl_withdraw(bc.wallet, bc.url)


@core_app.route("/lnurlwallet")
async def lnurlwallet():
    async with db.connect() as conn:
        account = await create_account(conn=conn)
        user = await get_user(account.id, conn=conn)
        wallet = await create_wallet(user_id=user.id, conn=conn)

    g.nursery.start_soon(
        redeem_lnurl_withdraw,
        wallet.id,
        request.args.get("lightning"),
        "LNbits initial funding: voucher redeem.",
        {"tag": "lnurlwallet"},
        5,  # wait 5 seconds before sending the invoice to the service
    )

    return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))


@core_app.route("/manifest/<usr>.webmanifest")
async def manifest(usr: str):
    user = await get_user(usr)
    if not user:
        return "", HTTPStatus.NOT_FOUND

    return jsonify(
        {
            "short_name": "LNbits",
            "name": "LNbits Wallet",
            "icons": [
                {
                    "src": "https://cdn.jsdelivr.net/gh/lnbits/lnbits@0.3.0/docs/logos/lnbits.png",
                    "type": "image/png",
                    "sizes": "900x900",
                }
            ],
            "start_url": "/wallet?usr=" + usr,
            "background_color": "#3367D6",
            "description": "Weather forecast information",
            "display": "standalone",
            "scope": "/",
            "theme_color": "#3367D6",
            "shortcuts": [
                {
                    "name": wallet.name,
                    "short_name": wallet.name,
                    "description": wallet.name,
                    "url": "/wallet?usr=" + usr + "&wal=" + wallet.id,
                }
                for wallet in user.wallets
            ],
        }
    )
