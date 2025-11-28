from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import json
import os
import re
from datetime import datetime, timezone
from enum import Enum
from os import path
from pathlib import Path
from time import gmtime, strftime, time
from typing import Any
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, BaseSettings, Extra, Field, validator


def list_parse_fallback(v: str):
    v = v.replace(" ", "")
    if len(v) > 0:
        if v.startswith("[") or v.startswith("{"):
            return json.loads(v)
        else:
            return v.split(",")
    else:
        return []


class LNbitsSettings(BaseModel):
    @classmethod
    def validate_list(cls, val):
        if isinstance(val, str):
            val = val.split(",") if val else []
        return val


class UsersSettings(LNbitsSettings):
    lnbits_admin_users: list[str] = Field(default=[])
    lnbits_allowed_users: list[str] = Field(default=[])
    lnbits_allow_new_accounts: bool = Field(default=True)

    @property
    def new_accounts_allowed(self) -> bool:
        return self.lnbits_allow_new_accounts and len(self.lnbits_allowed_users) == 0


class ExtensionsSettings(LNbitsSettings):
    lnbits_admin_extensions: list[str] = Field(default=[])
    lnbits_user_default_extensions: list[str] = Field(default=[])
    lnbits_extensions_deactivate_all: bool = Field(default=False)
    lnbits_extensions_builder_activate_non_admins: bool = Field(default=False)
    lnbits_extensions_manifests: list[str] = Field(
        default=[
            "https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json"
        ]
    )
    lnbits_extensions_builder_manifest_url: str = Field(
        default="https://raw.githubusercontent.com/lnbits/extension_builder_stub/refs/heads/main/manifest.json"
    )

    @property
    def extension_builder_working_dir_path(self) -> Path:
        return Path(settings.lnbits_data_folder, "extensions_builder")


class ExtensionsInstallSettings(LNbitsSettings):
    lnbits_extensions_default_install: list[str] = Field(default=[])
    # required due to GitHUb rate-limit
    lnbits_ext_github_token: str = Field(default="")


class RedirectPath(BaseModel):
    ext_id: str
    from_path: str
    redirect_to_path: str
    header_filters: dict = {}

    def in_conflict(self, other: RedirectPath) -> bool:
        if self.ext_id == other.ext_id:
            return False
        return self.redirect_matches(
            other.from_path, list(other.header_filters.items())
        ) or other.redirect_matches(self.from_path, list(self.header_filters.items()))

    def find_in_conflict(self, others: list[RedirectPath]) -> RedirectPath | None:
        for other in others:
            if self.in_conflict(other):
                return other
        return None

    def new_path_from(self, req_path: str) -> str:
        from_path = self.from_path.split("/")
        redirect_to = self.redirect_to_path.split("/")
        req_tail_path = req_path.split("/")[len(from_path) :]

        elements = [e for e in ([self.ext_id, *redirect_to, *req_tail_path]) if e != ""]

        return "/" + "/".join(elements)

    def redirect_matches(self, path: str, req_headers: list[tuple[str, str]]) -> bool:
        return self._has_common_path(path) and self._has_headers(req_headers)

    def _has_common_path(self, req_path: str) -> bool:
        if len(self.from_path) > len(req_path):
            return False

        redirect_path_elements = self.from_path.split("/")
        req_path_elements = req_path.split("/")

        sub_path = req_path_elements[: len(redirect_path_elements)]
        return self.from_path == "/".join(sub_path)

    def _has_headers(self, req_headers: list[tuple[str, str]]) -> bool:
        for h in self.header_filters:
            if not self._has_header(req_headers, (str(h), str(self.header_filters[h]))):
                return False
        return True

    def _has_header(
        self, req_headers: list[tuple[str, str]], header: tuple[str, str]
    ) -> bool:
        for h in req_headers:
            if h[0].lower() == header[0].lower() and h[1].lower() == header[1].lower():
                return True
        return False


class ExchangeRateProvider(BaseModel):
    name: str
    api_url: str
    path: str
    exclude_to: list[str] = []
    ticker_conversion: list[str] = []

    def convert_ticker(self, currency: str) -> str:
        if not self.ticker_conversion:
            return currency
        try:
            for t in self.ticker_conversion:
                _from, _to = t.split(":")
                if _from == currency:
                    return _to
        except Exception as err:
            logger.warning(err)
        return currency


