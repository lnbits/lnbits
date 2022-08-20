import pytest
import pytest_asyncio

get_urls_public = ["/boltz/api/v1/swap/boltz", "/boltz/api/v1/swap/mempool"]
get_urls_private = [
    "/boltz/api/v1/swap?all_wallets=true",
    "/boltz/api/v1/swap/reverse?all_wallets=true",
]
post_urls_private = [
    "/boltz/api/v1/swap",
    "payments",
    "/boltz/api/v1/swap/reverse",
    "/boltz/api/v1/swap/check",
    "/boltz/api/v1/swap/refund/UNKNOWN",
    "/boltz/api/v1/swap/status/UNKNOWN",
]


@pytest.mark.asyncio
async def test_endpoints_unauthenticated(client):
    for url in get_urls_public:
        response = await client.get(url)
        assert response.status_code == 200
    for url in get_urls_private:
        response = await client.get(url)
        assert response.status_code == 400
    # for url in post_urls_private:
    #     response = await client.post(url)
    #     assert response.status_code == 400


@pytest.mark.asyncio
async def test_endpoints_authenticated(client):
    for url in get_urls_public:
        response = await client.get(url)
        assert response.status_code == 200
    # for url in get_urls_private:
    #     response = await client.get(url)
    #     assert response.status_code == 200


#     for url in post_urls_private:
#         response = await client.post(url)
#         assert response.status_code == 200
