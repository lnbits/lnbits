import json
import hashlib
import httpx
from urllib.parse import urlparse

from lnbits import bolt11, lnurl
from lnbits.core.services import pay_invoice


async def lnurl_scan(code: str):
    """ Decode given LNURL code, and get callback for creating invoices.
    
    Returns dict(callback, description_hash, min/maxSendable)
    Raises if not payRequest type.

    NOTE: mostly copied logic from core/views/api.py api_lnurlscan()
    """

    url = lnurl.decode(code)

    if "tag=login" in url:
        raise ValueError("Only `payRequest` LNURL supported.")

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=5)
        if r.is_error:
            raise Exception("Failed to get LNURL parameters from {url}")

        data = json.loads(r.text)

        if data["tag"] == "payRequest":
            result = data.copy()

            result.update(
                description_hash=hashlib.sha256(
                    data["metadata"].encode("utf-8")
                ).hexdigest()
            )
            metadata = json.loads(data["metadata"])
            for [k, v] in metadata:
                if k == "text/plain":
                    result.update(description=v)
                if k == "image/jpeg;base64" or k == "image/png;base64":
                    data_uri = "data:" + k + "," + v
                    result.update(image=data_uri)
                if k == "text/email" or k == "text/identifier":
                    result.update(targetUser=v)

            result.update(commentAllowed=data.get("commentAllowed", 0))

            return result

        else:
            raise ValueError("Only `payRequest` LNURL supported.")


async def lnurl_get_invoice(callback, amount_msat, comment, description_hash):
    """ Gets the invoice params, by calling given LNURL callback.
    
    This needs to be called before every payment, to generate new invoice.
    Returns dict(pr=payment request/invoice, successAction)
    Raises if invoice invalid.
    """

    domain = urlparse(callback).netloc
    async with httpx.AsyncClient() as client:
        r = await client.get(
            callback,
            params={"amount": amount_msat, "comment": comment},
            timeout=40,
        )
        if r.is_error:
            raise httpx.ConnectError

    result = json.loads(r.text)
    if result.get("status") == "ERROR":
        raise Exception(f"Failed to get invoice from {domain}: {result.get('reason', '')}")

    invoice = bolt11.decode(result["pr"])

    if invoice.amount_msat != amount_msat:
        raise ValueError(f"{domain} returned an invalid invoice. Expected {amount_msat} msat, got {invoice.amount_msat}.")

    if invoice.description_hash != description_hash:
        raise ValueError(f"{domain} returned an invalid invoice. Expected description_hash == {description_hash}, got {invoice.description_hash}.")

    return result


async def pay_invoice_with_wallet(wallet_id, payment_request, comment=None, success_action=None):
    """ Actually pay given invoice, using given LNBits wallet.

    Returns payment hash.
    """

    extra = {}

    if success_action:
        extra["success_action"] = params["successAction"]
    if comment:
        extra["comment"] = comment

    payment_hash = await pay_invoice(
        wallet_id=wallet_id,
        payment_request=payment_request,
        description="",
        extra=extra,
    )

    return payment_hash


async def execute_lnurl_payment(wallet_id, lnurl_code,  amount_msat, comment=None):
    info = await lnurl_scan(lnurl_code)
    invoice = await lnurl_get_invoice(info["callback"], amount_msat, comment, info["description_hash"])
    payment_hash = await pay_invoice_with_wallet(wallet_id, invoice["pr"], comment)
    return payment_hash
