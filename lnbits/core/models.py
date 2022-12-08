import hashlib
import hmac
import json
from sqlite3 import Row
from typing import Dict, List, NamedTuple, Optional

from ecdsa import SECP256k1, SigningKey  # type: ignore
from fastapi import Query
from lnurl import encode as lnurl_encode  # type: ignore
from loguru import logger
from pydantic import BaseModel, Extra, validator

from lnbits.db import Connection
from lnbits.helpers import url_for
from lnbits.settings import get_wallet_class
from lnbits.wallets.base import PaymentStatus


class Wallet(BaseModel):
    id: str
    name: str
    user: str
    adminkey: str
    inkey: str
    balance_msat: int

    @property
    def balance(self) -> int:
        return self.balance_msat // 1000

    @property
    def withdrawable_balance(self) -> int:
        from .services import fee_reserve

        return self.balance_msat - fee_reserve(self.balance_msat)

    @property
    def lnurlwithdraw_full(self) -> str:

        url = url_for("/withdraw", external=True, usr=self.user, wal=self.id)
        try:
            return lnurl_encode(url)
        except:
            return ""

    def lnurlauth_key(self, domain: str) -> SigningKey:
        hashing_key = hashlib.sha256(self.id.encode("utf-8")).digest()
        linking_key = hmac.digest(hashing_key, domain.encode("utf-8"), "sha256")

        return SigningKey.from_string(
            linking_key, curve=SECP256k1, hashfunc=hashlib.sha256
        )

    async def get_payment(self, payment_hash: str) -> Optional["Payment"]:
        from .crud import get_standalone_payment

        return await get_standalone_payment(payment_hash)


class User(BaseModel):
    id: str
    email: Optional[str] = None
    extensions: List[str] = []
    wallets: List[Wallet] = []
    password: Optional[str] = None
    admin: bool = False
    super_user: bool = False

    @property
    def wallet_ids(self) -> List[str]:
        return [wallet.id for wallet in self.wallets]

    def get_wallet(self, wallet_id: str) -> Optional["Wallet"]:
        w = [wallet for wallet in self.wallets if wallet.id == wallet_id]
        return w[0] if w else None


class Payment(BaseModel):
    checking_id: str
    pending: bool
    amount: int
    fee: int
    memo: Optional[str]
    time: int
    bolt11: str
    preimage: str
    payment_hash: str
    extra: Optional[Dict] = {}
    wallet_id: str
    webhook: Optional[str]
    webhook_status: Optional[int]

    @classmethod
    def from_row(cls, row: Row):
        return cls(
            checking_id=row["checking_id"],
            payment_hash=row["hash"] or "0" * 64,
            bolt11=row["bolt11"] or "",
            preimage=row["preimage"] or "0" * 64,
            extra=json.loads(row["extra"] or "{}"),
            pending=row["pending"],
            amount=row["amount"],
            fee=row["fee"],
            memo=row["memo"],
            time=row["time"],
            wallet_id=row["wallet"],
            webhook=row["webhook"],
            webhook_status=row["webhook_status"],
        )

    @property
    def tag(self) -> Optional[str]:
        if self.extra is None:
            return ""
        return self.extra.get("tag")

    @property
    def msat(self) -> int:
        return self.amount

    @property
    def sat(self) -> int:
        return self.amount // 1000

    @property
    def is_in(self) -> bool:
        return self.amount > 0

    @property
    def is_out(self) -> bool:
        return self.amount < 0

    @property
    def is_uncheckable(self) -> bool:
        return self.checking_id.startswith("internal_")

    async def update_status(
        self,
        status: PaymentStatus,
        conn: Optional[Connection] = None,
    ) -> None:
        from .crud import update_payment_details

        await update_payment_details(
            checking_id=self.checking_id,
            pending=status.pending,
            fee=status.fee_msat,
            preimage=status.preimage,
            conn=conn,
        )

    async def set_pending(self, pending: bool) -> None:
        from .crud import update_payment_status

        await update_payment_status(self.checking_id, pending)

    async def check_status(
        self,
        conn: Optional[Connection] = None,
    ) -> PaymentStatus:
        if self.is_uncheckable:
            return PaymentStatus(None)

        logger.debug(
            f"Checking {'outgoing' if self.is_out else 'incoming'} pending payment {self.checking_id}"
        )

        WALLET = get_wallet_class()
        if self.is_out:
            status = await WALLET.get_payment_status(self.checking_id)
        else:
            status = await WALLET.get_invoice_status(self.checking_id)

        logger.debug(f"Status: {status}")

        if self.is_out and status.failed:
            logger.warning(
                f"Deleting outgoing failed payment {self.checking_id}: {status}"
            )
            await self.delete(conn)
        elif not status.pending:
            logger.info(
                f"Marking '{'in' if self.is_in else 'out'}' {self.checking_id} as not pending anymore: {status}"
            )
            await self.update_status(status, conn=conn)
        return status

    async def delete(self, conn: Optional[Connection] = None) -> None:
        from .crud import delete_payment

        await delete_payment(self.checking_id, conn=conn)


