from base64 import b64decode
from quart import jsonify, g, request
from functools import wraps

from lnbits.core.crud import get_wallet_for_key


def check_wallet(requires_admin=False):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(**kwargs):
            token = request.headers["Authorization"].split("Bearer ")[1]
            key_type, key = b64decode(token).decode("utf-8").split(":")

            if requires_admin and key_type != "admin":
                return jsonify(
                    {"error": True, "code": 2, "message": "insufficient permissions"}
                )

            g.wallet = await get_wallet_for_key(key, key_type)
            if not g.wallet:
                return jsonify(
                    {"error": True, "code": 2, "message": "insufficient permissions"}
                )
            return await view(**kwargs)

        return wrapped_view

    return wrap