class InstalledExtensionsSettings(LNbitsSettings):
    # installed extensions that have been deactivated
    lnbits_deactivated_extensions: set[str] = Field(default=set())
    # upgraded extensions that require API redirects
    lnbits_upgraded_extensions: dict[str, str] = Field(default={})
    # list of redirects that extensions want to perform
    lnbits_extensions_redirects: list[RedirectPath] = Field(default=[])

    # list of all extension ids
    lnbits_installed_extensions_ids: set[str] = Field(default=set())

    def find_extension_redirect(
        self, path: str, req_headers: list[tuple[bytes, bytes]]
    ) -> RedirectPath | None:
        headers = [(k.decode(), v.decode()) for k, v in req_headers]
        return next(
            (
                r
                for r in self.lnbits_extensions_redirects
                if r.redirect_matches(path, headers)
            ),
            None,
        )

    def activate_extension_paths(
        self,
        ext_id: str,
        upgrade_hash: str | None = None,
        ext_redirects: list[dict] | None = None,
    ):
        self.lnbits_deactivated_extensions.discard(ext_id)

        """
        Update the list of upgraded extensions. The middleware will perform
        redirects based on this
        """
        if upgrade_hash:
            self.lnbits_upgraded_extensions[ext_id] = upgrade_hash

        if ext_redirects:
            self._activate_extension_redirects(ext_id, ext_redirects)

        self.lnbits_installed_extensions_ids.add(ext_id)

    def deactivate_extension_paths(self, ext_id: str):
        self.lnbits_deactivated_extensions.add(ext_id)
        self._remove_extension_redirects(ext_id)

    def extension_upgrade_hash(self, ext_id: str) -> str:
        return settings.lnbits_upgraded_extensions.get(ext_id, "")

    def _activate_extension_redirects(self, ext_id: str, ext_redirects: list[dict]):
        ext_redirect_paths = [
            RedirectPath(**{"ext_id": ext_id, **er}) for er in ext_redirects
        ]
        existing_redirects = {
            r.ext_id
            for r in self.lnbits_extensions_redirects
            if r.find_in_conflict(ext_redirect_paths)
        }

        if len(existing_redirects) != 0:
            raise ValueError(
                f"Cannot redirect for extension '{ext_id}'."
                f" Already mapped by {existing_redirects}."
            )

        self._remove_extension_redirects(ext_id)
        self.lnbits_extensions_redirects += ext_redirect_paths

    def _remove_extension_redirects(self, ext_id: str):
        self.lnbits_extensions_redirects = [
            er for er in self.lnbits_extensions_redirects if er.ext_id != ext_id
        ]


class ExchangeHistorySettings(LNbitsSettings):
    lnbits_exchange_rate_history: list[dict] = Field(default=[])

    def append_exchange_rate_datapoint(self, rates: dict, max_size: int):
        data = {
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "rates": rates,
        }
        self.lnbits_exchange_rate_history.append(data)
        if len(self.lnbits_exchange_rate_history) > max_size:
            self.lnbits_exchange_rate_history.pop(0)


class ThemesSettings(LNbitsSettings):
    lnbits_site_title: str = Field(default="LNbits")
    lnbits_site_tagline: str = Field(default="free and open-source lightning wallet")
    lnbits_site_description: str | None = Field(
        default="The world's most powerful suite of bitcoin tools."
    )
    lnbits_show_home_page_elements: bool = Field(default=True)
    lnbits_default_wallet_name: str = Field(default="LNbits wallet")
    lnbits_custom_badge: str | None = Field(default=None)
    lnbits_custom_badge_color: str = Field(default="warning")
    lnbits_theme_options: list[str] = Field(
        default=[
            "classic",
            "freedom",
            "mint",
            "salvador",
            "monochrome",
            "autumn",
            "cyber",
            "flamingo",
            "bitcoin",
        ]
    )
    lnbits_custom_logo: str | None = Field(default=None)
    lnbits_custom_image: str | None = Field(default="/static/images/logos/lnbits.svg")
    lnbits_ad_space_title: str = Field(default="Supported by")
    lnbits_ad_space: str = Field(
        default="https://shop.lnbits.com/;/static/images/bitcoin-shop-banner.png;/static/images/bitcoin-shop-banner.png,https://affil.trezor.io/aff_c?offer_id=169&aff_id=33845;/static/images/bitcoin-hardware-wallet.png;/static/images/bitcoin-hardware-wallet.png,https://firefish.io/?ref=lnbits;/static/images/firefish.png;/static/images/firefish.png,https://opensats.org/;/static/images/open-sats.png;/static/images/open-sats.png"
    )  # sneaky sneaky
    lnbits_ad_space_enabled: bool = Field(default=False)
    lnbits_allowed_currencies: list[str] = Field(default=[])
    lnbits_default_accounting_currency: str | None = Field(default=None)
    lnbits_qr_logo: str = Field(default="/static/images/favicon_qr_logo.png")
    lnbits_default_reaction: str = Field(default="confettiBothSides")
    lnbits_default_theme: str = Field(default="salvador")
    lnbits_default_border: str = Field(default="hard-border")
    lnbits_default_gradient: bool = Field(default=True)
    lnbits_default_bgimage: str | None = Field(default=None)


class OpsSettings(LNbitsSettings):
    lnbits_baseurl: str = Field(default="http://127.0.0.1:5000/")
    lnbits_hide_api: bool = Field(default=False)


