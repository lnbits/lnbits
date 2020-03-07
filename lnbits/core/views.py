from flask import g, abort, redirect, request, render_template, send_from_directory, url_for
from os import path

from lnbits.core import core_app
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.helpers import Status

from .crud import (
    create_account,
    get_user,
    update_user_extension,
    create_wallet,
    delete_wallet,
)


@core_app.route("/favicon.ico")
def favicon():
    return send_from_directory(path.join(core_app.root_path, "static"), "favicon.ico")


@core_app.route("/")
def home():
    return render_template("core/index.html")


@core_app.route("/extensions")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def extensions():
    extension_to_enable = request.args.get("enable", type=str)
    extension_to_disable = request.args.get("disable", type=str)

    if extension_to_enable and extension_to_disable:
        abort(Status.BAD_REQUEST, "You can either `enable` or `disable` an extension.")

    if extension_to_enable:
        update_user_extension(user_id=g.user.id, extension=extension_to_enable, active=1)
    elif extension_to_disable:
        update_user_extension(user_id=g.user.id, extension=extension_to_disable, active=0)

    return render_template("core/extensions.html", user=get_user(g.user.id))


@core_app.route("/wallet")
@validate_uuids(["usr", "wal"])
def wallet():
    user_id = request.args.get("usr", type=str)
    wallet_id = request.args.get("wal", type=str)
    wallet_name = request.args.get("nme", type=str)

    # just wallet_name: create a new user, then create a new wallet for user with wallet_name
    # just user_id: return the first user wallet or create one if none found (with default wallet_name)
    # user_id and wallet_name: create a new wallet for user with wallet_name
    # user_id and wallet_id: return that wallet if user is the owner
    # nothing: create everything

    if not user_id:
        user = get_user(create_account().id)
    else:
        user = get_user(user_id) or abort(Status.NOT_FOUND, "User does not exist.")

    if not wallet_id:
        if user.wallets and not wallet_name:
            wallet = user.wallets[0]
        else:
            wallet = create_wallet(user_id=user.id, wallet_name=wallet_name)

        return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))

    if wallet_id not in user.wallet_ids:
        abort(Status.FORBIDDEN, "Not your wallet.")

    return render_template("core/wallet.html", user=user, wallet=user.get_wallet(wallet_id))


@core_app.route("/deletewallet")
@validate_uuids(["usr", "wal"], required=True)
@check_user_exists()
def deletewallet():
    wallet_id = request.args.get("wal", type=str)
    user_wallet_ids = g.user.wallet_ids

    if wallet_id not in user_wallet_ids:
        abort(Status.FORBIDDEN, "Not your wallet.")
    else:
        delete_wallet(user_id=g.user.id, wallet_id=wallet_id)
        user_wallet_ids.remove(wallet_id)

    if user_wallet_ids:
        return redirect(url_for("core.wallet", usr=g.user.id, wal=user_wallet_ids[0]))

    return redirect(url_for("core.home"))
