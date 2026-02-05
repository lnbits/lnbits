import asyncio
import hashlib
import json
import shutil
import subprocess
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import httpx
from bolt11 import decode as bolt11_decode
from coincurve.keys import PrivateKey
from embit.bip39 import mnemonic_from_bytes, mnemonic_is_valid
from loguru import logger

from lnbits.helpers import download_url, normalize_endpoint
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


class SparkSidecarError(Exception):
    pass


class LightsparkSparkWallet(Wallet):
    """
    Spark L2 funding source via a local sidecar service.

    Required settings/env:
      - SPARK_L2_ENDPOINT (default http://127.0.0.1:8765)
    Optional:
      - SPARK_L2_API_KEY
    """

    def __init__(self):
        self._status = "Initializing"
        self._sidecar_path = Path(settings.lnbits_data_folder, "light_spark")

        self.pending_invoices: list[str] = []

        self.endpoint = "http://127.0.0.1:8765"
        self._api_key = uuid.uuid4().hex
        if settings.spark_l2_internal_sidecar_version:
            self._sidecar_version = settings.spark_l2_internal_sidecar_version
            self.sidecar_task = asyncio.create_task(self._start_sidecar())
            logger.info(f"Internal Spark sidecar ({self._sidecar_version}).")
        elif settings.spark_l2_external_endpoint:
            self.endpoint = normalize_endpoint(
                cast(str, settings.spark_l2_external_endpoint)
            )
            self._api_key = settings.spark_l2_external_api_key
            logger.info(f"Using external Spark sidecar endpoint: {self.endpoint}")
        else:
            logger.error(
                "No Spark sidecar configuration found. Please set either "
                "spark_l2_internal_sidecar_version or spark_l2_external_endpoint."
            )

        headers = {"User-Agent": settings.user_agent, "X-Api-Key": self._api_key}

        self.client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers=headers,
            timeout=60,
        )

    async def _start_sidecar(self):
        logger.info("Starting Spark sidecar")
        npm_path = shutil.which("npm")
        if not npm_path:
            logger.error("npm not found in PATH, cannot start Spark sidecar")
            return
        logger.info(f"npm found: {npm_path}")

        repo, branch = "spark_sidecar", "main"

        node_modules_path = Path(self._sidecar_path, f"{repo}-{branch}")
        if not Path(self._sidecar_path, "package.json").is_file():
            logger.info("⏳ Downloading Spark sidecar.")
            await asyncio.to_thread(
                download_url,
                f"https://github.com/lnbits/{repo}/archive/refs/heads/{branch}.zip",
                Path(self._sidecar_path, f"{repo}.zip"),
            )
            logger.info("✅ Downloaded Spark sidecar.")
            logger.info("⏳ Extracting Spark sidecar.")
            shutil.unpack_archive(
                Path(self._sidecar_path, f"{repo}.zip"),
                self._sidecar_path,
            )
            logger.info("✅ Extracted Spark sidecar.")
            # todo: remove zip


        if not Path(self._sidecar_path, node_modules_path, "node_modules").is_dir():
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(node_modules_path),
                capture_output=True,
                text=True,
                check=True, # raises an exception if npm fails
            )
            print("### npm install output:")
            print(result.stdout)
            print(result.stderr)

        print("### Starting Spark sidecar node server")
        result = subprocess.run(
            ["node", "server.mjs"],
            cwd=str(node_modules_path),
            capture_output=True,
            text=True,
            # check=True, # raises an exception if node fails
        )

        print("### Spark sidecar output:")
        print(result.stdout)
        print(result.stderr)

    async def cleanup(self):
        try:
            await self.client.aclose()
            self.sidecar_task.cancel()
        except RuntimeError as e:
            logger.warning(f"Error closing wallet connection: {e}")

    async def _request(
        self, method: str, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        error_message = None
        try:
            r = await self.client.request(method, path, json=json_data)
            r.raise_for_status()
            j = r.json()
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                try:
                    error_json = exc.response.json()
                    if "error" in error_json:
                        error_message = error_json["error"]
                except Exception as json_exc:
                    logger.error(
                        f"Failed to parse Spark error response as JSON: {json_exc}"
                    )
            raise SparkSidecarError(
                error_message or f"Spark sidecar request error: '{exc}'"
            ) from exc

        if error_message or j.get("error"):
            raise SparkSidecarError(
                error_message or f"Spark sidecar error: {j['error']}"
            )
        return j

    async def status(self) -> StatusResponse:
        try:
            res = await self._request("POST", "/v1/balance")
            balance_msat = res.get("balance_msat")
            if balance_msat is not None:
                return StatusResponse(None, int(balance_msat))
            balance_sats = res.get("balance_sats")
            if balance_sats is None:
                return StatusResponse("Spark sidecar: missing balance.", 0)
            return StatusResponse(None, int(balance_sats) * 1000)
        except Exception as e:
            return StatusResponse(f"Spark sidecar status error: {e}", 0)

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
                raise SparkSidecarError(
                    "Spark sidecar invoice response missing fields."
                )
            self.pending_invoices.append(checking_id)

            return InvoiceResponse(
                ok=True,
                payment_request=bolt11,
                checking_id=checking_id,
                preimage=res.get("preimage"),
            )
        except Exception as e:
            return InvoiceResponse(ok=False, error_message=str(e))

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            max_fee_sats = (int(fee_limit_msat) + 999) // 1000

            payment_hash = None
            try:
                payment_hash = bolt11_decode(bolt11).payment_hash
            except Exception:
                payment_hash = None
            payload = {
                "bolt11": bolt11,
                "max_fee_sats": max_fee_sats,
                "payment_hash": payment_hash,
            }
            res = await self._request("POST", "/v1/payments", payload)
            checking_id = payment_hash or res.get("checking_id")
            if not checking_id:
                raise SparkSidecarError(
                    "Spark sidecar payment response missing checking_id."
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
        except Exception:
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
        except Exception:
            return PaymentPendingStatus()

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

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        stream_path = "/v1/invoices/stream"
        while settings.lnbits_running:
            try:
                async with self.client.stream("GET", stream_path, timeout=None) as r:
                    if r.status_code in {404, 405}:
                        logger.warning(
                            "Spark sidecar invoice stream not available, "
                            "falling back to polling."
                        )
                        async for checking_id in self._poll_pending_invoices():
                            yield checking_id
                        return
                    r.raise_for_status()
                    logger.info("connected to Spark sidecar invoice stream.")
                    async for line in r.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = json.loads(line[5:].strip())
                        checking_id = data.get("checking_id")
                        if not checking_id:
                            continue
                        yield checking_id
            except Exception as exc:
                logger.error(
                    "lost connection to Spark sidecar invoice stream: "
                    f"'{exc}' retrying in 5 seconds"
                )
                await asyncio.sleep(5)

    async def _start_sidecar(self):
        logger.info("Starting Spark sidecar")
        node_path = shutil.which("node")
        if not node_path:
            logger.error("Node.js not found in PATH, cannot start Spark sidecar")
            return
        logger.info(f"Node.js found: {node_path}")

        repo, version = "spark_sidecar", self._sidecar_version
        node_modules_path = Path(self._sidecar_path, f"{repo}-{version}")
        await self._prepare_sidecar(repo, version, node_modules_path)

        await self._start_sidecar_process(node_path, node_modules_path)

    async def _prepare_sidecar(self, repo: str, version: str, node_modules_path: Path):
        if not Path(node_modules_path, "package.json").is_file():
            await self._download_sidecar(repo, version)
        else:
            logger.info("Spark sidecar already downloaded.")

        if not Path(node_modules_path, "node_modules").is_dir():
            self._install_sidecar_packages(node_modules_path)
        else:
            logger.info("Spark sidecar npm dependencies already installed.")

    def _install_sidecar_packages(self, node_modules_path: Path):
        logger.info(f"Installing Spark sidecar npm dependencies {node_modules_path}")
        npm_path = shutil.which("npm")
        if not npm_path:
            logger.error("npm not found in PATH, cannot start Spark sidecar")
            return
        logger.info(f"npm found: {npm_path}")

        result = subprocess.run(  # noqa: S603
            [npm_path, "install"],
            cwd=str(node_modules_path),
            capture_output=True,
            text=True,
            shell=False,
            check=True,  # raises an exception if npm fails
        )
        logger.info("Spark sidecar npm dependencies installed.")
        logger.info("npm install output:")
        logger.info(result.stdout)
        logger.error(result.stderr)

    async def _check_mnemonic(self):
        if settings.spark_l2_mnemonic and len(settings.spark_l2_mnemonic) > 0:
            valid = mnemonic_is_valid(settings.spark_l2_mnemonic)
            if not valid:
                logger.warning("SPARK_L2_MNEMONIC is set but invalid. Please recheck!")

            return

        logger.info("SPARK_L2_MNEMONIC is not set, generating random mnemonic.")

        words = mnemonic_from_bytes(PrivateKey().secret)
        settings.spark_l2_mnemonic = words
        from lnbits.core.crud.settings import set_settings_field

        await set_settings_field("spark_l2_mnemonic", words)

    async def _start_sidecar_process(self, node_path: str, node_modules_path: Path):
        logger.info("Starting Spark sidecar node process.")

        await self._check_mnemonic()

        env = {
            "SPARK_NETWORK": settings.spark_l2_network,
            "SPARK_SIDECAR_API_KEY": self._api_key or "",
            "SPARK_PAY_WAIT_MS": str(settings.spark_l2_pay_wait_ms),
            "SPARK_MNEMONIC": str(settings.spark_l2_mnemonic),
        }

        process = subprocess.Popen(  # noqa: S603
            [node_path, "server.mjs"],
            env=env,
            cwd=str(node_modules_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            text=True,
        )

        logger.info("Started Spark sidecar node process.")
        await asyncio.to_thread(self._log_process_output, process)

    async def _download_sidecar(self, repo: str, version: str):
        zip_path = Path(self._sidecar_path, f"{repo}.zip")
        logger.info(f"⏳ Downloading Spark sidecar to {zip_path}")
        Path(zip_path).parent.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(
            download_url,
            f"https://github.com/lnbits/{repo}/archive/refs/tags/v{version}.zip",
            zip_path,
        )
        logger.info("✅ Downloaded Spark sidecar.")

        logger.info("⏳ Extracting Spark sidecar.")

        shutil.unpack_archive(
            zip_path,
            self._sidecar_path,
        )
        logger.info("✅ Extracted Spark sidecar.")
        shutil.rmtree(zip_path, ignore_errors=True)
        # todo: remove zip

    def _log_process_output(self, process: subprocess.Popen):
        if process.stdout:
            for line in process.stdout:
                logger.info(f"[Lightspark]: {line}", end="")
        else:
            logger.error(" No output captured for Spark sidecar.")