class AssetSettings(LNbitsSettings):
    lnbits_max_asset_size_mb: float = Field(default=2.5, ge=0.0)
    lnbits_assets_allowed_mime_types: list[str] = Field(
        default=[
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/heic",
            "image/heif",
            "image/heics",
            "png",
            "jpeg",
            "jpg",
            "heic",
            "heif",
            "heics",
        ]
    )
    lnbits_asset_thumbnail_width: int = Field(default=128, ge=0)
    lnbits_asset_thumbnail_height: int = Field(default=128, ge=0)
    lnbits_asset_thumbnail_format: str = Field(default="png")

    lnbits_max_assets_per_user: int = Field(default=1, ge=0)
    lnbits_assets_no_limit_users: list[str] = Field(default=[])


class FeeSettings(LNbitsSettings):
    lnbits_reserve_fee_min: int = Field(default=2000, ge=0)
    lnbits_reserve_fee_percent: float = Field(default=1.0, ge=0)
    lnbits_service_fee: float = Field(default=0, ge=0)
    lnbits_service_fee_ignore_internal: bool = Field(default=True)
    lnbits_service_fee_max: int = Field(default=0)
    lnbits_service_fee_wallet: str | None = Field(default=None)

    # WARN: this same value must be used for balance check and passed to
    # funding_source.pay_invoice(), it may cause a vulnerability if the values differ
    def fee_reserve(self, amount_msat: int, internal: bool = False) -> int:
        if internal:
            return 0
        reserve_min = self.lnbits_reserve_fee_min
        reserve_percent = self.lnbits_reserve_fee_percent
        return max(int(reserve_min), int(abs(amount_msat) * reserve_percent / 100.0))


class ExchangeProvidersSettings(LNbitsSettings):
    lnbits_exchange_rate_cache_seconds: int = Field(default=30, ge=0)
    lnbits_exchange_history_size: int = Field(default=60, ge=0)
    lnbits_exchange_history_refresh_interval_seconds: int = Field(default=300, ge=0)

    lnbits_exchange_rate_providers: list[ExchangeRateProvider] = Field(
        default=[
            ExchangeRateProvider(
                name="Binance",
                api_url="https://api.binance.com/api/v3/ticker/price?symbol=BTC{TO}",
                path="$.price",
                exclude_to=["czk"],
                ticker_conversion=["USD:USDT"],
            ),
            ExchangeRateProvider(
                name="Blockchain",
                api_url="https://blockchain.info/frombtc?currency={TO}&value=100000000",
                path="",
                exclude_to=[],
                ticker_conversion=[],
            ),
            ExchangeRateProvider(
                name="Exir",
                api_url="https://api.exir.io/v1/ticker?symbol=btc-{to}",
                path="$.last",
                exclude_to=["czk", "eur"],
                ticker_conversion=["USD:USDT"],
            ),
            ExchangeRateProvider(
                name="Bitfinex",
                api_url="https://api.bitfinex.com/v1/pubticker/btc{to}",
                path="$.last_price",
                exclude_to=["czk"],
                ticker_conversion=[],
            ),
            ExchangeRateProvider(
                name="Bitstamp",
                api_url="https://www.bitstamp.net/api/v2/ticker/btc{to}/",
                path="$.last",
                exclude_to=["czk"],
                ticker_conversion=[],
            ),
            ExchangeRateProvider(
                name="Coinbase",
                api_url="https://api.coinbase.com/v2/exchange-rates?currency=BTC",
                path="$.data.rates.{TO}",
                exclude_to=[],
                ticker_conversion=[],
            ),
            ExchangeRateProvider(
                name="Kraken",
                api_url="https://api.kraken.com/0/public/Ticker?pair=XBT{TO}",
                path="$.result.XXBTZ{TO}.c[0]",
                exclude_to=["czk"],
                ticker_conversion=[],
            ),
            ExchangeRateProvider(
                name="yadio",
                api_url="https://api.yadio.io/exrates/BTC",
                path="$.BTC.{TO}",
                exclude_to=[],
                ticker_conversion=[],
            ),
        ]
    )


class SecuritySettings(LNbitsSettings):
    lnbits_rate_limit_no: int = Field(default=200, ge=0)
    lnbits_rate_limit_unit: str = Field(default="minute")
    lnbits_allowed_ips: list[str] = Field(default=[])
    lnbits_blocked_ips: list[str] = Field(default=[])
    lnbits_callback_url_rules: list[str] = Field(
        default=["https?://([a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})(:\\d+)?"]
    )

    lnbits_wallet_limit_max_balance: int = Field(default=0, ge=0)
    lnbits_wallet_limit_daily_max_withdraw: int = Field(default=0, ge=0)
    lnbits_wallet_limit_secs_between_trans: int = Field(default=0, ge=0)
    lnbits_only_allow_incoming_payments: bool = Field(default=False)
    lnbits_watchdog_switch_to_voidwallet: bool = Field(default=False)
    lnbits_watchdog_interval_minutes: int = Field(default=60, gt=0)
    lnbits_watchdog_delta: int = Field(default=1_000_000, gt=0)

    lnbits_max_outgoing_payment_amount_sats: int = Field(default=10_000_000, ge=0)
    lnbits_max_incoming_payment_amount_sats: int = Field(default=10_000_000, ge=0)

    def is_wallet_max_balance_exceeded(self, amount):
        return (
            self.lnbits_wallet_limit_max_balance
            and self.lnbits_wallet_limit_max_balance > 0
            and amount > self.lnbits_wallet_limit_max_balance
        )


