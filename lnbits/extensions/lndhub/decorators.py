from base64 import b64decode
from functools import wraps
from fastapi.param_functions import Security

from fastapi.security.api_key import APIKeyHeader

from lnbits.core.crud import get_wallet_for_key
from fastapi import Request, status
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse

from lnbits.decorators import WalletTypeInfo, get_key_type  # type: ignore


api_key_header_auth = APIKeyHeader(name="AUTHORIZATION", auto_error=False, description="Admin or Invoice key for LNDHub API's")
async def check_wallet(r: Request, api_key_header_auth: str = Security(api_key_header_auth)) -> WalletTypeInfo:    
    if not api_key_header_auth:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    t = api_key_header_auth.split(" ")[1]
    _, token = b64decode(t).decode("utf-8").split(":")

    return await get_key_type(r, api_key_header=token)

