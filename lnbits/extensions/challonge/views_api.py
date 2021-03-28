from lnbits.extensions.challonge.models import Participant, Tournament
from logging import fatal
import re
from quart import g, jsonify, request
from http import HTTPStatus
from lnbits.core import crud
import json

import httpx
from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
import uuid

from . import challonge_ext
from .crud import (
    delete_participant,
    create_tournament,
    delete_tournament,
    create_participant,
    get_participantByUsername,
    get_participant,
    get_participants,
    get_tournament,
    get_tournaments,
    update_tournament,
    claim_winning,
    get_participant_by_secret,
    set_participant_winner
)
from .challonge import (
    challonge_add_user_to_tournament,
    challonge_get_tournament_data,
    challonge_set_tournament_description,
    challonge_delete_user_from_tournament
)
from .dto import TournamentDTO, ParticipantDTO

from ..withdraw.crud import create_withdraw_link

# Tournaments


@challonge_ext.route("/api/v1/tournaments", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_tournaments() -> TournamentDTO:
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    tournamentDTOList = []
    for tournament in await get_tournaments(wallet_ids):
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
        tournamentDTOList.append(tournamentDTO)

   
    return jsonify([domain._asdict() for domain in tournamentDTOList]), HTTPStatus.OK


@challonge_ext.route("/api/v1/tournaments", methods=["POST"])
@challonge_ext.route("/api/v1/tournaments/<tournament_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "wallet": {"type": "string", "empty": False, "required": True},
        "challonge_API": {"type": "string", "empty": False, "required": True},
        "challonge_tournament_id": {"type": "string", "empty": False, "required": True},
        "signup_fee": {"type": "integer", "empty": False, "required": True},
        "webhook": {"type": "string", "empty": False, "required": False},
    }
)
async def api_tournament_create(tournament_id=None) -> TournamentDTO:
    if tournament_id:
        tournament = await get_tournament(tournament_id)

        if not tournament:
            return jsonify({"message": "tournament does not exist."}), HTTPStatus.NOT_FOUND

        if tournament.wallet != g.wallet.id:
            return jsonify({"message": "Not your tournament."}), HTTPStatus.FORBIDDEN

        tournament = await update_tournament(tournament_id=tournament_id, **g.data)
    else:
        challonge_tournament_data = await challonge_get_tournament_data(
            challonge_API=g.data["challonge_API"], challonge_tournament_id=g.data["challonge_tournament_id"]
        )
        if challonge_tournament_data == "Error occured":
            return challonge_tournament_data, HTTPStatus.BAD_REQUEST

        challonge_tournament_data = await challonge_set_tournament_description(
            challonge_API=g.data["challonge_API"],
            challonge_tournament_id=g.data["challonge_tournament_id"],
            description=challonge_tournament_data["tournament"]["description"] + " <br><i>Signups managed by Lnbits</i>",
        )
        if "errors" in challonge_tournament_data or challonge_tournament_data == "Error occured":
            return challonge_tournament_data, HTTPStatus.BAD_REQUEST

        tournament = await create_tournament(**g.data)
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
        return jsonify(tournamentDTO._asdict()), HTTPStatus.CREATED