class NotificationsSettings(LNbitsSettings):
    lnbits_nostr_notifications_enabled: bool = Field(default=False)
    lnbits_nostr_notifications_private_key: str = Field(default="")
    lnbits_nostr_notifications_identifiers: list[str] = Field(default=[])
    lnbits_telegram_notifications_enabled: bool = Field(default=False)
    lnbits_telegram_notifications_access_token: str = Field(default="")
    lnbits_telegram_notifications_chat_id: str = Field(default="")
    lnbits_email_notifications_enabled: bool = Field(default=False)
    lnbits_email_notifications_email: str = Field(default="")
    lnbits_email_notifications_username: str = Field(default="")
    lnbits_email_notifications_password: str = Field(default="")
    lnbits_email_notifications_server: str = Field(default="smtp.protonmail.ch")
    lnbits_email_notifications_port: int = Field(default=587)
    lnbits_email_notifications_to_emails: list[str] = Field(default=[])

    lnbits_notification_settings_update: bool = Field(default=True)
    lnbits_notification_credit_debit: bool = Field(default=True)
    notification_balance_delta_threshold_sats: int = Field(default=1, ge=0)
    lnbits_notification_server_start_stop: bool = Field(default=True)
    lnbits_notification_watchdog: bool = Field(default=False)
    lnbits_notification_server_status_hours: int = Field(default=24, gt=0)
    lnbits_notification_incoming_payment_amount_sats: int = Field(
        default=1_000_000, ge=0
    )
    lnbits_notification_outgoing_payment_amount_sats: int = Field(
        default=1_000_000, ge=0
    )

    def is_nostr_notifications_configured(self) -> bool:
        return (
            self.lnbits_nostr_notifications_enabled
            and self.lnbits_nostr_notifications_private_key is not None
        )

    def is_telegram_notifications_configured(self) -> bool:
        return (
            self.lnbits_telegram_notifications_enabled
            and self.lnbits_telegram_notifications_access_token is not None
        )


class FakeWalletFundingSource(LNbitsSettings):
    fake_wallet_secret: str = Field(default="ToTheMoon1")
    lnbits_denomination: str = Field(default="sats")


class LNbitsFundingSource(LNbitsSettings):
    lnbits_endpoint: str = Field(default="https://demo.lnbits.com")
    lnbits_key: str | None = Field(default=None)
    lnbits_admin_key: str | None = Field(default=None)
    lnbits_invoice_key: str | None = Field(default=None)


class ClicheFundingSource(LNbitsSettings):
    cliche_endpoint: str | None = Field(default=None)


class CLNRestFundingSource(LNbitsSettings):
    clnrest_url: str | None = Field(default=None)
    clnrest_ca: str | None = Field(default=None)
    clnrest_cert: str | None = Field(default=None)
    clnrest_readonly_rune: str | None = Field(default=None)
    clnrest_invoice_rune: str | None = Field(default=None)
    clnrest_pay_rune: str | None = Field(default=None)
    clnrest_renepay_rune: str | None = Field(default=None)
    clnrest_last_pay_index: str | None = Field(default=None)
    clnrest_nodeid: str | None = Field(default=None)


class CoreLightningFundingSource(LNbitsSettings):
    corelightning_rpc: str | None = Field(default=None)
    corelightning_pay_command: str = Field(default="pay")
    clightning_rpc: str | None = Field(default=None)


class CoreLightningRestFundingSource(LNbitsSettings):
    corelightning_rest_url: str | None = Field(default=None)
    corelightning_rest_macaroon: str | None = Field(default=None)
    corelightning_rest_cert: str | None = Field(default=None)


class EclairFundingSource(LNbitsSettings):
    eclair_url: str | None = Field(default=None)
    eclair_pass: str | None = Field(default=None)


class LndRestFundingSource(LNbitsSettings):
    lnd_rest_endpoint: str | None = Field(default=None)
    lnd_rest_cert: str | None = Field(default=None)
    lnd_rest_macaroon: str | None = Field(default=None)
    lnd_rest_macaroon_encrypted: str | None = Field(default=None)
    lnd_rest_route_hints: bool = Field(default=True)
    lnd_rest_allow_self_payment: bool = Field(default=False)
    lnd_cert: str | None = Field(default=None)
    lnd_admin_macaroon: str | None = Field(default=None)
    lnd_invoice_macaroon: str | None = Field(default=None)
    lnd_rest_admin_macaroon: str | None = Field(default=None)
    lnd_rest_invoice_macaroon: str | None = Field(default=None)


class LndGrpcFundingSource(LNbitsSettings):
    lnd_grpc_endpoint: str | None = Field(default=None)
    lnd_grpc_cert: str | None = Field(default=None)
    lnd_grpc_port: int | None = Field(default=None)
    lnd_grpc_admin_macaroon: str | None = Field(default=None)
    lnd_grpc_invoice_macaroon: str | None = Field(default=None)
    lnd_grpc_macaroon: str | None = Field(default=None)
    lnd_grpc_macaroon_encrypted: str | None = Field(default=None)


