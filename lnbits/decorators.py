from cerberus import Validator  # type: ignore
from flask import g, abort, jsonify, request
from functools import wraps
from typing import List, Union
from uuid import UUID

from lnbits.core.crud import get_user, get_wallet_for_key
from .helpers import Status


def api_check_wallet_key(key_type: str = "invoice"):
    def wrap(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            try:
                g.wallet = get_wallet_for_key(request.headers["X-Api-Key"], key_type)
            except KeyError:
                return jsonify({"message": "`X-Api-Key` header missing."}), Status.BAD_REQUEST

            if not g.wallet:
                return jsonify({"message": "Wrong keys."}), Status.UNAUTHORIZED

            return view(**kwargs)

        return wrapped_view

    return wrap


def api_validate_post_request(*, schema: dict):
    def wrap(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if "application/json" not in request.headers["Content-Type"]:
                return jsonify({"message": "Content-Type must be `application/json`."}), Status.BAD_REQUEST

            v = Validator(schema)
            g.data = {key: request.json[key] for key in schema.keys()}

            if not v.validate(g.data):
                return jsonify({"message": f"Errors in request data: {v.errors}"}), Status.BAD_REQUEST

            return view(**kwargs)

        return wrapped_view

    return wrap


def check_user_exists(param: str = "usr"):
    def wrap(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            g.user = get_user(request.args.get(param, type=str)) or abort(Status.NOT_FOUND, "User not found.")
            return view(**kwargs)

        return wrapped_view

    return wrap


def validate_uuids(params: List[str], *, required: Union[bool, List[str]] = False, version: int = 4):
    def wrap(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            query_params = {param: request.args.get(param, type=str) for param in params}

            for param, value in query_params.items():
                if not value and (required is True or (required and param in required)):
                    abort(Status.BAD_REQUEST, f"`{param}` is required.")

                if value:
                    try:
                        UUID(value, version=version)
                    except ValueError:
                        abort(Status.BAD_REQUEST, f"`{param}` is not a valid UUID.")

            return view(**kwargs)

        return wrapped_view

    return wrap
