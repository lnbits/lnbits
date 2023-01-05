# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here

# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

from . import deezy_ext
from . import db
from .models import (
    Token,
)
from .crud import (
    get_token,
    save_token
)


@deezy_ext.get("/api/v1/token")
async def api_deezy():
    """Get token from table."""
    rows = await get_token()
    return rows


@deezy_ext.post("/api/v1/store-token")
async def api_deezy(data: Token):
    await save_token(data)

    return data.deezy_token