class LnPayFundingSource(LNbitsSettings):
    lnpay_api_endpoint: str | None = Field(default=None)
    lnpay_api_key: str | None = Field(default=None)
    lnpay_wallet_key: str | None = Field(default=None)
    lnpay_admin_key: str | None = Field(default=None)


class BlinkFundingSource(LNbitsSettings):
    blink_api_endpoint: str | None = Field(default="https://api.blink.sv/graphql")
    blink_ws_endpoint: str | None = Field(default="wss://ws.blink.sv/graphql")
    blink_token: str | None = Field(default=None)


class ZBDFundingSource(LNbitsSettings):
    zbd_api_endpoint: str | None = Field(default="https://api.zebedee.io/v0/")
    zbd_api_key: str | None = Field(default=None)


class PhoenixdFundingSource(LNbitsSettings):
    phoenixd_api_endpoint: str | None = Field(default="http://localhost:9740/")
    phoenixd_api_password: str | None = Field(default=None)


class AlbyFundingSource(LNbitsSettings):
    alby_api_endpoint: str | None = Field(default="https://api.getalby.com/")
    alby_access_token: str | None = Field(default=None)


class OpenNodeFundingSource(LNbitsSettings):
    opennode_api_endpoint: str | None = Field(default=None)
    opennode_key: str | None = Field(default=None)
    opennode_admin_key: str | None = Field(default=None)
    opennode_invoice_key: str | None = Field(default=None)


class SparkFundingSource(LNbitsSettings):
    spark_url: str | None = Field(default=None)
    spark_token: str | None = Field(default=None)


class LnTipsFundingSource(LNbitsSettings):
    lntips_api_endpoint: str | None = Field(default=None)
    lntips_api_key: str | None = Field(default=None)
    lntips_admin_key: str | None = Field(default=None)
    lntips_invoice_key: str | None = Field(default=None)


class NWCFundingSource(LNbitsSettings):
    nwc_pairing_url: str | None = Field(default=None)


class BreezSdkFundingSource(LNbitsSettings):
    breez_api_key: str | None = Field(default=None)
    breez_greenlight_seed: str | None = Field(default=None)
    breez_greenlight_invite_code: str | None = Field(default=None)
    breez_greenlight_device_key: str | None = Field(default=None)
    breez_greenlight_device_cert: str | None = Field(default=None)
    breez_use_trampoline: bool = Field(default=True)


class BreezLiquidSdkFundingSource(LNbitsSettings):
    breez_liquid_api_key: str | None = Field(default=None)
    breez_liquid_seed: str | None = Field(default=None)
    breez_liquid_fee_offset_sat: int = Field(default=50)


class BoltzFundingSource(LNbitsSettings):
    boltz_client_endpoint: str | None = Field(default="127.0.0.1:9002")
    boltz_client_macaroon: str | None = Field(default=None)
    boltz_client_wallet: str | None = Field(default="lnbits")
    boltz_client_password: str = Field(default="")
    boltz_client_cert: str | None = Field(default=None)
    boltz_mnemonic: str | None = Field(default=None)


class StrikeFundingSource(LNbitsSettings):
    strike_api_endpoint: str | None = Field(
        default="https://api.strike.me/v1", env="STRIKE_API_ENDPOINT"
    )
    strike_api_key: str | None = Field(default=None, env="STRIKE_API_KEY")


class FiatProviderLimits(BaseModel):
    # empty list means all users are allowed to receive payments via Stripe
    allowed_users: list[str] = Field(default=[])

    service_max_fee_sats: int = Field(default=0)
    service_fee_percent: float = Field(default=0)
    service_fee_wallet_id: str | None = Field(default=None)

    service_min_amount_sats: int = Field(default=0)
    service_max_amount_sats: int = Field(default=0)
    service_faucet_wallet_id: str | None = Field(default="")


class StripeFiatProvider(LNbitsSettings):
    stripe_enabled: bool = Field(default=False)
    stripe_api_endpoint: str = Field(default="https://api.stripe.com")
    stripe_api_secret_key: str | None = Field(default=None)
    stripe_payment_success_url: str = Field(default="https://lnbits.com")

    stripe_payment_webhook_url: str = Field(
        default="https://your-lnbits-domain-here.com/api/v1/callback/stripe"
    )
    # Use this secret to verify that events come from Stripe.
    stripe_webhook_signing_secret: str | None = Field(default=None)

    stripe_limits: FiatProviderLimits = Field(default_factory=FiatProviderLimits)


class LightningSettings(LNbitsSettings):
    lightning_invoice_expiry: int = Field(default=3600, gt=0)


