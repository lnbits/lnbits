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
        get_wallet,
)

from lnbits.decorators import (
        WalletTypeInfo, 
        get_key_type,
        require_admin_key,
        require_invoice_key,
)

from lnbits.core.services import (
        create_invoice,
        check_invoice_status,
        pay_invoice,
)

from . import jitsi_ext

from .crud import (
        addChatMessage,
        createConference,
        getConference,
        getParticipant,
        getAllParticipants,
        createParticipant,
)

from pydantic import BaseModel
class CreateJitsiConference(BaseModel):
    admin:         str
    conferenceId:  str

@jitsi_ext.post('/api/v1/conference', status_code = HTTPStatus.CREATED)
async def createJitsiConference(
        conferenceParams: CreateJitsiConference,
        walletType: WalletTypeInfo = Depends(require_admin_key),    
        ):

    result = None

    wallet = walletType.wallet;
    user = await get_user(wallet.user)
    assert user, f'createJitsiConference: user with id "{wallet.user}" was not found.'
    print('createJitsiConference: user: ', user)

    conference = await getConference(conferenceParams.conferenceId, user.id)  
    if conference is None:  #TODO test
        conference = await createConference(conferenceParams.conferenceId, user.id)

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
            participantId = conferenceParams.admin,
            userId = user.id,
            conferenceId = conferenceParams.conferenceId,
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
        walletType: WalletTypeInfo = Depends(require_admin_key),
        ):
    assert conferenceId, 'conference id is required'

    conference = await get_conference(conference_id)
    if conference is None:
        raise HTTPException(
                status_code = HTTPStatus.NOT_FOUND,
                detail = f'jitsi conference "{conference_id}" does not exist.'
        )

    return conference.dict()

class JitsiPayment(BaseModel):
    payer:  str
    payee:  str
    amount: int
    memo:   str

@jitsi_ext.post('/api/v1/conference/{conferenceId}/pay', status_code = HTTPStatus.CREATED)
async def pay(
        payment: JitsiPayment,
        walletType = Depends(require_invoice_key)   # TODO(nochiel) Make this work in jitsi.js.
        ):
    assert False, 'not implemented' # FIXME(nochiel) 

    print('api_jitsi_conference_participant_pay: payment', payment)
    assert payment.amount > 0, 'the amount in the payment is invalid';

    payer = await getParticipant(conferenceId, payment.payer)
    assert payer, 'the payer is not in the database'

    paymentHash, paymentRequest = await create_invoice(wallet_id = payer.wallet, amount = payment.amount,)
    assert paymentHash 
    assert paymentRequest 

    result = pay_invoice(
            wallet_id       = payer.wallet,
            payment_request = paymentRequest,
            description     = payment.memo,
            )
    assert paymentHash == result, f'bad payment hash: {result}'

@jitsi_ext.get('/api/v1/conference/{conferenceId}/participant/{participantId}/wallet',  
        status_code = HTTPStatus.OK)
async def getJitsiParticipantWallet(
        conferenceId,
        participantId,
        walletType = Depends(require_admin_key),  
        ):


    participant = await getParticipant(conferenceId, participantId)
    assert participant
    wallet = await get_wallet(participant.wallet);
    if wallet is None:
        raise HTTPException(
                status_code = HTTPStatus.NOT_FOUND,
                detail = f'wallet "{walletId}" was not found', 
                )

    print('getJitsiParticipantWallet: wallet found: ', wallet)
    return wallet


class JitsiParticipant(BaseModel):
    id: str

@jitsi_ext.post('/api/v1/conference/{conferenceId}/participant', status_code = HTTPStatus.CREATED)
async def createJitsiParticipant(conferenceId: str, jitsiParticipant: JitsiParticipant,):

    user = await create_account()
    assert user, 'we were not able to create a new user'

    print('createJitsiParticipant: new user: ', user)

    wallet = await create_wallet(user_id = user.id, wallet_name = conferenceId)
    assert wallet, 'we were not able to create a new wallet'

    print('createJitsiParticipant: new wallet: ', wallet)

    participant = await createParticipant(
            participantId = jitsiParticipant.id,
            userId = user.id,
            conferenceId = conferenceId,
            walletId = wallet.id)

    if participant is None:
        raise HTTPException(
                status_code = HTTPStatus.INTERNAL_SERVER_ERROR,
                detail = 'unable to create new jitsi participant'
                )

    print('createJitsiParticipant: new participant:', participant)

    return participant.dict()

@jitsi_ext.get('/api/v1/conference/{conferenceId}/participant/{participantId}',
        status_code = HTTPStatus.OK)
async def getJitsiParticipant(
        conferenceId, 
        participantId,
        walletType = Depends(require_admin_key)
        ):  
    print('getJitsiParticipant')

    # participants = await getAllParticipants(conferenceId)
    # print('all participants: ', participants);

    assert participantId, 'participantId is required'
    participant = await getParticipant(conferenceId, participantId)
    if participant is None:
        raise HTTPException(
                status_code = HTTPStatus.NOT_FOUND,
                detail = f'jitsi participant "{participantId}" was not found in conference "{conferenceId}"'
        )

    return participant.dict()


class JitsiChatMessage(BaseModel):
    message: str

@jitsi_ext.post("/api/v1/conference/{conferenceId}/message")
async def logChatMessage(
        chatMessage: JitsiChatMessage,
        walletType = Depends(require_admin_key)
        ):

    assert False, 'not implemented'  # FIXME(nochiel)

    assert chatMessage.message
    numberOfMessages = addChatMessage(conferenceId,)


    assert False, 'not implemented'










