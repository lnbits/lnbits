"""Instance encryption key for server-managed onchain wallets.

Private material is kept outside the settings database. The database pins its
fingerprint so a lost key cannot silently be replaced when restoring an instance.
"""

import base64
import hashlib
import os
import secrets
import tempfile
from pathlib import Path

from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.settings import get_settings_field, set_settings_field
from lnbits.settings import settings

KEY_RECORD = "onchain_key"


class OnchainKeyStatus(BaseModel):
    configured: bool = False
    backup_confirmed: bool = False
    fingerprint: str | None = None
    source: str | None = None
    error: str | None = None


def key_path() -> Path:
    return Path(settings.lnbits_data_folder) / ".onchain_key"


def decode_key(encoded: str) -> bytes:
    try:
        key = base64.b64decode(encoded.strip(), validate=True)
        if len(key) != 32:
            raise ValueError
        return key
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "The onchain encryption key must contain 32 random bytes."
        ) from exc


def key_fingerprint(key: bytes) -> str:
    return hashlib.sha256(key).hexdigest()


def read_onchain_key() -> bytes:
    configured = settings.lnbits_onchain_master_key
    # Compatibility with Watchonly installations configured before core integration.
    encoded = (
        configured.get_secret_value()
        if configured
        else os.getenv("WATCHONLY_MASTER_KEY")
    )
    try:
        stored = decode_key(key_path().read_text()) if key_path().exists() else None
    except OSError as exc:
        raise ValueError("Cannot read the onchain encryption key file.") from exc
    if encoded:
        key = decode_key(encoded)
        if stored is not None and key != stored:
            raise ValueError(
                "The environment key does not match the saved onchain key."
            )
        return key
    if stored is None:
        raise ValueError(
            "Restore the onchain encryption key or complete setup in Payments settings."
        )
    return stored


def _save_key(key: bytes) -> None:
    """Publish a complete mode-0600 file without ever replacing an existing key."""
    target = key_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".onchain-key-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as file:
            file.write(base64.b64encode(key).decode() + "\n")
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if decode_key(target.read_text()) != key:
                raise ValueError(
                    "An onchain key already exists. It cannot be replaced."
                ) from None
        if os.name == "posix":
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


async def onchain_key_status() -> OnchainKeyStatus:
    record = await get_settings_field(KEY_RECORD)
    pinned = (record.value or {}) if record else {}
    status = OnchainKeyStatus(fingerprint=pinned.get("fingerprint"))
    try:
        key = await run_in_threadpool(read_onchain_key)
        fingerprint = key_fingerprint(key)
        if status.fingerprint and fingerprint != status.fingerprint:
            raise ValueError(
                "The onchain encryption key does not match this database. "
                "Restore its original key."
            )
        status.fingerprint = fingerprint
        status.configured = True
        status.backup_confirmed = bool(pinned.get("backup_confirmed"))
        status.source = (
            "environment"
            if settings.lnbits_onchain_master_key or os.getenv("WATCHONLY_MASTER_KEY")
            else "file"
        )
    except ValueError as exc:
        status.error = str(exc)
    return status


async def setup_onchain_key(restore: str | None = None) -> OnchainKeyStatus:
    record = await get_settings_field(KEY_RECORD)
    pinned = (record.value or {}) if record else {}
    if restore is not None:
        key = decode_key(restore)
        if record and pinned.get("fingerprint") != key_fingerprint(key):
            raise ValueError("This recovery key does not match the database.")
        # An operator-managed environment key must agree with a restored file.
        configured = settings.lnbits_onchain_master_key
        encoded = (
            configured.get_secret_value()
            if configured
            else os.getenv("WATCHONLY_MASTER_KEY")
        )
        if encoded and decode_key(encoded) != key:
            raise ValueError(
                "This recovery key does not match the configured environment key."
            )
        await run_in_threadpool(_save_key, key)
    else:
        try:
            key = await run_in_threadpool(read_onchain_key)
        except ValueError:
            if (
                record
                or key_path().exists()
                or settings.lnbits_onchain_master_key
                or os.getenv("WATCHONLY_MASTER_KEY")
            ):
                raise ValueError(
                    "Restore the original onchain key before continuing."
                ) from None
            key = secrets.token_bytes(32)
            await run_in_threadpool(_save_key, key)
    fingerprint = key_fingerprint(key)
    if record and pinned.get("fingerprint") != fingerprint:
        raise ValueError("The onchain encryption key does not match this database.")
    if not record:
        await set_settings_field(
            KEY_RECORD, {"fingerprint": fingerprint, "backup_confirmed": False}
        )
    return await onchain_key_status()


async def confirm_onchain_key_backup(fingerprint: str) -> OnchainKeyStatus:
    status = await setup_onchain_key()
    if not status.configured or status.fingerprint != fingerprint:
        raise ValueError(
            "The backup does not match the current onchain encryption key."
        )
    await set_settings_field(
        KEY_RECORD, {"fingerprint": fingerprint, "backup_confirmed": True}
    )
    return await onchain_key_status()


async def require_onchain_payments() -> None:
    if not settings.lnbits_allow_onchain_payments:
        raise ValueError("Server onchain payments are disabled in Payments settings.")
    status = await onchain_key_status()
    if not status.configured or not status.backup_confirmed:
        raise ValueError(
            "The administrator must set up and back up the onchain "
            "encryption key in Payments settings."
        )
