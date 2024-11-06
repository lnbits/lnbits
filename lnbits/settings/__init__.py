from __future__ import annotations

import importlib
import importlib.metadata
from hashlib import sha256
from os import path

import httpx
from loguru import logger

from lnbits.settings.auth import AuthMethods
from lnbits.settings.extensions import RedirectPath

from .lnbits import (
    AdminSettings,
    EditableSettings,
    ReadOnlySettings,
    Settings,
    SuperSettings,
    TransientSettings,
    UpdateSettings,
    get_funding_source,
)


def set_cli_settings(**kwargs):
    for key, value in kwargs.items():
        setattr(settings, key, value)


def send_admin_user_to_saas():
    if settings.lnbits_saas_callback:
        with httpx.Client() as client:
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "X-API-KEY": settings.lnbits_saas_secret,
            }
            payload = {
                "instance_id": settings.lnbits_saas_instance_id,
                "adminuser": settings.super_user,
            }
            try:
                client.post(
                    settings.lnbits_saas_callback,
                    headers=headers,
                    json=payload,
                )
                logger.success("sent super_user to saas application")
            except Exception as e:
                logger.error(
                    "error sending super_user to saas:"
                    f" {settings.lnbits_saas_callback}. Error: {e!s}"
                )


readonly_variables = ReadOnlySettings.readonly_fields()
transient_variables = TransientSettings.readonly_fields()

settings = Settings()

settings.lnbits_path = str(path.dirname(path.realpath(__file__)))

settings.version = importlib.metadata.version("lnbits")
settings.auth_secret_key = (
    settings.auth_secret_key or sha256(settings.super_user.encode("utf-8")).hexdigest()
)

if not settings.user_agent:
    settings.user_agent = f"LNbits/{settings.version}"

# printing environment variable for debugging
if not settings.lnbits_admin_ui:
    logger.debug("Environment Settings:")
    for key, value in settings.dict(exclude_none=True).items():
        logger.debug(f"{key}: {value}")


__all__ = [
    "settings",
    # functions
    "set_cli_settings",
    "send_admin_user_to_saas",
    "get_funding_source",
    # settings
    "Settings",
    "AdminSettings",
    "EditableSettings",
    "SuperSettings",
    "UpdateSettings",
    # auth
    "AuthMethods",
    # extensions
    "RedirectPath",
]
