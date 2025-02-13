from cryptography.hazmat.primitives import serialization
from loguru import logger
from py_vapid import Vapid
from py_vapid.utils import b64urlencode

from lnbits.db import dict_to_model
from lnbits.settings import (
    EditableSettings,
    UpdateSettings,
    readonly_variables,
    settings,
)

from ..crud import update_admin_settings


async def check_webpush_settings():
    if not settings.lnbits_webpush_privkey:
        vapid = Vapid()
        vapid.generate_keys()
        privkey = vapid.private_pem()
        assert vapid.public_key, "VAPID public key does not exist"
        pubkey = b64urlencode(
            vapid.public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        push_settings = {
            "lnbits_webpush_privkey": privkey.decode(),
            "lnbits_webpush_pubkey": pubkey,
        }
        update_cached_settings(push_settings)
        if settings.lnbits_admin_ui:
            await update_admin_settings(EditableSettings(**push_settings))

    logger.info("Initialized webpush settings with generated VAPID key pair.")
    logger.info(f"Pubkey: {settings.lnbits_webpush_pubkey}")


def dict_to_settings(sets_dict: dict) -> UpdateSettings:
    return dict_to_model(sets_dict, UpdateSettings)


def update_cached_settings(sets_dict: dict):
    editable_settings = dict_to_settings(sets_dict)
    for key in sets_dict.keys():
        if key in readonly_variables:
            continue
        if key not in settings.dict().keys():
            continue
        try:
            value = getattr(editable_settings, key)
            setattr(settings, key, value)
        except Exception:
            logger.warning(f"Failed overriding setting: {key}.")
    if "super_user" in sets_dict:
        settings.super_user = sets_dict["super_user"]
