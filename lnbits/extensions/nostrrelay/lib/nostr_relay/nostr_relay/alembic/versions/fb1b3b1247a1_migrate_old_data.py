"""Migrate old data

Revision ID: fb1b3b1247a1
Revises: e748549d8d91
Create Date: 2023-01-13 15:36:06.861535

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError, ProgrammingError
from nostr_relay.event import Event
from rapidjson import loads, dumps


# revision identifiers, used by Alembic.
revision = 'fb1b3b1247a1'
down_revision = 'e748549d8d91'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    metadata_obj = sa.MetaData()
    metadata_obj.reflect(bind=connection)
    if 'event' not in metadata_obj.tables:
        print("Old data does not exist")
        return

    insert = sa.insert(sa.table('events',
        sa.column('id'),
        sa.column('created_at'),
        sa.column('content'),
        sa.column('kind'),
        sa.column('tags'),
        sa.column('sig'),
        sa.column('pubkey'),
    ))
    tag_insert = sa.insert(sa.table('tags',
        sa.column('id'),
        sa.column('name'),
        sa.column('value')
    ))
    count = 0
    for event_id, event_json in result:
        event = Event(**loads(event_json))
        connection.execute(insert.values([{
                'id': event.id_bytes,
                'created_at': event.created_at,
                'pubkey': bytes.fromhex(event.pubkey),
                'sig': bytes.fromhex(event.sig),
                'content': event.content,
                'kind': event.kind,
                'tags': dumps(event.tags),
            }])
        )
        tags = set()
        for tag in event.tags:
            if tag[0] in ('delegation', 'expiration'):
                tags.add((tag[0], tag[1]))
            elif len(tag[0]) == 1:
                tags.add((tag[0], tag[1]))
        if tags:
            result = connection.execute(tag_insert,
                [{'id': event.id_bytes, 'name': tag[0], 'value': tag[1]} for tag in tags]
            )
        count += 1
    print(f"Migrated {count} events")


def downgrade() -> None:
    pass