class FundingSourcesSettings(
    FakeWalletFundingSource,
    LNbitsFundingSource,
    ClicheFundingSource,
    CLNRestFundingSource,
    CoreLightningFundingSource,
    CoreLightningRestFundingSource,
    EclairFundingSource,
    LndRestFundingSource,
    LndGrpcFundingSource,
    LnPayFundingSource,
    BlinkFundingSource,
    AlbyFundingSource,
    BoltzFundingSource,
    ZBDFundingSource,
    PhoenixdFundingSource,
    OpenNodeFundingSource,
    SparkFundingSource,
    LnTipsFundingSource,
    NWCFundingSource,
    BreezSdkFundingSource,
    StrikeFundingSource,
    BreezLiquidSdkFundingSource,
):
    lnbits_backend_wallet_class: str = Field(default="VoidWallet")
    # How long to wait for the payment to be confirmed before returning a pending status
    # It will not fail the payment, it will make it return pending after the timeout
    lnbits_funding_source_pay_invoice_wait_seconds: int = Field(default=5, ge=0)
    funding_source_max_retries: int = Field(default=4, ge=0)


class FiatProvidersSettings(StripeFiatProvider):
    def is_fiat_provider_enabled(self, provider: str | None) -> bool:
        """
        Checks if a specific fiat provider is enabled.
        """
        if not provider:
            return False
        if provider == "stripe":
            return self.stripe_enabled
        # Add checks for other fiat providers here as needed
        return False

    def get_fiat_providers_for_user(self, user_id: str) -> list[str]:
        """
        Returns a list of fiat payment methods allowed for the user.
        """
        allowed_providers = []
        if self.stripe_enabled and (
            not self.stripe_limits.allowed_users
            or user_id in self.stripe_limits.allowed_users
        ):
            allowed_providers.append("stripe")

        # Add other fiat providers here as needed
        return allowed_providers

    def get_fiat_provider_limits(self, provider_name: str) -> FiatProviderLimits | None:
        """
        Returns the limits for a specific fiat provider.
        """
        return getattr(self, provider_name + "_limits", None)


class WebPushSettings(LNbitsSettings):
    lnbits_webpush_pubkey: str | None = Field(default=None)
    lnbits_webpush_privkey: str | None = Field(default=None)


class NodeUISettings(LNbitsSettings):
    # on-off switch for node ui
    lnbits_node_ui: bool = Field(default=False)
    # whether to display the public node ui (only if lnbits_node_ui is True)
    lnbits_public_node_ui: bool = Field(default=False)
    # can be used to disable the transactions tab in the node ui
    # (recommended for large cln nodes)
    lnbits_node_ui_transactions: bool = Field(default=False)


class AuthMethods(Enum):
    user_id_only = "user-id-only"
    username_and_password = "username-password"  # noqa: S105
    nostr_auth_nip98 = "nostr-auth-nip98"
    google_auth = "google-auth"
    github_auth = "github-auth"
    keycloak_auth = "keycloak-auth"

    @classmethod
    def all(cls):
        return [
            AuthMethods.user_id_only.value,
            AuthMethods.username_and_password.value,
            AuthMethods.nostr_auth_nip98.value,
            AuthMethods.google_auth.value,
            AuthMethods.github_auth.value,
            AuthMethods.keycloak_auth.value,
        ]


class AuthSettings(LNbitsSettings):
    auth_token_expire_minutes: int = Field(default=525600, gt=0)
    auth_all_methods: list[str] = [a.value for a in AuthMethods]
    auth_allowed_methods: list[str] = Field(
        default=[
            AuthMethods.user_id_only.value,
            AuthMethods.username_and_password.value,
        ]
    )
    # How many seconds after login the user is allowed to update its credentials.
    # A fresh login is required afterwards.
    auth_credetials_update_threshold: int = Field(default=120, gt=0)
    auth_authentication_cache_minutes: int = Field(default=10, ge=0)

    def is_auth_method_allowed(self, method: AuthMethods):
        return method.value in self.auth_allowed_methods


class NostrAuthSettings(LNbitsSettings):
    nostr_absolute_request_urls: list[str] = Field(
        default=["http://127.0.0.1:5000", "http://localhost:5000"]
    )


class GoogleAuthSettings(LNbitsSettings):
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")


class GitHubAuthSettings(LNbitsSettings):
    github_client_id: str = Field(default="")
    github_client_secret: str = Field(default="")


class KeycloakAuthSettings(LNbitsSettings):
    keycloak_discovery_url: str = Field(default="")
    keycloak_client_id: str = Field(default="")
    keycloak_client_secret: str = Field(default="")
    keycloak_client_custom_org: str | None = Field(default=None)
    keycloak_client_custom_icon: str | None = Field(default=None)


