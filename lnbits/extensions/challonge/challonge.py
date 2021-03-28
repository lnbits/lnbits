from lnbits.extensions.challonge.models import Tournament 
import httpx, json


# https://api.challonge.com/v1/documents/participants/create
async def challonge_add_user_to_tournament(tournament: Tournament, challonge_username: str, username: str, email: str):
    ### SEND REQUEST TO CHALLONGE   
    url = "https://api.challonge.com/v1/tournaments/" + tournament.challonge_tournament_id + "/participants.json?api_key=" + tournament.challonge_api
    header = {"Content-Type": "application/x-www-form-urlencoded"}
    ch_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                url,
                headers=header,
                data={
                    "participant[challonge_username]": challonge_username,
                    "participant[name]": username,
                    "participant[email]": email
                },
                timeout=40,
            )
            ch_response = json.loads(r.text)
        except AssertionError:
            ch_response = "Error occured"
    return ch_response

# https://api.challonge.com/v1/documents/participants/delete
async def challonge_delete_user_from_tournament(tournament: Tournament, participant_id: str):
    url = "https://api.challonge.com/v1/tournaments/" + tournament.challonge_tournament_id + "/participants/"+ str(participant_id) + "?api_key=" + tournament.challonge_api
    header = {"Content-Type": "application/x-www-form-urlencoded"}
    ch_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.delete(
                url,
                headers=header,
                timeout=40,
            )
            #ch_response = json.loads(r.text)
        except AssertionError:
            ch_response = "Error occured"
    #return ch_response



async def  challonge_get_tournament_data(challonge_API : str, challonge_tournament_id: str):
    ### SEND REQUEST TO CHALLONGE   
    url = "https://api.challonge.com/v1/tournaments/" + challonge_tournament_id + ".json?include_participants=1&include_participants=1&api_key="+challonge_API
    # header = {"api_key": challonge_API, "Content-Type": "application/json"}
    ch_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                url,
                timeout=40,
            )
            ch_response = json.loads(r.text)
        except AssertionError:
            ch_response = "Error occured"
    return ch_response



async def  challonge_set_tournament_description(challonge_API : str, challonge_tournament_id: str, description: str):
    ### SEND REQUEST TO CHALLONGE   
    url = "https://api.challonge.com/v1/tournaments/" + challonge_tournament_id + ".json?api_key=" + challonge_API
    header = {"Content-Type": "application/x-www-form-urlencoded"}
    ch_response = ""
    async with httpx.AsyncClient() as client:
        try:
            r = await client.put(
                url=url,
                headers=header,
                data={
                    "tournament[description]": description
                },
                timeout=40,
            )
            ch_response = json.loads(r.text)
        except AssertionError:
            ch_response = "Error occured"
    return ch_response