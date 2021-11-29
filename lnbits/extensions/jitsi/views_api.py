# views_api.py is for you API endpoints that could be hit by another service

# add your dependencies here
from quart import g, jsonify
from http import HTTPStatus
# import json
# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

from quart import jsonify
from http import HTTPStatus

from lnbits.core.crud import (
        create_account,
        get_user,
        create_wallet,
        get_wallet
)

from lnbits.decorators import api_check_wallet_key, api_validate_post_request
# from lnbits.core.services import create_invoice, check_invoice_status

from . import jitsi_ext
from .crud import (
    create_conference,
    get_conference,
    get_participant,
    create_participant
)

@jitsi_ext.route('/api/v1/conference', methods=['POST'])
@api_check_wallet_key(key_type='invoice')
@api_validate_post_request(
        schema = {
            'conference': {'type': 'string', 'required': True},
            'admin': {'type' : 'string', 'required': True},
            }
        )
async def api_jitsi_conferences_create():
    conferenceId, admin = g.data['conference'], g.data['admin']
    conference = await get_conference(conferenceId, admin)
    print('api_jitsi_conferences_create', conference)
    if conference is None:
        conference = await create_conference(conferenceId, admin)
        assert conference != {}, 'api_jitsi_conferences_create: conference is empty!'
    return jsonify(conference._asdict()) , HTTPStatus.CREATED

@jitsi_ext.route('/api/v1/conference/<conference_id>/participant/<participant_id>', methods=['GET'])
@api_check_wallet_key(key_type = 'invoice')
async def api_jitsi_conference_participant(conference_id, participant_id):
    assert participant_id != '', 'participant_id is required'

    participant = await get_participant(conference_id, participant_id)
    if participant:
        status = HTTPStatus.OK
    else:
        status = HTTPStatus.NOT_FOUND

    return jsonify(participant._asdict()) if participant else {}, status

# Ref. UserManager
@jitsi_ext.route("/api/v1/conference/participant", methods=["POST"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema={
        "participant": {"type": "string", "empty": False, "required": True}, # From Jitsi. This will be used as the wallet_name
        "conference": {"type": "string", "empty": False, "required": True}, # From Jitsi when the conference is started.
        # "admin_id": {"type": "string", "empty": False, "required": True},       # The user/host of the conference
        # "wallet_name": {"type": "string", "empty": False, "required": True},    
        # "email": {"type": "string", "required": False},
        # "password": {"type": "string", "required": False},
    }
)
async def api_jitsi_participant_create():

    participant, conference = g.data['participant'], g.data['conference']

    account = await create_account()
    print('api_jitsi_participant_create: new account:', account)

    user = await get_user(account.id)
    assert user,  'we could not get a jitsi user for this participant'
    print('api_jitsi_participant_create: new user:', user)

    wallet = await create_wallet(user_id = user.id, wallet_name = conference)
    assert wallet, 'we could not create a wallet for this participant'
    print('api_jitsi_participant_create: new wallet:', wallet)

    participant = await create_participant(participant, user.id, conference, wallet.id)
    assert participant, 'we could not create a participant'
    print('api_jitsi_participant_create: new participant:', participant)

    return jsonify(participant._asdict()), HTTPStatus.CREATED

@jitsi_ext.route('/api/v1/conference/participant/wallet/<wallet_id>', methods=['GET'])
@api_check_wallet_key(key_type='invoice')
async def api_jitsi_participant_wallet(wallet_id):

    wallet = await get_wallet(wallet_id);
    status = HTTPStatus.OK
    if wallet is None:
        status = HTTPStatus.NOT_FOUND

    print('api_jitsi_participant_wallet: wallet found: ', wallet)
    # FIXME(nochiel) Construct a better wallet struct using properties e.g. balance().
    return jsonify(wallet._asdict()) if wallet else {}, status
        











