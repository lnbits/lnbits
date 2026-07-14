from __future__ import annotations

import json
from typing import Any

from lnurl import LnAddress, Lnurl


def normalize_lnurl(value: str) -> str:
    normalized = value.strip()
    if normalized.lower().startswith("lightning:"):
        normalized = normalized[len("lightning:") :]
    if "@" in normalized:
        normalized = normalized.lower()
    if not normalized:
        raise ValueError("LNURL is required.")
    return normalized


def lnurl_for_core(value: str) -> Lnurl | LnAddress:
    normalized = normalize_lnurl(value)
    if "@" in normalized:
        return LnAddress(normalized)
    return Lnurl(normalized)


def lnurl_payment_amount_for_core(amount: float) -> int:
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return round(amount * 1000)


def lnurl_payment_unit_for_core(currency: str) -> str:
    unit = currency.strip().lower()
    if not unit:
        raise ValueError("Currency is required.")
    if unit in {"sat", "sats"}:
        return "sat"
    return unit.upper()


def lnurl_pay_response_metadata_json(response: Any) -> str:
    metadata = getattr(response, "metadata", None)
    if metadata is None:
        return "[]"

    metadata_list = getattr(metadata, "list", None)
    try:
        if callable(metadata_list):
            return json.dumps(metadata_list())
        return json.dumps(metadata)
    except TypeError:
        return json.dumps(str(metadata))


def lnurl_pay_response_text(response: Any) -> str:
    description = getattr(response, "description", None)
    if description is not None:
        return str(description)

    metadata = getattr(response, "metadata", None)
    text = getattr(metadata, "text", None)
    return str(text) if text is not None else ""


def lnurl_pay_response_int(response: Any, snake_name: str, camel_name: str) -> int:
    value = getattr(response, snake_name, None)
    if value is None:
        value = getattr(response, camel_name, 0)
    return int(value or 0)
