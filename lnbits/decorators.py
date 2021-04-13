from cerberus import Validator  # type: ignore
from quart import g, abort, jsonify, request
from functools import wraps
from http import HTTPStatus
from typing import List, Union
from uuid import UUID

from lnbits.core.crud import get_user, get_wallet_for_key
from lnbits.settings import LNBITS_ALLOWED_USERS


def api_check_wallet_key(key_type: str = "invoice", accept_querystring=False):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            try:
                key_value = request.headers.get("X-Api-Key") or request.args["api-key"]
                g.wallet = await get_wallet_for_key(key_value, key_type)
            except KeyError:
                return (
                    jsonify({"message": "`X-Api-Key` header missing."}),
                    HTTPStatus.BAD_REQUEST,
                )

            if not g.wallet:
                return jsonify({"message": "Wrong keys."}), HTTPStatus.UNAUTHORIZED

            return await view(**kwargs)

        return wrapped_view

    return wrap


def api_validate_post_request(*, schema: dict):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            if "application/json" not in request.headers["Content-Type"]:
                return (
                    jsonify({"message": "Content-Type must be `application/json`."}),
                    HTTPStatus.BAD_REQUEST,
                )

            v = Validator(schema)
            data = await request.get_json()
            g.data = {key: data[key] for key in schema.keys() if key in data}

            if not v.validate(g.data):
                return (
                    jsonify({"message": f"Errors in request data: {v.errors}"}),
                    HTTPStatus.BAD_REQUEST,
                )

            return await view(**kwargs)

        return wrapped_view

    return wrap


def check_user_exists(param: str = "usr"):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            g.user = await get_user(request.args.get(param, type=str)) or abort(
                HTTPStatus.NOT_FOUND, "User  does not exist."
            )

            if LNBITS_ALLOWED_USERS and g.user.id not in LNBITS_ALLOWED_USERS:
                abort(HTTPStatus.UNAUTHORIZED, "User not authorized.")

            return await view(**kwargs)

        return wrapped_view

    return wrap


def validate_uuids(
    params: List[str], *, required: Union[bool, List[str]] = False, version: int = 4
):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            query_params = {
                param: request.args.get(param, type=str) for param in params
            }

            for param, value in query_params.items():
                if not value and (required is True or (required and param in required)):
                    abort(HTTPStatus.BAD_REQUEST, f"`{param}` is required.")

                if value:
                    try:
                        UUID(value, version=version)
                    except ValueError:
                        abort(HTTPStatus.BAD_REQUEST, f"`{param}` is not a valid UUID.")

            return await view(**kwargs)

        return wrapped_view

    return wrap
