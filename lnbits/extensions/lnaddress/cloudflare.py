import httpx

from .models import Domains


async def cloudflare_create_record(domain: Domains, ip: str):
    url = (
        "https://api.cloudflare.com/client/v4/zones/"
        + domain.cf_zone_id
        + "/dns_records"
    )
    header = {
        "Authorization": "Bearer " + domain.cf_token,
        "Content-Type": "application/json",
    }

    cf_response = {}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=header,
                json={
                    "type": "CNAME",
                    "name": domain.domain,
                    "content": ip,
                    "ttl": 0,
                    "proxied": False,
                },
                timeout=40,
            )
            cf_response = r.json()
        except AssertionError:
            cf_response = {"error": "Error occured"}
    return cf_response


async def cloudflare_deleterecord(domain: Domains, domain_id: str):
    url = (
        "https://api.cloudflare.com/client/v4/zones/"
        + domain.cf_zone_id
        + "/dns_records"
    )
    header = {
        "Authorization": "Bearer " + domain.cf_token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(url + "/" + domain_id, headers=header, timeout=40)
            cf_response = r.text
        except AssertionError:
            cf_response = "Error occured"
        return cf_response
