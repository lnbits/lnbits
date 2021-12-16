import pytest
import secrets
from lnbits.core.crud import get_wallet
from lnbits.settings import HOST, PORT
from lnbits.extensions.bleskomat.crud import get_bleskomat_lnurl
from lnbits.extensions.bleskomat.helpers import generate_bleskomat_lnurl_signature, query_to_signing_payload
from tests.conftest import client
from tests.helpers import credit_wallet
from tests.extensions.bleskomat.conftest import bleskomat, lnurl
from tests.mocks import WALLET

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_missing_secret(client):
    response = await client.get("/bleskomat/u")
    assert response.status_code == 200
    assert response.json() == {"status": "ERROR", "reason": "Missing secret"}

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_invalid_secret(client):
    response = await client.get("/bleskomat/u?k1=invalid-secret")
    assert response.status_code == 200
    assert response.json() == {"status": "ERROR", "reason": "Invalid secret"}

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_unknown_api_key(client):
    query = {
        "id": "does-not-exist",
        "nonce": secrets.token_hex(10),
        "tag": "withdrawRequest",
        "minWithdrawable": "1",
        "maxWithdrawable": "1",
        "defaultDescription": "",
        "f": "EUR",
    }
    payload = query_to_signing_payload(query)
    signature = "xxx"# not checked, so doesn't matter
    response = await client.get(f'/bleskomat/u?{payload}&signature={signature}')
    assert response.status_code == 200
    assert response.json() == {"status": "ERROR", "reason": "Unknown API key"}

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_invalid_signature(client, bleskomat):
    query = {
        "id": bleskomat.api_key_id,
        "nonce": secrets.token_hex(10),
        "tag": "withdrawRequest",
        "minWithdrawable": "1",
        "maxWithdrawable": "1",
        "defaultDescription": "",
        "f": "EUR",
    }
    payload = query_to_signing_payload(query)
    signature = "invalid"
    response = await client.get(f'/bleskomat/u?{payload}&signature={signature}')
    assert response.status_code == 200
    assert response.json() == {"status": "ERROR", "reason": "Invalid API key signature"}

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_valid_signature(client, bleskomat):
    query = {
        "id": bleskomat.api_key_id,
        "nonce": secrets.token_hex(10),
        "tag": "withdrawRequest",
        "minWithdrawable": "1",
        "maxWithdrawable": "1",
        "defaultDescription": "test valid sig",
        "f": "EUR",# tests use the dummy exchange rate provider
    }
    payload = query_to_signing_payload(query)
    signature = generate_bleskomat_lnurl_signature(
        payload=payload,
        api_key_secret=bleskomat.api_key_secret,
        api_key_encoding=bleskomat.api_key_encoding
    )
    response = await client.get(f'/bleskomat/u?{payload}&signature={signature}')
    assert response.status_code == 200
    data = response.json()
    assert data["tag"] == "withdrawRequest"
    assert data["minWithdrawable"] == 1000
    assert data["maxWithdrawable"] == 1000
    assert data["defaultDescription"] == "test valid sig"
    assert data["callback"] == f'http://{HOST}:{PORT}/bleskomat/u'
    k1 = data["k1"]
    lnurl = await get_bleskomat_lnurl(secret=k1)
    assert lnurl

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_action_insufficient_balance(client, lnurl):
    bleskomat = lnurl["bleskomat"]
    secret = lnurl["secret"]
    pr = "lntb500n1pseq44upp5xqd38rgad72lnlh4gl339njlrsl3ykep82j6gj4g02dkule7k54qdqqcqzpgxqyz5vqsp5h0zgewuxdxcl2rnlumh6g520t4fr05rgudakpxm789xgjekha75s9qyyssq5vhwsy9knhfeqg0wn6hcnppwmum8fs3g3jxkgw45havgfl6evchjsz3s8e8kr6eyacz02szdhs7v5lg0m7wehd5rpf6yg8480cddjlqpae52xu"
    WALLET.pay_invoice.reset_mock()
    response = await client.get(f'/bleskomat/u?k1={secret}&pr={pr}')
    assert response.status_code == 200
    assert response.json() == {"status": "ERROR", "reason": "Failed to pay invoice: Insufficient balance."}
    wallet = await get_wallet(bleskomat.wallet)
    assert wallet.balance_msat == 0
    bleskomat_lnurl = await get_bleskomat_lnurl(secret)
    assert bleskomat_lnurl.has_uses_remaining() == True
    WALLET.pay_invoice.assert_not_called()

@pytest.mark.asyncio
async def test_bleskomat_lnurl_api_action_success(client, lnurl):
    bleskomat = lnurl["bleskomat"]
    secret = lnurl["secret"]
    pr = "lntb500n1pseq44upp5xqd38rgad72lnlh4gl339njlrsl3ykep82j6gj4g02dkule7k54qdqqcqzpgxqyz5vqsp5h0zgewuxdxcl2rnlumh6g520t4fr05rgudakpxm789xgjekha75s9qyyssq5vhwsy9knhfeqg0wn6hcnppwmum8fs3g3jxkgw45havgfl6evchjsz3s8e8kr6eyacz02szdhs7v5lg0m7wehd5rpf6yg8480cddjlqpae52xu"
    await credit_wallet(
        wallet_id=bleskomat.wallet,
        amount=100000,
    )
    wallet = await get_wallet(bleskomat.wallet)
    assert wallet.balance_msat == 100000
    WALLET.pay_invoice.reset_mock()
    response = await client.get(f'/bleskomat/u?k1={secret}&pr={pr}')
    assert response.json() == {"status": "OK"}
    wallet = await get_wallet(bleskomat.wallet)
    assert wallet.balance_msat == 50000
    bleskomat_lnurl = await get_bleskomat_lnurl(secret)
    assert bleskomat_lnurl.has_uses_remaining() == False
    WALLET.pay_invoice.assert_called_once_with(pr)
