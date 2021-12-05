import json
import pytest
import secrets
from lnbits.core.crud import create_account, create_wallet
from lnbits.extensions.bleskomat.crud import create_bleskomat, create_bleskomat_lnurl
from lnbits.extensions.bleskomat.models import CreateBleskomat
from lnbits.extensions.bleskomat.helpers import generate_bleskomat_lnurl_secret, generate_bleskomat_lnurl_signature, prepare_lnurl_params, query_to_signing_payload
from lnbits.extensions.bleskomat.exchange_rates import exchange_rate_providers

exchange_rate_providers["dummy"] = {
    "name": "dummy",
    "domain": None,
    "api_url": None,
    "getter": lambda data, replacements: str(1e8),# 1 BTC = 100000000 sats
}

@pytest.fixture
async def bleskomat():
    user = await create_account()
    wallet = await create_wallet(user_id=user.id, wallet_name="bleskomat_test")
    data = CreateBleskomat(
        name="Test Bleskomat",
        fiat_currency="EUR",
        exchange_rate_provider="dummy",
        fee="0"
    )
    bleskomat = await create_bleskomat(data=data, wallet_id=wallet.id)
    return bleskomat

@pytest.fixture
async def lnurl(bleskomat):
    query = {
        "tag": "withdrawRequest",
        "nonce": secrets.token_hex(10),
        "tag": "withdrawRequest",
        "minWithdrawable": "50000",
        "maxWithdrawable": "50000",
        "defaultDescription": "test valid sig",
    }
    tag = query["tag"]
    params = prepare_lnurl_params(tag, query)
    payload = query_to_signing_payload(query)
    signature = generate_bleskomat_lnurl_signature(
        payload=payload,
        api_key_secret=bleskomat.api_key_secret,
        api_key_encoding=bleskomat.api_key_encoding
    )
    secret = generate_bleskomat_lnurl_secret(bleskomat.api_key_id, signature)
    params = json.JSONEncoder().encode(params)
    lnurl = await create_bleskomat_lnurl(
        bleskomat=bleskomat, secret=secret, tag=tag, params=params, uses=1
    )
    return {
        "bleskomat": bleskomat,
        "lnurl": lnurl,
        "secret": secret,
    }
