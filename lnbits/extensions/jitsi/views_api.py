# Ref. UserManager extension.
# TODO(nochiel) Handle errors.
# TODO(nochiel) Remove print statements. FIXME Replace print with logging.
# FIXME(nochiel) Use camelCase instead of snake_case or just be consistent wtf.

# FIXME(nochiel) Port to FastAPI
# - [ ] Remove references to `g`.

# TODO(nochiel) TEST
# - [ ] What happens if the admin joins the conference after starting the conference e.g. from a different tab.

from fastapi import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from http import HTTPStatus

from lnbits.core.crud import (
        create_account,
        get_user,
        create_wallet,
        get_wallet
)

from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from lnbits.core.services import (
        create_invoice,
        check_invoice_status
)

from . import jitsi_ext

from .crud import (
    createConference,
    getConference,
    getParticipant,
    createParticipant
)

from pydantic import BaseModel
class CreateJitsiConference(BaseModel):
    admin:         str
    conferenceId:  str

@jitsi_ext.post('/api/v1/conference', status_code = HTTPStatus.CREATED)
async def createJitsiConference(
        createConference: CreateJitsiConference,
        walletInfo: WalletTypeInfo = Depends(require_admin_key),    
        ):

    result = None

    wallet = walletInfo.wallet;
    assert wallet
    user = await get_user(wallet.user)
    assert user, f'createJitsiConference: user with id "{wallet.user}" was not found.'
    print('createJitsiConference: ', user)

    conference = await getConference(createConference.conferenceId, user.id)  
    if conference is None:  #TODO test
        conference = await create_conference(createConference.conferenceId, user.id)

    assert conference is not None, 'createJitsiConference: failed to get/create conference!'
    result = conference.dict()

    # Ref. lnbits/core/views/generic.py
    conferenceWallet = None
    assert user.wallets
    for w in user.wallets:
        if w.name == conference.name:
            conferenceWallet = w
            break

    if conferenceWallet is None:
        conferenceWallet = await create_wallet(user_id = user.id, wallet_name = conference.name)
        print('createJitsiConference: created new wallet for admin : ', conferenceWallet)

    assert conferenceWallet
    participant = await createParticipant(
            participantId = createConference.admin,
            userId = user.id,
            conferenceId = createConference.conferenceId,
            walletId = conferenceWallet.id)

    print('createJitsiConference: new admin set for conference: ', participant)
    if participant is None:
        raise HTTPException(
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR,
                detail = 'LNBits Jitsi admin participant was not created'
                )

    return result

@jitsi_ext.get('/api/v1/conference/{conferenceId}', status_code = HTTPStatus.OK)
async def api_jitsi_conference(
        conferenceId,
        walletInfo: WalletTypeInfo = Depends(require_admin_key),
        ):
    assert conferenceId != '', 'conference id is required'

    conference = await get_conference(conference_id)
    if conference is None:
        raise HTTPException(
                status_code = HTTPStatus.NOT_FOUND,
                detail = f'jitsi conference "{conference_id}" does not exist.'
        )

    return conference.dict()


@jitsi_ext.get('/api/v1/conference/{conference_id}/participant/{participant_id}',
        status_code = HTTPStatus.OK)
async def api_jitsi_conference_participant(conference_id, participant_id,
        walletInfo: WalletTypeInfo = Depends(require_admin_key)
        ):  

    assert participant_id, 'participant_id is required'
    participant = await getParticipant(conference_id, participant_id)
    if participant is None:
        raise HTTPException(
                status_code = HTTPStatus.NOT_FOUND,
                detail = f'jitsi participant "{participant_id}" was not found in conference "{conference_id}"'
        )

    return participant.dict()

@jitsi_ext.post('/api/v1/conference/<conferenceId>/pay', status_code = HTTPStatus.CREATED)
# @api_check_wallet_key(key_type = 'invoice')
# @api_validate_post_request(
        #     schema={
        #         "payer": {"type": "string", "required": True}, 
        #         "payee": {"type": "string", "required": True}, 
        # 
        #         # Amount in sats. We assume msats aren't used.
        #         # TODO(nochiel) Can we validate amount > 0.
        #         "amount": {"type": "int", "required": True},    
        # 
        #         "memo": {"type": "string", "required": True}, 
        #     }
        # )
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


@jitsi_ext.post("/api/v1/conference/participant", status_code = HTTPStatus.CREATED)
# @api_check_wallet_key(key_type="invoice")
# @api_validate_post_request(
        #     schema = {
        #         "participant": {"type": "string", "required": True}, 
        #         "conference": {"type": "string", "required": True}, 
        #     }
        # )
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

@jitsi_ext.get('/api/v1/conference/participant/wallet/<wallet_id>',
        status_code = HTTPStatus.OK)
# @api_check_wallet_key(key_type='invoice')
async def api_jitsi_participant_wallet(wallet_id):

    wallet = await get_wallet(wallet_id);
    status = HTTPStatus.OK
    if wallet is None:
        status = HTTPStatus.NOT_FOUND

    print('api_jitsi_participant_wallet: wallet found: ', wallet)
    # FIXME(nochiel) Construct a better wallet struct using properties e.g. balance().
    return jsonify(wallet._asdict()) if wallet else {}, status
        
@jitsi_ext.post("/api/v1/conference/message")
# @api_check_wallet_key(key_type="invoice")
# @api_validate_post_request(
        #     schema={
        #         'from': {'type': 'string', 'empty': False, 'required': True}, # From Jitsi when the conference is started.
        #         'message': {'type': 'string', 'empty': False, 'required': True},       # The user/host of the conference
        #         'timestamp': {'type': 'int', 'empty': False, 'required': True},    
        #     }
        # )

async def api_jitsi_conference_message_push():
    m = Message(g.data['from'], g.data['from'], g.data['stamp'])












