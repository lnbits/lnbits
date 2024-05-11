import sys
import traceback
from http import HTTPStatus
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse, Response
from loguru import logger

from lnbits.core.services import InvoiceError, PaymentError

from .helpers import template_renderer


def register_exception_handlers(app: FastAPI):
    register_exception_handler(app)
    register_request_validation_exception_handler(app)
    register_http_exception_handler(app)
    register_payment_error_handler(app)
    register_invoice_error_handler(app)


def render_html_error(request: Request, exc: Exception) -> Optional[Response]:
    # Only the browser sends "text/html" request
    # not fail proof, but everything else get's a JSON response
    if (
        request.headers
        and "accept" in request.headers
        and "text/html" in request.headers["accept"]
    ):
        if (
            isinstance(exc, HTTPException)
            and exc.headers
            and "token-expired" in exc.headers
        ):
            response = RedirectResponse("/")
            response.delete_cookie("cookie_access_token")
            response.delete_cookie("is_lnbits_user_authorized")
            response.set_cookie("is_access_token_expired", "true")
            return response

        return template_renderer().TemplateResponse(
            request, "error.html", {"err": f"Error: {exc!s}"}
        )

    return None


def register_exception_handler(app: FastAPI):
    @app.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        etype, _, tb = sys.exc_info()
        traceback.print_exception(etype, exc, tb)
        logger.error(f"Exception: {exc!s}")
        return render_html_error(request, exc) or JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )


def register_request_validation_exception_handler(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.error(f"RequestValidationError: {exc!s}")
        return render_html_error(request, exc) or JSONResponse(
            status_code=HTTPStatus.BAD_REQUEST,
            content={"detail": str(exc)},
        )


def register_http_exception_handler(app: FastAPI):
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.error(f"HTTPException {exc.status_code}: {exc.detail}")
        return render_html_error(request, exc) or JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )


def register_payment_error_handler(app: FastAPI):
    @app.exception_handler(PaymentError)
    async def payment_error_handler(request: Request, exc: PaymentError):
        logger.error(f"PaymentError: {exc.message}, {exc.status}")
        return JSONResponse(
            status_code=520,
            content={"detail": exc.message, "status": exc.status},
        )


def register_invoice_error_handler(app: FastAPI):
    @app.exception_handler(InvoiceError)
    async def invoice_error_handler(request: Request, exc: InvoiceError):
        logger.error(f"InvoiceError: {exc.message}, Status: {exc.status}")
        return JSONResponse(
            status_code=520,
            content={"detail": exc.message, "status": exc.status},
        )
