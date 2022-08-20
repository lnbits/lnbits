import pytest
import pytest_asyncio

from tests.helpers import is_regtest


@pytest.mark.asyncio
async def test_mempool_url(client):
    response = await client.get("/boltz/api/v1/swap/mempool")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_boltz_config(client):
    response = await client.get("/boltz/api/v1/swap/boltz")
    assert response.status_code == 200


get_urls_private = [
    "/boltz/api/v1/swap?all_wallets=true",
    "/boltz/api/v1/swap/reverse?all_wallets=true",
]
post_urls_private = [
    "/boltz/api/v1/swap",
    "/boltz/api/v1/swap/reverse",
    "/boltz/api/v1/swap/check",
    "/boltz/api/v1/swap/refund/UNKNOWN",
    "/boltz/api/v1/swap/status/UNKNOWN",
]


@pytest.mark.asyncio
async def test_endpoints_unauthenticated(client):
    for url in get_urls_private:
        response = await client.get(url)
        assert response.status_code == 400
    # https://github.com/lnbits/lnbits-legend/pull/848
    # for url in post_urls_private:
    #     response = await client.post(url)
    #     assert response.status_code == 400