class AuditSettings(LNbitsSettings):
    lnbits_audit_enabled: bool = Field(default=True)

    # number of days to keep the audit entry
    lnbits_audit_retention_days: int = Field(default=7, ge=0)

    lnbits_audit_log_ip_address: bool = Field(default=False)
    lnbits_audit_log_path_params: bool = Field(default=True)
    lnbits_audit_log_query_params: bool = Field(default=True)
    lnbits_audit_log_request_body: bool = Field(default=False)

    # List of paths to be included (regex match). Empty list means all.
    lnbits_audit_include_paths: list[str] = Field(default=[".*api/v1/.*"])
    # List of paths to be excluded (regex match). Empty list means none.
    lnbits_audit_exclude_paths: list[str] = Field(default=["/static"])

    # List of HTTP methods to be included. Empty lists means all.
    # Options (case-sensitive): GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
    lnbits_audit_http_methods: list[str] = Field(
        default=["POST", "PUT", "PATCH", "DELETE"]
    )

    # List of HTTP codes to be included (regex match). Empty lists means all.
    lnbits_audit_http_response_codes: list[str] = Field(default=["4.*", "5.*"])

    def audit_http_request_details(self) -> bool:
        return (
            self.lnbits_audit_log_path_params
            or self.lnbits_audit_log_query_params
            or self.lnbits_audit_log_request_body
        )

    def audit_http_request(
        self,
        http_method: str | None = None,
        path: str | None = None,
        http_response_code: str | None = None,
    ) -> bool:
        if not self.lnbits_audit_enabled:
            return False
        if len(self.lnbits_audit_http_methods) != 0:
            if not http_method:
                return False
            if http_method not in self.lnbits_audit_http_methods:
                return False

        if not self._is_http_request_path_auditable(path):
            return False

        if not self._is_http_response_code_auditable(http_response_code):
            return False

        return True

    def _is_http_request_path_auditable(self, path: str | None):
        if len(self.lnbits_audit_exclude_paths) != 0 and path:
            for exclude_path in self.lnbits_audit_exclude_paths:
                if _re_fullmatch_safe(exclude_path, path):
                    return False

        if len(self.lnbits_audit_include_paths) == 0:
            return True

        if not path:
            return False
        for include_path in self.lnbits_audit_include_paths:
            if _re_fullmatch_safe(include_path, path):
                return True

        return False

    def _is_http_response_code_auditable(self, http_response_code: str | None) -> bool:
        if not http_response_code:
            # No response code means only request filters should apply
            return True

        if len(self.lnbits_audit_http_response_codes) == 0:
            return True

        for response_code in self.lnbits_audit_http_response_codes:
            if _re_fullmatch_safe(response_code, http_response_code):
                return True

        return False


class EditableSettings(
    UsersSettings,
    ExtensionsSettings,
    ThemesSettings,
    OpsSettings,
    AssetSettings,
    FeeSettings,
    ExchangeProvidersSettings,
    SecuritySettings,
    NotificationsSettings,
    FundingSourcesSettings,
    FiatProvidersSettings,
    LightningSettings,
    WebPushSettings,
    NodeUISettings,
    AuditSettings,
    AuthSettings,
    NostrAuthSettings,
    GoogleAuthSettings,
    GitHubAuthSettings,
    KeycloakAuthSettings,
):
    @validator(
        "lnbits_admin_users",
        "lnbits_allowed_users",
        "lnbits_theme_options",
        "lnbits_admin_extensions",
        pre=True,
    )
    @classmethod
    def validate_editable_settings(cls, val):
        return super().validate_list(val)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            **{k: v for k, v in d.items() if k in inspect.signature(cls).parameters}
        )

    # fixes openapi.json validation, remove field env_names
    class Config:
        @staticmethod
        def schema_extra(schema: dict[str, Any]) -> None:
            for prop in schema.get("properties", {}).values():
                prop.pop("env_names", None)


class UpdateSettings(EditableSettings):
    class Config:
        extra = Extra.forbid


class EnvSettings(LNbitsSettings):
    debug: bool = Field(default=False)
    debug_database: bool = Field(default=False)
    bundle_assets: bool = Field(default=True)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000, gt=0)
    forwarded_allow_ips: str = Field(default="*")
    lnbits_title: str = Field(default="LNbits API")
    lnbits_path: str = Field(default=".")
    lnbits_extensions_path: str = Field(default="lnbits")
    super_user: str = Field(default="")
    auth_secret_key: str = Field(default="")
    version: str = Field(default="0.0.0")
    user_agent: str = Field(default="")
    enable_log_to_file: bool = Field(default=True)
    log_rotation: str = Field(default="100 MB")
    log_retention: str = Field(default="3 months")

    cleanup_wallets_days: int = Field(default=90, ge=0)
    funding_source_max_retries: int = Field(default=4, ge=0)

    @property
    def has_default_extension_path(self) -> bool:
        return self.lnbits_extensions_path == "lnbits"

    def check_auth_secret_key(self):
        if self.auth_secret_key:
            return
        if not os.path.isdir(settings.lnbits_data_folder):
            os.mkdir(settings.lnbits_data_folder)
        auth_key_file = Path(settings.lnbits_data_folder, ".lnbits_auth_key")
        if auth_key_file.is_file():
            with open(auth_key_file) as file:
                self.auth_secret_key = file.readline()
            return
        self.auth_secret_key = uuid4().hex
        with open(auth_key_file, "w+") as file:
            file.write(self.auth_secret_key)


