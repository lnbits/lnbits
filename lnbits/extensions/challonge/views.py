from quart import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from http import HTTPStatus

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
    return await render_template(
        "tournaments/display.html",
        tournament_id=tournament.id,
        tournament_name=tournament.tournament_name,
        tournament_status=tournament.status,
        tournament_signupfee=tournament.signup_fee,
        tournament_prize_pool=tournament.prize_pool,
    )