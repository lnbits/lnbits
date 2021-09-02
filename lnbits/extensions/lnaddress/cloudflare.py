from lnbits.extensions.lnaddress.models import Domains
import httpx, json


async def cloudflare_create_record(
    domain: Domains, ip: str
):
    url = (
        "https://api.cloudflare.com/client/v4/zones/"
        + domain.cf_zone_id
        + "/pagerules"
    )
    header = {
        "Authorization": "Bearer " + domain.cf_token,
        "Content-Type": "application/json",
    }

    cf_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=header,
                json={
                    "targets": [{
                        "target": "url",
                        "constraint": {
                            "operator": "matches",
                            "value": f"*{domain.domain}/*"
                        }
                    }],
                    "actions": [{
                        "id": "forwarding_url",
                        "value": {
                            "url": f"{ip}$2",
                            "status_code": 302
                        }
                    }],
                    "status": "active"
                },
                timeout=40,
            )
            cf_response = json.loads(r.text)
        except AssertionError:
            cf_response = "Error occured"
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
            r = await client.delete(
                url + "/" + domain_id,
                headers=header,
                timeout=40,
            )
            cf_response = r.text
        except AssertionError:
            cf_response = "Error occured"
