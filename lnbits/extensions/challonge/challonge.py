from lnbits.extensions.challonge.models import Tournament 
import httpx, json


# https://api.challonge.com/v1/documents/participants/create
async def challonge_add_user_to_tournament(tournament: Tournament, name: str, challonge_name: str, email: str):
    # Call to cloudflare sort of a dry-run - if success delete the domain and wait for payment
    ### SEND REQUEST TO CLOUDFLARE
    url = "https://api.challonge.com/v1/" + tournament.challonge_tournament_id + "/participants.json"
    header = {"api_key": tournament.challonge_API, "Content-Type": "application/json"}
    ch_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=header,
                json={
                    "participant[name]": name,
                    "participant[challonge_username]": challonge_name,
                    "participant[email]": email
                },
                timeout=40,
            )
            ch_response = json.loads(r.text)
        except AssertionError:
            ch_response = "Error occured"
    return ch_response