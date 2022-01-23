# TODO(nochiel) API responses should be json so that we can get named fields in the client.

from base64 import urlsafe_b64encode
from uuid import uuid4
from typing import List, Optional, Union

from lnbits.core.crud import (
        create_account,
        create_wallet,
        get_user,
        )

from . import db
from .models import Conference, Participant

async def createConference(
        conference: str,
        admin: str,
        ) -> Conference:

    assert conference != '', 'a conference id was not given'
    print('crud.py.createConference: ', conference)

    await db.execute(
            '''
            INSERT INTO jitsi.conferences (name, admin)
            VALUES (? , ?)
            ''',
            (conference, admin),
            )

    conference = await getConference(conference, admin)
    assert conference, 'createConference failed'

    return conference

async def getConference(
        name: str,
        admin: str
        ) -> Conference:

    assert name != '', 'conference id is null'
    assert admin != '', 'admin id is null'

    row = await db.fetchone(
            '''
            SELECT * FROM jitsi.conferences 
            WHERE name = ? AND admin = ?
            ''',
            (name, admin))

    result = Conference(**row) if row else None
    print('crud.py.getConference: result: ', result)

    return result

async def getParticipant(
        conference: str,
        participant: str
        ) -> Participant:
    # print('crud.py.getParticipant')

    # rows = await db.fetchall(
    #         '''
    #         SELECT * FROM jitsi.participants
    #         '''
    #         )
    # print('crud.py.getParticipant: rows', rows)

    row = await db.fetchone(
            '''
            SELECT * FROM jitsi.participants
            WHERE id = ? AND conference = ?
            ''',
            (participant, conference))

    
    # print('crud.py.getParticipant: row: ', row)
    return Participant(**row) if row else None

async def createParticipant(*,
        participantId: str,
        userId: str,
        conferenceId : str,
        walletId: str
) -> Participant:

    assert participantId   
    assert userId          
    assert conferenceId    
    assert walletId        

    await db.execute(
        """
        INSERT INTO jitsi.participants (id, user, conference, wallet)
        VALUES (?, ?, ?, ?)
        """,
        (participantId, userId, conferenceId, walletId),
    )

    participant = await getParticipant(conferenceId, participantId)
    assert participant, "newly created participant couldn't be retrieved"
    return participant

