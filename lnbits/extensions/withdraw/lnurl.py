import shortuuid  # type: ignore
from http import HTTPStatus
from datetime import datetime
from quart import jsonify, request

from lnbits.core.services import pay_invoice

from . import withdraw_ext
from .crud import get_withdraw_link_by_hash, update_withdraw_link


# FOR LNURLs WHICH ARE NOT UNIQUE


@withdraw_ext.route("/api/v1/lnurl/<unique_hash>", methods=["GET"])
async def api_lnurl_response(unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-withdraw not found."}),
            HTTPStatus.OK,
        )

    if link.is_spent:
        return (
            jsonify({"status": "ERROR", "reason": "Withdraw is spent."}),
            HTTPStatus.OK,
        )

    return jsonify(link.lnurl_response.dict()), HTTPStatus.OK


# FOR LNURLs WHICH ARE UNIQUE


@withdraw_ext.route("/api/v1/lnurl/<unique_hash>/<id_unique_hash>", methods=["GET"])
async def api_lnurl_multi_response(unique_hash, id_unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-withdraw not found."}),
            HTTPStatus.OK,
        )

    if link.is_spent:
        return (
            jsonify({"status": "ERROR", "reason": "Withdraw is spent."}),
            HTTPStatus.OK,
        )

    useslist = link.usescsv.split(",")
    found = False
    for x in useslist:
        tohash = link.id + link.unique_hash + str(x)
        if id_unique_hash == shortuuid.uuid(name=tohash):
            found = True
    if not found:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-withdraw not found."}),
            HTTPStatus.OK,
        )

    return jsonify(link.lnurl_response.dict()), HTTPStatus.OK


# CALLBACK


@withdraw_ext.route("/api/v1/lnurl/cb/<unique_hash>", methods=["GET"])
async def api_lnurl_callback(unique_hash):
    link = await get_withdraw_link_by_hash(unique_hash)
    k1 = request.args.get("k1", type=str)
    payment_request = request.args.get("pr", type=str)
    now = int(datetime.now().timestamp())

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-withdraw not found."}),
            HTTPStatus.OK,
        )

    if link.is_spent:
        return (
            jsonify({"status": "ERROR", "reason": "Withdraw is spent."}),
            HTTPStatus.OK,
        )

    if link.k1 != k1:
        return jsonify({"status": "ERROR", "reason": "Bad request."}), HTTPStatus.OK

    if now < link.open_time:
        return (
            jsonify(
                {"status": "ERROR", "reason": f"Wait {link.open_time - now} seconds."}
            ),
            HTTPStatus.OK,
        )

    try:
        usescsv = ""
        for x in range(1, link.uses - link.used):
            usecv = link.usescsv.split(",")
            usescsv += "," + str(usecv[x])
        usecsvback = usescsv
        usescsv = usescsv[1:]

        changesback = {
            "open_time": link.wait_time,
            "used": link.used,
            "usescsv": usecsvback,
        }

        changes = {
            "open_time": link.wait_time + now,
            "used": link.used + 1,
            "usescsv": usescsv,
        }

        await update_withdraw_link(link.id, **changes)

        await pay_invoice(
            wallet_id=link.wallet,
            payment_request=payment_request,
            max_sat=link.max_withdrawable,
            extra={"tag": "withdraw"},
        )
    except ValueError as e:
        await update_withdraw_link(link.id, **changesback)
        return jsonify({"status": "ERROR", "reason": str(e)})
    except PermissionError:
        await update_withdraw_link(link.id, **changesback)
        return jsonify({"status": "ERROR", "reason": "Withdraw link is empty."})
    except Exception as e:
        await update_withdraw_link(link.id, **changesback)
        return jsonify({"status": "ERROR", "reason": str(e)})

    return jsonify({"status": "OK"}), HTTPStatus.OK