class BalanceCheck(BaseModel):
    wallet: str
    service: str
    url: str

    @classmethod
    def from_row(cls, row: Row):
        return cls(wallet=row["wallet"], service=row["service"], url=row["url"])


# admin
# --------
class UpdateSettings(BaseModel, extra=Extra.forbid):
    @validator(
        "lnbits_admin_users",
        "lnbits_allowed_users",
        "lnbits_theme_options",
        "lnbits_disabled_extensions",
        "lnbits_admin_extensions",
        pre=True,
    )
    def validate(cls, val):
        if type(val) == str:
            val = val.split(",") if val else []
        return val

    lnbits_backend_wallet_class: str = Query(None)
    lnbits_admin_users: List[str] = Query(None)
    lnbits_allowed_users: List[str] = Query(None)
    lnbits_admin_extensions: List[str] = Query(None)
    lnbits_disabled_extensions: List[str] = Query(None)
    lnbits_theme_options: List[str] = Query(None)
    lnbits_force_https: bool = Query(None)
    lnbits_reserve_fee_min: int = Query(None, ge=0)
    lnbits_reserve_fee_percent: float = Query(None, ge=0)
    lnbits_service_fee: float = Query(None, ge=0)
    lnbits_hide_api: bool = Query(None)
    lnbits_site_title: str = Query(None)
    lnbits_site_tagline: str = Query(None)
    lnbits_site_description: str = Query(None)
    lnbits_default_wallet_name: str = Query(None)
    lnbits_denomination: str = Query(None)
    lnbits_custom_logo: str = Query(None)
    lnbits_ad_space: str = Query(None)
    lnbits_ad_space_title: str = Query(None)
    lnbits_ad_space_enabled: bool = Query(None)

    # funding sources
    fake_wallet_secret: str = Query(None)
    lnbits_endpoint: str = Query(None)
    lnbits_key: str = Query(None)
    cliche_endpoint: str = Query(None)
    corelightning_rpc: str = Query(None)
    eclair_url: str = Query(None)
    eclair_pass: str = Query(None)
    lnd_rest_endpoint: str = Query(None)
    lnd_rest_cert: str = Query(None)
    lnd_rest_macaroon: str = Query(None)
    lnd_rest_macaroon_encrypted: str = Query(None)
    lnd_cert: str = Query(None)
    lnd_admin_macaroon: str = Query(None)
    lnd_invoice_macaroon: str = Query(None)
    lnd_grpc_endpoint: str = Query(None)
    lnd_grpc_cert: str = Query(None)
    lnd_grpc_port: int = Query(None, ge=0)
    lnd_grpc_admin_macaroon: str = Query(None)
    lnd_grpc_invoice_macaroon: str = Query(None)
    lnd_grpc_macaroon: str = Query(None)
    lnd_grpc_macaroon_encrypted: str = Query(None)
    lnpay_api_endpoint: str = Query(None)
    lnpay_api_key: str = Query(None)
    lnpay_wallet_key: str = Query(None)
    lntxbot_api_endpoint: str = Query(None)
    lntxbot_key: str = Query(None)
    opennode_api_endpoint: str = Query(None)
    opennode_key: str = Query(None)
    spark_url: str = Query(None)
    spark_token: str = Query(None)
    lntips_api_endpoint: str = Query(None)
    lntips_api_key: str = Query(None)
    lntips_admin_key: str = Query(None)
    lntips_invoice_key: str = Query(None)

    boltz_mempool_space_url: str = Query(None)
    boltz_mempool_space_url_ws: str = Query(None)
    boltz_network: str = Query(None)
    boltz_url: str = Query(None)


class SuperSettings(UpdateSettings):
    super_user: str


class AdminSettings(UpdateSettings):
    super_user: bool
    lnbits_allowed_funding_sources: Optional[List[str]]
