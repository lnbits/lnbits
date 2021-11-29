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

async def create_conference(
        conference: str,
        admin: str,
        ) -> Conference:

    assert conference != '', 'a conference id was not given'
    print('crud.py.create_conference: ', conference)

    await db.execute(
            '''
            INSERT INTO jitsi.conferences (id, admin)
            VALUES (? , ?)
            ''',
            (conference, admin),
            )

    conference = await get_conference(conference, admin)
    assert conference, 'create_conference failed'

    return conference

async def get_conference(
        conference: str,
        admin: str
        ) -> Conference:

    assert conference != '', 'conference id is null'
    assert admin != '', 'admin id is null'

    row = await db.fetchone(
            '''
            SELECT * FROM jitsi.conferences 
            WHERE id = ? AND admin = ?
            ''',
            (conference, admin))

    result = Conference(**row) if row else None
    print('crud.py.get_conference: result: ', result)

    return result

async def get_participant(
        conference: str,
        participant: str
        ) -> Participant:
    print('crud.py.get_participant')

    # rows = await db.fetchall(
    #         '''
    #         SELECT * FROM jitsi.participants
    #         '''
    #         )
    # print('crud.py.get_participant: rows', rows)

    row = await db.fetchone(
            '''
            SELECT * FROM jitsi.participants
            WHERE id = ? AND conference = ?
            ''',
            (participant, conference))
    
    return Participant(**row) if row else None

async def create_participant(
        participant_id: str,
        user_id: str,
        conference_id : str,
        wallet_id: str
) -> Participant:

    assert participant_id != '';
    assert user_id != '';
    assert conference_id != '';
    assert wallet_id != '';

    await db.execute(
        """
        INSERT INTO jitsi.participants (id, user, conference, wallet)
        VALUES (?, ?, ?, ?)
        """,
        (participant_id, user_id, conference_id, wallet_id),
    )

    participant = await get_participant(conference_id, participant_id)
    assert participant, "newly created participant couldn't be retrieved"
    return participant

