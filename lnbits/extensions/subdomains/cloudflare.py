import httpx

from .models import Domains


async def cloudflare_create_subdomain(
    domain: Domains, subdomain: str, record_type: str, ip: str
):
    # Call to cloudflare sort of a dry-run - if success delete the domain and wait for payment
    ### SEND REQUEST TO CLOUDFLARE
    url = (
        "https://api.cloudflare.com/client/v4/zones/"
        + domain.cf_zone_id
        + "/dns_records"
    )
    header = {
        "Authorization": "Bearer " + domain.cf_token,
        "Content-Type": "application/json",
    }
    aRecord = subdomain + "." + domain.domain
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            headers=header,
            json={
                "type": record_type,
                "name": aRecord,
                "content": ip,
                "ttl": 0,
                "proxied": False,
            },
            timeout=40,
        )
        r.raise_for_status()
        return r.json()


async def cloudflare_deletesubdomain(domain: Domains, domain_id: str):
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
        await client.delete(url + "/" + domain_id, headers=header, timeout=40)
