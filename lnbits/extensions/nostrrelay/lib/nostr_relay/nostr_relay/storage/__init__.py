import sqlalchemy as sa
from nostr_relay.config import Config
from nostr_relay.util import call_from_path

__all__ = ('get_storage', 'get_metadata')


def _fix_old_config():
    if Config.db_filename or not Config.storage:
        import warnings
        warnings.warn("Please read https://code.pobblelabs.org/fossil/nostr_relay/doc/tip/docs/140upgrade.md for important upgrade information")
        Config.storage = {'sqlalchemy.url': f'sqlite+aiosqlite:///{Config.db_filename}'}
        Config.db_filename = None
        print(Config.storage)


_STORAGE = None
def get_storage(reload=False):
    """
    Return singleton instance of storage object
    """
    global _STORAGE
    if _STORAGE is None or reload:
        _fix_old_config()
        _STORAGE = call_from_path(Config.storage.get('class', 'nostr_relay.storage.db.DBStorage'), Config.storage)
    return _STORAGE


_METADATA = None
def get_metadata():
    global _METADATA
    if _METADATA is None:
        _fix_old_config()
        _METADATA = sa.MetaData()
        if 'asyncpg' in Config.storage.get('sqlalchemy.url', ''):
            from sqlalchemy.dialects.postgresql import BYTEA, JSONB
            EventTable = sa.Table(
                'events',
                _METADATA,
                sa.Column('id', BYTEA(), primary_key=True),
                sa.Column('created_at', sa.Integer()),
                sa.Column('kind', sa.Integer()), 
                sa.Column('pubkey', BYTEA()),
                sa.Column('tags', JSONB()),
                sa.Column('sig', BYTEA()),
                sa.Column('content', sa.Text()),
            )
        else:
            EventTable = sa.Table(
                'events',
                _METADATA,
                sa.Column('id', sa.BLOB(), primary_key=True),
                sa.Column('created_at', sa.Integer()),
                sa.Column('kind', sa.Integer()), 
                sa.Column('pubkey', sa.BLOB()),
                sa.Column('tags', sa.JSON()),
                sa.Column('sig', sa.BLOB()),
                sa.Column('content', sa.Text()),
            )
        sa.Index('createdidx', EventTable.c.created_at)
        sa.Index('kindidx', EventTable.c.kind),
        sa.Index('pubkeyidx', EventTable.c.pubkey)

        TagTable = sa.Table(
            'tags', 
            _METADATA,
            sa.Column('id', EventTable.c.id.type, sa.ForeignKey(EventTable.c.id, ondelete="CASCADE")), 
            sa.Column('name', sa.Text()),
            sa.Column('value', sa.Text()),
            sa.UniqueConstraint("id", "name", "value", name="unique_tag"),
        )
        sa.Index('tagidx', TagTable.c.name, TagTable.c.value)

        IdentTable = sa.Table(
            'identity',
            _METADATA,
            sa.Column('identifier', sa.Text(), primary_key=True),
            sa.Column('pubkey', sa.Text()),
            sa.Column('relays', sa.JSON()),
        )
    return _METADATA
