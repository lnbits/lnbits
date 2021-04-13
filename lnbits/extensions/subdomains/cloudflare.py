from lnbits.extensions.subdomains.models import Domains
import httpx, json


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
    cf_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=header,
                json={
                    "type": record_type,
                    "name": aRecord,
                    "content": ip,
                    "ttl": 0,
                    "proxed": False,
                },
                timeout=40,
            )
            cf_response = json.loads(r.text)
        except AssertionError:
            cf_response = "Error occured"
    return cf_response


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
        try:
            r = await client.delete(
                url + "/" + domain_id,
                headers=header,
                timeout=40,
            )
            cf_response = r.text
        except AssertionError:
            cf_response = "Error occured"