@challonge_ext.route("/api/v1/tournaments/<tournament_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_tournament_delete(tournament_id):
    tournament = await get_tournament(tournament_id)

    if not tournament:
        return jsonify({"message": "tournament does not exist."}), HTTPStatus.NOT_FOUND

    if tournament.wallet != g.wallet.id:
        return jsonify({"message": "Not your tournament."}), HTTPStatus.FORBIDDEN

    await delete_tournament(tournament_id)

    return "", HTTPStatus.NO_CONTENT

@challonge_ext.route("/api/v1/tournaments/<tournament_id>", methods=["POST"])
@api_validate_post_request(
    schema={
        "secret": {"type": "string", "empty": False, "required": True},
    }
)
async def claim_winnings(tournament_id):
    tournament : Tournament = await get_tournament(tournament_id)
    participant : Participant = await get_participant_by_secret(g.data["secret"])
    if (tournament.id == participant.tournament):
        challonge_tournament_data = await challonge_get_tournament_data(
            challonge_API=tournament.challonge_api, challonge_tournament_id=tournament.challonge_tournament_id
        )
        if (challonge_tournament_data["tournament"]["state"] == "complete"):
            for x in challonge_tournament_data["tournament"]["participants"]:
                if (x['participant']["final_rank"] == 1):
                    if (participant.username == x['participant']["display_name"]):
                        await set_participant_winner(payment_hash=participant.id);
                        withdrawable = tournament.signup_fee * len(challonge_tournament_data["tournament"]["participants"])
                        withdraw_url = await create_withdraw_link(
                            wallet_id=tournament.wallet, 
                            title=challonge_tournament_data["tournament"]["name"],
                            max_withdrawable=withdrawable,
                            min_withdrawable=withdrawable,
                            uses=1,
                            wait_time=30,
                            is_unique=True,
                            usescsv=False
                            )
                        return jsonify({**withdraw_url._asdict(), **{"lnurl": withdraw_url.lnurl}}), HTTPStatus.CREATED
        else:
            return jsonify({"message": "Tournament not completed yet!"}), HTTPStatus.BAD_REQUEST
    else:
        return jsonify({"message:", "Participant not in the tournament"}), HTTPStatus.BAD_REQUEST

#########participants##########


@challonge_ext.route("/api/v1/participants", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_participants():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return jsonify([tournament._asdict() for tournament in await get_participants(wallet_ids)]), HTTPStatus.OK


@challonge_ext.route("/api/v1/participants/<tournament_id>", methods=["POST"])
@api_validate_post_request(
    schema={
        "tournament": {"type": "string", "empty": False, "required": True},
        "email": {"type": "string", "empty": True, "required": False},
        "challonge_username": {"type": "string", "empty": True, "required": False},
        "username": {"type": "string", "empty": False, "required": True},
    }
)
async def api_participants_new_participant(tournament_id):
    tournament = await get_tournament(tournament_id=tournament_id)

    # If the request is coming for the non-existant tournament
    if not tournament:
        return jsonify({"message": "Tournament does not exist."}), HTTPStatus.NOT_FOUND

    ## If tournament already exist in our database reject it
    if (
        await get_participantByUsername(g.data["challonge_username"],g.data["username"] ) is not None
    ):  # TODO check if g.data["participant_name"] really exist
        return (
            jsonify(
                {
                    "message": g.data["challonge_username"]
                    + " participant with this name already registered"
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    cf_response = await challonge_add_user_to_tournament(
        challonge_username=g.data["challonge_username"],
        username=g.data["username"],
        email=g.data["email"],
        tournament=tournament
    )

    if not "errors" in cf_response:
        await challonge_delete_user_from_tournament(tournament=tournament, participant_id=cf_response['participant']['id'])
    else:
        return (
            jsonify({"message": "Problem with challonge: " + cf_response["errors"][0]}),
            HTTPStatus.BAD_REQUEST,
        ) 
    

    ## ALL OK - create an invoice and return it to the user with generated secret
    sats = tournament.signup_fee
    secret = str(uuid.uuid4()) # generate a secret id string that will be passed to user to retrieve potential winnings
    payment_hash, payment_request = await create_invoice(
        wallet_id=tournament.wallet,
        amount=sats,
        memo=f"Signup for Challonge tournament {tournament.challonge_tournament_id} with username: {g.data['username']}. Your secret id is: {secret}",
        extra={"tag": "lnchallonge"},
    )  # TODO Fix memo

    participant = await create_participant(payment_hash=payment_hash, wallet=tournament.wallet, tournament=tournament.id, secret=secret, status="signup", challonge_username=g.data['challonge_username'], username=g.data['username'])

    if not participant:
        return jsonify({"message": "Participant could not be fetched."}), HTTPStatus.NOT_FOUND

    return jsonify({"payment_hash": payment_hash, "payment_request": payment_request}), HTTPStatus.OK


@challonge_ext.route("/api/v1/participants/<payment_hash>", methods=["GET"])
async def api_participant_check_payment(payment_hash):
    participant = await get_participant(payment_hash)
    try:
        status = await check_invoice_status(participant.wallet, participant.id)
        is_paid = not status.pending
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    if is_paid:
        return jsonify({"paid": True}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK


@challonge_ext.route("/api/v1/participants/<participant_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_participant_delete(participant_id):
    participant = await get_participant(participant_id)

    if not participant:
        return jsonify({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    if participant.wallet != g.wallet.id:
        return jsonify({"message": "Not your participant."}), HTTPStatus.FORBIDDEN

    await delete_participant(participant_id)

    return "", HTTPStatus.NO_CONTENT
