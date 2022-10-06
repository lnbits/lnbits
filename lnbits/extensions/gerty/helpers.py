import httpx

async def get_mempool_recommended_fees(gerty):
    if isinstance(gerty.mempool_endpoint, str):
        async with httpx.AsyncClient() as client:
            r = await client.get(gerty.mempool_endpoint + "/api/v1/fees/recommended")
    return r.json()