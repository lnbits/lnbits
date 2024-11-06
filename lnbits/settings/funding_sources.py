from __future__ import annotations

from typing import Optional

from pydantic import Field

from .lnbits import LNbitsSettings


class FakeWalletFundingSource(LNbitsSettings):
    fake_wallet_secret: str = Field(default="ToTheMoon1")


class LNbitsFundingSource(LNbitsSettings):
    lnbits_endpoint: str = Field(default="https://demo.lnbits.com")
    lnbits_key: Optional[str] = Field(default=None)
    lnbits_admin_key: Optional[str] = Field(default=None)
    lnbits_invoice_key: Optional[str] = Field(default=None)


class ClicheFundingSource(LNbitsSettings):
    cliche_endpoint: Optional[str] = Field(default=None)


class CoreLightningFundingSource(LNbitsSettings):
    corelightning_rpc: Optional[str] = Field(default=None)
    corelightning_pay_command: str = Field(default="pay")
    clightning_rpc: Optional[str] = Field(default=None)


class CoreLightningRestFundingSource(LNbitsSettings):
    corelightning_rest_url: Optional[str] = Field(default=None)
    corelightning_rest_macaroon: Optional[str] = Field(default=None)
    corelightning_rest_cert: Optional[str] = Field(default=None)


class EclairFundingSource(LNbitsSettings):
    eclair_url: Optional[str] = Field(default=None)
    eclair_pass: Optional[str] = Field(default=None)


class LndRestFundingSource(LNbitsSettings):
    lnd_rest_endpoint: Optional[str] = Field(default=None)
    lnd_rest_cert: Optional[str] = Field(default=None)
    lnd_rest_macaroon: Optional[str] = Field(default=None)
    lnd_rest_macaroon_encrypted: Optional[str] = Field(default=None)
    lnd_rest_route_hints: bool = Field(default=True)
    lnd_cert: Optional[str] = Field(default=None)
    lnd_admin_macaroon: Optional[str] = Field(default=None)
    lnd_invoice_macaroon: Optional[str] = Field(default=None)
    lnd_rest_admin_macaroon: Optional[str] = Field(default=None)
    lnd_rest_invoice_macaroon: Optional[str] = Field(default=None)


class LndGrpcFundingSource(LNbitsSettings):
    lnd_grpc_endpoint: Optional[str] = Field(default=None)
    lnd_grpc_cert: Optional[str] = Field(default=None)
    lnd_grpc_port: Optional[int] = Field(default=None)
    lnd_grpc_admin_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_invoice_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_macaroon: Optional[str] = Field(default=None)
    lnd_grpc_macaroon_encrypted: Optional[str] = Field(default=None)


class LnPayFundingSource(LNbitsSettings):
    lnpay_api_endpoint: Optional[str] = Field(default=None)
    lnpay_api_key: Optional[str] = Field(default=None)
    lnpay_wallet_key: Optional[str] = Field(default=None)
    lnpay_admin_key: Optional[str] = Field(default=None)


class BlinkFundingSource(LNbitsSettings):
    blink_api_endpoint: Optional[str] = Field(default="https://api.blink.sv/graphql")
    blink_ws_endpoint: Optional[str] = Field(default="wss://ws.blink.sv/graphql")
    blink_token: Optional[str] = Field(default=None)


class ZBDFundingSource(LNbitsSettings):
    zbd_api_endpoint: Optional[str] = Field(default="https://api.zebedee.io/v0/")
    zbd_api_key: Optional[str] = Field(default=None)


class PhoenixdFundingSource(LNbitsSettings):
    phoenixd_api_endpoint: Optional[str] = Field(default="http://localhost:9740/")
    phoenixd_api_password: Optional[str] = Field(default=None)


class AlbyFundingSource(LNbitsSettings):
    alby_api_endpoint: Optional[str] = Field(default="https://api.getalby.com/")
    alby_access_token: Optional[str] = Field(default=None)


class OpenNodeFundingSource(LNbitsSettings):
    opennode_api_endpoint: Optional[str] = Field(default=None)
    opennode_key: Optional[str] = Field(default=None)
    opennode_admin_key: Optional[str] = Field(default=None)
    opennode_invoice_key: Optional[str] = Field(default=None)


class SparkFundingSource(LNbitsSettings):
    spark_url: Optional[str] = Field(default=None)
    spark_token: Optional[str] = Field(default=None)


class LnTipsFundingSource(LNbitsSettings):
    lntips_api_endpoint: Optional[str] = Field(default=None)
    lntips_api_key: Optional[str] = Field(default=None)
    lntips_admin_key: Optional[str] = Field(default=None)
    lntips_invoice_key: Optional[str] = Field(default=None)


class NWCFundingSource(LNbitsSettings):
    nwc_pairing_url: Optional[str] = Field(default=None)


class BreezSdkFundingSource(LNbitsSettings):
    breez_api_key: Optional[str] = Field(default=None)
    breez_greenlight_seed: Optional[str] = Field(default=None)
    breez_greenlight_invite_code: Optional[str] = Field(default=None)
    breez_greenlight_device_key: Optional[str] = Field(default=None)
    breez_greenlight_device_cert: Optional[str] = Field(default=None)


class BoltzFundingSource(LNbitsSettings):
    boltz_client_endpoint: Optional[str] = Field(default="127.0.0.1:9002")
    boltz_client_macaroon: Optional[str] = Field(default=None)
    boltz_client_wallet: Optional[str] = Field(default="lnbits")
    boltz_client_cert: Optional[str] = Field(default=None)


class LightningSettings(LNbitsSettings):
    lightning_invoice_expiry: int = Field(default=3600)


class FundingSourcesSettings(
    FakeWalletFundingSource,
    LNbitsFundingSource,
    ClicheFundingSource,
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
):
    lnbits_backend_wallet_class: str = Field(default="VoidWallet")