class PersistenceSettings(LNbitsSettings):
    lnbits_data_folder: str = Field(default="./data")
    lnbits_database_url: str | None = Field(default=None)


class SuperUserSettings(LNbitsSettings):
    lnbits_allowed_funding_sources: list[str] = Field(
        default=[
            "AlbyWallet",
            "BoltzWallet",
            "BlinkWallet",
            "BreezSdkWallet",
            "BreezLiquidSdkWallet",
            "CLNRestWallet",
            "CoreLightningRestWallet",
            "CoreLightningWallet",
            "EclairWallet",
            "FakeWallet",
            "LNPayWallet",
            "LNbitsWallet",
            "LnTipsWallet",
            "LndRestWallet",
            "LndWallet",
            "OpenNodeWallet",
            "PhoenixdWallet",
            "VoidWallet",
            "ZBDWallet",
            "NWCWallet",
            "StrikeWallet",
        ]
    )


class TransientSettings(InstalledExtensionsSettings, ExchangeHistorySettings):
    # Transient Settings:
    #  - are initialized, updated and used at runtime
    #  - are not read from a file or from the `settings` table
    #  - are not persisted in the `settings` table when the settings are updated
    #  - are cleared on server restart
    first_install: bool = Field(default=False)

    # Indicates that the server should continue to run.
    # When set to false it indicates that the shutdown procedure is ongoing.
    # If false no new tasks, threads, etc should be started.
    # Long running while loops should use this flag instead of `while True:`
    lnbits_running: bool = Field(default=True)

    # Remember the latest balance delta in order to compare with the current one
    latest_balance_delta_sats: int = Field(default=0)

    lnbits_all_extensions_ids: set[str] = Field(default=set())

    server_startup_time: int = Field(default=int(time()))

    has_holdinvoice: bool = Field(default=False)
    has_nodemanager: bool = Field(default=False)

    @property
    def lnbits_server_up_time(self) -> str:
        up_time = int(time() - self.server_startup_time)
        return strftime("%H:%M:%S", gmtime(up_time))

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class ReadOnlySettings(
    EnvSettings,
    ExtensionsInstallSettings,
    PersistenceSettings,
    SuperUserSettings,
):
    lnbits_admin_ui: bool = Field(default=True)

    @property
    def lnbits_extensions_upgrade_path(self) -> str:
        return str(Path(self.lnbits_data_folder, "upgrades"))

    @validator(
        "lnbits_allowed_funding_sources",
        pre=True,
    )
    @classmethod
    def validate_readonly_settings(cls, val):
        return super().validate_list(val)

    @classmethod
    def readonly_fields(cls):
        return [f for f in inspect.signature(cls).parameters if not f.startswith("_")]


class Settings(EditableSettings, ReadOnlySettings, TransientSettings, BaseSettings):
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        json_loads = list_parse_fallback

    def is_user_allowed(self, user_id: str) -> bool:
        return (
            len(self.lnbits_allowed_users) == 0
            or user_id in self.lnbits_allowed_users
            or user_id in self.lnbits_admin_users
            or user_id == self.super_user
        )

    def is_super_user(self, user_id: str | None = None) -> bool:
        return user_id == self.super_user

    def is_admin_user(self, user_id: str) -> bool:
        return self.is_super_user(user_id) or user_id in self.lnbits_admin_users

    def is_admin_extension(self, ext_id: str) -> bool:
        return ext_id in self.lnbits_admin_extensions

    def is_installed_extension_id(self, ext_id: str) -> bool:
        return ext_id in self.lnbits_installed_extensions_ids

    def is_ready_to_install_extension_id(self, ext_id: str) -> bool:
        return (
            ext_id not in self.lnbits_installed_extensions_ids
            and ext_id in self.lnbits_all_extensions_ids
        )


class SuperSettings(EditableSettings):
    super_user: str


class AdminSettings(EditableSettings):
    is_super_user: bool
    lnbits_allowed_funding_sources: list[str] | None


class SettingsField(BaseModel):
    id: str
    value: Any | None
    tag: str = "core"


def _re_fullmatch_safe(pattern: str, string: str):
    try:
        return re.fullmatch(pattern, string) is not None
    except Exception as _:
        logger.warning(f"Regex error for pattern {pattern}")
        return False


def set_cli_settings(**kwargs):
    for key, value in kwargs.items():
        setattr(settings, key, value)


readonly_variables = ReadOnlySettings.readonly_fields()
transient_variables = TransientSettings.readonly_fields()

settings = Settings()

settings.lnbits_path = str(path.dirname(path.realpath(__file__)))

settings.version = importlib.metadata.version("lnbits")

settings.check_auth_secret_key()

if not settings.user_agent:
    settings.user_agent = f"LNbits/{settings.version}"

# printing environment variable for debugging
if not settings.lnbits_admin_ui:
    logger.debug("Environment Settings:")
    for key, value in settings.dict(exclude_none=True).items():
        logger.debug(f"{key}: {value}")


def get_funding_source():
    """
    Backwards compatibility
    """
    from lnbits.wallets import get_funding_source

    return get_funding_source()
