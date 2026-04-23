import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import httpx
from bolt11 import decode as bolt11_decode
from coincurve.keys import PrivateKey
from embit.bip39 import mnemonic_from_bytes, mnemonic_is_valid
from loguru import logger

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)


class ArkadeSidecarError(Exception):
    pass


class ArkadeNotFoundError(ArkadeSidecarError):
    pass


class ArkadeWallet(Wallet):
    """
    Arkade funding source via a local sidecar service.
    """

    def __init__(self):
        self._status = "Initializing"
        self._sidecar_path = Path(settings.lnbits_data_folder, "arkade")

        self.pending_invoices: list[str] = []

        self.endpoint = "http://127.0.0.1:8765"
        self._api_key = uuid.uuid4().hex

        sidecar_url = settings.arkade_sidecar_url or settings.arkade_external_endpoint
        if sidecar_url:
            self.endpoint = normalize_endpoint(cast(str, sidecar_url))
            logger.info(f"Using external Arkade sidecar endpoint: {self.endpoint}")
        else:
            logger.error("No Arkade sidecar endpoint configuration found.")

        api_key = settings.arkade_sidecar_api_key or settings.arkade_external_api_key
        if api_key:
            self._api_key = cast(str, api_key)
            logger.info("Using external Arkade sidecar API.")
        else:
            logger.warning("No Arkade sidecar API key configured.")

        headers = {"User-Agent": settings.user_agent, "X-Api-Key": self._api_key}

        self.client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers=headers,
            timeout=60,
        )

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def status(self) -> StatusResponse:
        try:
            res = await self._request("POST", "/v1/balance")
            logger.debug(f"Arkade sidecar balance response: {res}")
            status = res.get("status")
            if status == "missing_mnemonic":
                await self._check_sidecar_mnemonic()
                return StatusResponse("Arkade sidecar mnemonic not set", 0)

            balance_msat = res.get("balance_msat")
            if balance_msat is not None:
                return StatusResponse(None, int(balance_msat))
            balance_sats = res.get("balance_sats")
            if balance_sats is None:
                return StatusResponse("Arkade sidecar: missing balance.", 0)
            return StatusResponse(None, int(balance_sats) * 1000)
        except Exception as e:
            logger.warning(f"Arkade sidecar status error: {e}")
            return StatusResponse(f"Arkade sidecar status error: {e}", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,
        **kwargs,
    ) -> InvoiceResponse:
        expiry = kwargs.get("expiry")
        expiry_secs = int(expiry) if expiry else None

        description_hash_hex = None
        if description_hash:
            description_hash_hex = description_hash.hex()
        elif unhashed_description:
            description_hash_hex = hashlib.sha256(unhashed_description).hexdigest()

        try:
            payload = {
                "amount_sats": int(amount),
                "memo": (memo or "") if not description_hash_hex else None,
                "description_hash": description_hash_hex,
                "expiry_seconds": expiry_secs,
            }
            res = await self._request("POST", "/v1/invoices", payload)
            bolt11 = res.get("payment_request")
            checking_id = res.get("checking_id")
            if not bolt11 or not checking_id:
                return InvoiceResponse(
                    ok=False,
                    error_message="Arkade sidecar invoice response missing fields.",
                )
            self.pending_invoices.append(checking_id)

            return InvoiceResponse(
                ok=True,
                payment_request=bolt11,
                checking_id=checking_id,
                preimage=res.get("preimage", None),
            )
        except Exception as e:
            return InvoiceResponse(ok=False, error_message=str(e))

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            bolt11 = bolt11.removeprefix("lightning:").removeprefix("LIGHTNING:")
            max_fee_sats = (int(fee_limit_msat) + 999) // 1000
            logger.info(
                f"Paying invoice via Arkade sidecar with max fee {max_fee_sats} sats."
            )

            payment_hash = None
            try:
                payment_hash = bolt11_decode(bolt11).payment_hash
            except Exception as exc:
                logger.warning(exc)
                payment_hash = None

            payload = {
                "bolt11": bolt11,
                "max_fee_sats": max_fee_sats,
                "payment_hash": payment_hash,
            }
            res = await self._request("POST", "/v1/payments", payload)
            checking_id = payment_hash or res.get("checking_id")
            if not checking_id:
                return PaymentResponse(
                    ok=False,
                    error_message="Arkade sidecar payment response missing checking_id.",
                )
            status = res.get("status")
            fee_msat = res.get("fee_msat")
            ok = None
            if status:
                ok = self._map_payment_ok(status)
            return PaymentResponse(
                ok=ok,
                checking_id=checking_id,
                fee_msat=int(fee_msat) if fee_msat is not None else None,
                preimage=res.get("preimage"),
            )
        except Exception as e:
            return PaymentResponse(ok=False, error_message=str(e))

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            res = await self._request("GET", f"/v1/invoices/{checking_id}")
            status = res.get("status")
            if not status:
                return PaymentPendingStatus()
            return self._map_invoice_status(status)
        except ArkadeNotFoundError:
            return PaymentFailedStatus()
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        try:
            res = await self._request("GET", f"/v1/payments/{checking_id}")
            status = res.get("status")
            fee_msat = res.get("fee_msat")
            preimage = res.get("preimage")
            if not status:
                return PaymentPendingStatus()
            mapped = self._map_payment_status(status)
            if mapped.success:
                return PaymentSuccessStatus(
                    fee_msat=int(fee_msat) if fee_msat is not None else None,
                    preimage=preimage,
                )
            if mapped.failed:
                return PaymentFailedStatus()
            return PaymentPendingStatus()
        except ArkadeNotFoundError:
            return PaymentFailedStatus()
        except Exception as exc:
            logger.warning(exc)
            return PaymentPendingStatus()

    async def get_ark_address(self) -> str | None:
        try:
            res = await self._request("GET", "/v1/address")
            return res.get("ark_address") or res.get("address")
        except Exception as exc:
            logger.warning(f"Unable to fetch Arkade receive address: {exc}")
            return None

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        stream_path = "/v1/invoices/stream"
        while settings.lnbits_running:
            try:
                async with self.client.stream("GET", stream_path, timeout=None) as r:
                    if r.status_code in {404, 405}:
                        logger.warning(
                            "Arkade sidecar invoice stream not available, "
                            "falling back to polling."
                        )
                        async for checking_id in self._poll_pending_invoices():
                            yield checking_id
                        return
                    r.raise_for_status()
                    logger.info("connected to Arkade sidecar invoice stream.")
                    async for line in r.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = json.loads(line[5:].strip())
                        checking_id = data.get("checking_id")
                        if checking_id:
                            yield checking_id
            except Exception as exc:
                logger.error(
                    "lost connection to Arkade sidecar invoice stream: "
                    f"'{exc}' retrying in 5 seconds"
                )
                await asyncio.sleep(5)

    async def _request(
        self, method: str, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self.client.request(
                method, path, json=json_data, timeout=30
            )
            payload = response.json()
        except (httpx.RequestError, json.JSONDecodeError) as exc:
            raise ArkadeSidecarError(
                f"Arkade sidecar request error: '{exc}'"
            ) from exc

        response_body = payload.get("response", payload)
        if not isinstance(response_body, dict):
            raise ArkadeSidecarError("Arkade sidecar response missing 'response' body.")

        error_message = response_body.get("error")

        if response.status_code == 404:
            raise ArkadeNotFoundError(error_message or "Not found")

        if response.is_error:
            raise ArkadeSidecarError(
                error_message
                or f"Arkade sidecar request failed with status {response.status_code}."
            )

        if error_message:
            raise ArkadeSidecarError(error_message)

        return response_body

    async def _poll_pending_invoices(self) -> AsyncGenerator[str, None]:
        while settings.lnbits_running:
            for invoice in list(self.pending_invoices):
                try:
                    status = await self.get_invoice_status(invoice)
                    if status.paid:
                        yield invoice
                        self.pending_invoices.remove(invoice)
                    elif status.failed:
                        self.pending_invoices.remove(invoice)
                except Exception as exc:
                    logger.error(f"could not get status of invoice {invoice}: '{exc}' ")
            await asyncio.sleep(5)

    def _map_invoice_status(self, status: str) -> PaymentStatus:
        success = {
            "LIGHTNING_PAYMENT_RECEIVED",
            "TRANSFER_COMPLETED",
            "PAYMENT_PREIMAGE_RECOVERED",
        }
        failed = {
            "TRANSFER_FAILED",
            "PAYMENT_PREIMAGE_RECOVERING_FAILED",
            "REFUND_SIGNING_FAILED",
            "REFUND_SIGNING_COMMITMENTS_QUERYING_FAILED",
            "TRANSFER_CREATION_FAILED",
        }
        if status in success:
            return PaymentSuccessStatus()
        if status in failed:
            return PaymentFailedStatus()
        return PaymentPendingStatus()

    def _map_payment_status(self, status: str) -> PaymentStatus:
        success = {
            "LIGHTNING_PAYMENT_SUCCEEDED",
            "TRANSFER_COMPLETED",
            "PREIMAGE_PROVIDED",
        }
        failed = {
            "LIGHTNING_PAYMENT_FAILED",
            "TRANSFER_FAILED",
            "PREIMAGE_PROVIDING_FAILED",
            "USER_TRANSFER_VALIDATION_FAILED",
            "USER_SWAP_RETURN_FAILED",
        }
        if status in success:
            return PaymentSuccessStatus()
        if status in failed:
            return PaymentFailedStatus()
        return PaymentPendingStatus()

    def _map_payment_ok(self, status: str) -> bool | None:
        mapped = self._map_payment_status(status)
        if mapped.success:
            return True
        if mapped.failed:
            return False
        return None

    async def _check_sidecar_mnemonic(self):
        if settings.arkade_mnemonic:
            valid = mnemonic_is_valid(settings.arkade_mnemonic)
            if not valid:
                logger.warning("ARKADE_MNEMONIC is set but invalid. Please recheck!")
                return
            await self._set_sidecar_mnemonic(settings.arkade_mnemonic)
            return

        logger.info("ARKADE_MNEMONIC is not set, one will be generated for you.")
        mnemonic = mnemonic_from_bytes(PrivateKey().secret)
        await self._set_sidecar_mnemonic(mnemonic)

    async def _set_sidecar_mnemonic(self, mnemonic: str):
        logger.info("Checking 'ARKADE_MNEMONIC' on the Arkade sidecar.")
        resp = await self._request("POST", "/v1/mnemonic", {"mnemonic": mnemonic})
        status = resp.get("status")
        logger.info(f"Arkade sidecar mnemonic status: {status}")
        if status == "set":
            logger.info("Updating 'ARKADE_MNEMONIC' mnemonic settings.")
            from lnbits.core.crud.settings import set_settings_field

            await set_settings_field("arkade_mnemonic", mnemonic)
        else:
            logger.info("Nothing to do for 'ARKADE_MNEMONIC' on the Arkade sidecar.")
