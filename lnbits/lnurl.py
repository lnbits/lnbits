from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from lnurl import LnurlErrorResponse, decode, encode, handle
from loguru import logger

from lnbits.exceptions import InvoiceError, PaymentError


class LnurlErrorResponseHandler(APIRoute):
    """
    Custom APIRoute class to handle LNURL errors.
    LNURL errors always return with status 200 and
    a JSON response with `status="ERROR"` and a `reason` key.
    Helps to catch HTTPException and return a valid lnurl error response

    Example:
    withdraw_lnurl_router = APIRouter(prefix="/api/v1/lnurl")
    withdraw_lnurl_router.route_class = LnurlErrorResponseHandler
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def lnurl_route_handler(request: Request) -> Response:
            try:
                response = await original_route_handler(request)
                return response
            except (InvoiceError, PaymentError) as exc:
                logger.debug(f"Wallet Error: {exc}")
                response = JSONResponse(
                    status_code=200,
                    content={"status": "ERROR", "reason": f"{exc.message}"},
                )
                return response
            except HTTPException as exc:
                logger.debug(f"HTTPException: {exc}")
                response = JSONResponse(
                    status_code=200,
                    content={"status": "ERROR", "reason": f"{exc.detail}"},
                )
                return response
            except Exception as exc:
                logger.error("Unknown Error:", exc)
                response = JSONResponse(
                    status_code=200,
                    content={
                        "status": "ERROR",
                        "reason": f"UNKNOWN ERROR: {exc!s}",
                    },
                )
                return response

        return lnurl_route_handler


__all__ = [
    "decode",
    "encode",
    "handle",
    "LnurlErrorResponse",
    "LnurlErrorResponseHandler",
]
