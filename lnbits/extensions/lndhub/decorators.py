from base64 import b64decode

from fastapi import Request, status
from fastapi.param_functions import Security
from fastapi.security.api_key import APIKeyHeader
from starlette.exceptions import HTTPException

from lnbits.decorators import WalletTypeInfo, get_key_type  # type: ignore

api_key_header_auth = APIKeyHeader(
    name="AUTHORIZATION",
    auto_error=False,
    description="Admin or Invoice key for LNDHub API's",
)


async def check_wallet(
    r: Request, api_key_header_auth: str = Security(api_key_header_auth)
) -> WalletTypeInfo:
    if not api_key_header_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth key"
        )

    t = api_key_header_auth.split(" ")[1]
    _, token = b64decode(t).decode().split(":")

    return await get_key_type(r, api_key_header=token)


async def require_admin_key(
    r: Request, api_key_header_auth: str = Security(api_key_header_auth)
):
    wallet = await check_wallet(r, api_key_header_auth)
    if wallet.wallet_type != 0:
        # If wallet type is not admin then return the unauthorized status
        # This also covers when the user passes an invalid key type
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin key required."
        )
    else:
        return wallet
