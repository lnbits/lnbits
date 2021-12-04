from quart import g, jsonify, request
from lnbits.decorators import api_validate_post_request

from http import HTTPStatus
from datetime import datetime
import json

from . import autopay_ext, context
from .models import ScheduleEntry, PaymentLogEntry
from .scheduler import Scheduler
from .utils import lnurl_scan
from .storage import SqliteStorage




@autopay_ext.route("/api/v1/scheduler", methods=["POST"])
async def api_scheduler():
    s = context.get_scheduler()
    await s.run(datetime.now())

    return jsonify({"status": "success"}), HTTPStatus.OK


@autopay_ext.route("/api/v1/schedule", methods=["GET"])
async def api_autopay_schedule_get():
    storage = context.storage
    r = []
    for se in await storage.read_schedule_entries():
        s_dict = dict(se._asdict())
        ps = await storage.read_payment_log_entries(se.id)
        s_dict["payments"] = [dict(p._asdict()) for p in ps]
        s_dict["next_payment"] = str(se.next_run(await storage.read_payment_count(se.id)))
        r.append(s_dict)

    return jsonify({"schedule": r}), HTTPStatus.OK


@autopay_ext.route("/api/v1/schedule", methods=["POST"])
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "wallet_id": {"type": "string", "empty": False, "required": True},
        "base_datetime": {"type": "string", "empty": False, "required": True},
        "repeat_freq": {"type": "string", "empty": False, "required": True},
        "lnurl": {"type": "string", "empty": False, "required": True},
        "amount_msat": {"type": "integer", "required": True}
    }
)
async def api_autopay_schedule_post():
    d = json.loads(await request.get_data())

    # Validate
    errors = []
    ScheduleEntry.validate_base_datetime(d["base_datetime"], errors)
    ScheduleEntry.validate_repeat_freq(d["repeat_freq"], errors)
    try:
        lnurl_params = await context.lnurl_scan(d["lnurl"])
        if d["amount_msat"] < lnurl_params["minSendable"]:
            errors.append(f"'amount_msat' must be at least {lnurl_params['minSendable']} to pay this LNURL")
        if d["amount_msat"] > lnurl_params["maxSendable"]:
            errors.append(f"'amount_msat' must be at max {lnurl_params['maxSendable']} to pay this LNURL")
    except (AssertionError, ValueError) as e:
        errors.append(f"'lnurl' invalid: {e}")

    if len(errors) > 0:
        return jsonify({"message": f"Errors in request data: {errors}"}), HTTPStatus.BAD_REQUEST,

    se = ScheduleEntry.from_request(d)

    await context.storage.create_schedule_entry(se)

    return jsonify({"status": "success",}), HTTPStatus.CREATED


@autopay_ext.route("/api/v1/schedule/<int:schedule_id>", methods=["DELETE"])
async def api_autopay_schedule_delete(schedule_id: int):
    await context.storage.delete_schedule_entry(schedule_id)

    return jsonify({"status": "success",}), HTTPStatus.OK
