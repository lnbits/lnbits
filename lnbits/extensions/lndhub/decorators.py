from base64 import b64decode
from functools import wraps

from lnbits.core.crud import get_wallet_for_key
from fastapi import Request
from http import HTTPStatus
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore


def check_wallet(requires_admin=False):
    def wrap(view):
        @wraps(view)
        async def wrapped_view(request: Request, **kwargs):
            token = request.headers["Authorization"].split("Bearer ")[1]
            key_type, key = b64decode(token).decode("utf-8").split(":")

            if requires_admin and key_type != "admin":
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="insufficient permissions",
                )
            g.wallet = await get_wallet_for_key(key, key_type)
            if not g.wallet:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="insufficient permissions",
                )
            return await view(**kwargs)

        return wrapped_view

    return wrap
