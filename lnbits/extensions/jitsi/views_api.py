# Ref. UserManager extension.
# TODO(nochiel) Handle errors.
# FIXME(nochiel) Correctness? api_check_wallet_key(key_type="invoice")
# FIXME(nochiel) Use camelCase instead of snake_case or just be consistent wtf.

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

from lnbits.decorators import (
        api_check_wallet_key,
        api_validate_post_request
)

from lnbits.core.services import (
        create_invoice,
        check_invoice_status
)

from . import jitsi_ext
from .crud import (
    create_conference,
    get_conference,
    get_participant,
    create_participant
)

@jitsi_ext.route('/api/v1/conference/<conferenceId>', methods=['GET'])
@api_check_wallet_key(key_type='invoice')
async def api_jitsi_conference(conferenceId):
    assert conferenceId != '', 'conferenceId is required'

    conference = await get_conference(conferenceId)
    if conference:
        status = HTTPStatus.OK
    else:
        status = HTTPStatus.NOT_FOUND

    return jsonify(conference._asdict()) if conference else {}, status


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
    result, status = None, HTTPStatus.INTERNAL_SERVER_ERROR

    # FIXME(nochiel) An LNBits user can have different conferences that have the same name! Distinguish the wallets or make conference names unique.

    user = await get_user(g.wallet.user)
    print('api_jitsi_conferences_create', user)

    conference = await get_conference(conferenceId, user.id)  
    if conference is None:
        conference = await create_conference(conferenceId, user.id)

    assert conference is not None, 'api_jitsi_conferences_create: conference is empty!'
    status = HTTPStatus.CREATED
    result = jsonify(conference._asdict())

    # Ref. lnbits/core/views/generic.py
    wallet = None
    assert user.wallets
    for w in user.wallets:
        if w.name == conference.name:
            wallet = w
            break

    if wallet is None:
        wallet = await create_wallet(user_id = user.id, wallet_name = conference.name)
        print('api_jitsi_conference_create: created new wallet for admin :', wallet)

    assert wallet
    participant = await create_participant(
            participant_id = admin,
            user_id = user.id,
            conference_id = conferenceId,
            wallet_id = wallet.id)

    print('api_jitsi_conference_create: new admin: ', participant)
    if participant is None:
        status = HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify(conference._asdict()) , HTTPStatus.CREATED

@jitsi_ext.route('/api/v1/conference/<conferenceId>/participant/<participant_id>', methods=['GET'])
@api_check_wallet_key(key_type = 'invoice')
async def api_jitsi_conference_participant(conferenceId, participant_id):
    assert participant_id != '', 'participant_id is required'

    participant = await get_participant(conferenceId, participant_id)
    if participant:
        status = HTTPStatus.OK
    else:
        status = HTTPStatus.NOT_FOUND

    return jsonify(participant._asdict()) if participant else {}, status

@jitsi_ext.route('/api/v1/conference/<conferenceId>/pay', methods=['POST'])
@api_check_wallet_key(key_type = 'invoice')
@api_validate_post_request(
    schema={
        "payer": {"type": "string", "required": True}, 
        "payee": {"type": "string", "required": True}, 

        # Amount in sats. We assume msats aren't used.
        # TODO(nochiel) Can we validate amount > 0.
        "amount": {"type": "int", "required": True},    

        "memo": {"type": "string", "required": True}, 
    }
)
async def api_jitsi_conference_participant_pay(conferenceId):
    assert(amount > 0);
    
    print('api_jitsi_conference_participant_pay', g.data)
    payment = Payment(**g.data);
    print('api_jitsi_conference_participant_pay: payment', payment)

    payer = await getParticipant(conferenceId, payment.payer)
    assert payer

    paymentHash, paymentRequest = await create_invoice(wallet_id = payer.wallet, amount = payment.amount,)
    assert(paymentHash != '')
    assert(paymentRequest != '')


@jitsi_ext.route("/api/v1/conference/participant", methods=["POST"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema = {
        "participant": {"type": "string", "required": True}, 
        "conference": {"type": "string", "required": True}, 
    }
)
async def api_jitsi_participant_create():

    participantId, conference = g.data['participant'], g.data['conference']

    account = await create_account()
    print('api_jitsi_participant_create: new account:', account)

    user = await get_user(account.id)
    result, status = None, HTTPStatus.INTERNAL_SERVER_ERROR
    if user is not None:
        print('api_jitsi_participant_create: new user:', user)

        wallet = await create_wallet(user_id = user.id, wallet_name = conference)
        if wallet is not None:
            print('api_jitsi_participant_create: new wallet:', wallet)

            participant = await create_participant(
                    participant_id = participantId,
                    user_id = user.id,
                    conference_id = conference,
                    wallet_id = wallet.id)

            if participant is not None:
                print('api_jitsi_participant_create: new participant:', participant)
                status = HTTPStatus.CREATED
                result = jsonify(participant._asdict())

    return result, status

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
        
@jitsi_ext.route("/api/v1/conference/message", methods=["POST"])
@api_check_wallet_key(key_type="invoice")
@api_validate_post_request(
    schema={
        'from': {'type': 'string', 'empty': False, 'required': True}, # From Jitsi when the conference is started.
        'message': {'type': 'string', 'empty': False, 'required': True},       # The user/host of the conference
        'timestamp': {'type': 'int', 'empty': False, 'required': True},    
    }
)

async def api_jitsi_conference_message_push():
    m = Message(g.data['from'], g.data['from'], g.data['stamp'])












