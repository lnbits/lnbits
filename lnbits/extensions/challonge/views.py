from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus
from .dto import TournamentDTO, ParticipantDTO

from .challonge import (
    challonge_add_user_to_tournament,
    challonge_get_tournament_data,
    challonge_set_tournament_description,
)

from . import challonge_ext
from .crud import get_tournament

@challonge_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("challonge/index.html", user=g.user)


@challonge_ext.route("/<tournament_id>")
async def display(tournament_id):
    tournament = await get_tournament(tournament_id)
    if not tournament:
        abort(HTTPStatus.NOT_FOUND, "Tournament does not exist.")
    challonge_tournament_data = await challonge_get_tournament_data(
            challonge_API=tournament.challonge_api, challonge_tournament_id=tournament.challonge_tournament_id
        )
    tournamentDTO = TournamentDTO(
        id=tournament.id,
        wallet=tournament.wallet,
        challonge_tournament_id=tournament.challonge_tournament_id,
        signup_fee=tournament.signup_fee,
        winner_id=tournament.winner_id,
        webhook=tournament.webhook,
        name=challonge_tournament_data["tournament"]["name"],
        description=challonge_tournament_data["tournament"]["description"],
        started_at=challonge_tournament_data["tournament"]["started_at"],
        completed_at=challonge_tournament_data["tournament"]["completed_at"],
        state=challonge_tournament_data["tournament"]["state"],
        signup_cap=challonge_tournament_data["tournament"]["signup_cap"],
        participants_count=challonge_tournament_data["tournament"]["participants_count"],
    )   
    return await render_template(
        "challonge/display.html",
        tournament_id = tournamentDTO.id, 
        tournament_wallet = tournamentDTO.wallet,
        tournament_challonge_tournament_id = tournamentDTO.challonge_tournament_id,
        tournament_signup_fee = tournamentDTO.signup_fee,
        tournament_winner_id = tournamentDTO.winner_id,
        tournament_webhook = tournamentDTO.webhook,
        tournament_name = tournamentDTO.name,
        tournament_description = tournamentDTO.description,
        tournament_started_at = tournamentDTO.started_at,
        tournament_completed_at = tournamentDTO.completed_at,
        tournament_state = tournamentDTO.state,
        tournament_signup_cap = tournamentDTO.signup_cap,
        tournament_participants_count = tournamentDTO.participants_count,

    )