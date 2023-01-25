import os
import os.path
import asyncio
import sqlite3
import collections
import logging
import secrets
import threading

from time import time

import aiosqlite
import rapidjson
import sqlalchemy as sa
from sqlalchemy.engine.base import Engine

from ..event import Event, EventKind
from ..config import Config
from ..verification import Verifier
from ..auth import get_authenticator, Action
from ..errors import StorageError, AuthenticationError
from ..util import call_from_path, catchtime, Periodic
from . import get_metadata


force_hex_translation = str.maketrans('abcdef0213456789','abcdef0213456789', 'ghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')

def validate_id(obj_id):
    obj_id = str(obj_id or '').lower().strip()
    if obj_id.isalnum():
        obj_id = obj_id.translate(force_hex_translation)
        return obj_id
    return ''


class BaseStorage:
    async def add_event(self, event_json: dict, auth_token=None):
        raise NotImplentedError()

    async def subscribe(self, client_id, sub_id, filters, queue, auth_token=None, **kwargs):
        raise NotImplementedError()

    async def unsubscribe(self, client_id, sub_id=None):
        raise NotImplementedError()

    async def close(self):
        pass



class DBStorage(BaseStorage):

    def __init__(self, options):
        self.options = options
        self.db_url = options.get('sqlalchemy.url', 'sqlite+aiosqlite:///nostr.sqlite3')
        self.clients = collections.defaultdict(dict)
        self.db = None
        self.garbage_collector_task = None
        self.is_postgres = 'postgresql' in self.db_url
        self._my_token = secrets.token_hex(4)
        self.log = logging.getLogger(__name__)
        if self.is_postgres:
            # sa.event.listen(Engine, "connect", self._subscribe_to_channel)
            pass
        else:
            # add event listener to set appropriate PRAGMA items
            sa.event.listen(Engine, "connect", self._set_sqlite_pragma)

    def _set_sqlite_pragma(self, dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        pragma = '''
                PRAGMA journal_mode = wal;
                PRAGMA locking_mode = NORMAL;
                PRAGMA synchronous = normal;
                PRAGMA temp_store = memory;
                PRAGMA mmap_size = 30000000000;
                PRAGMA foreign_keys = ON;
        '''
        for stmt in pragma.split(';'):
            stmt = stmt.strip()
            if stmt:
                cursor.execute(stmt)
        cursor.close()

    def _subscribe_to_channel(self, dbapi_connection, connection_record):
        def add_listener():
            asyncio.create_task(dbapi_connection.driver_connection.add_listener('addevent', self._event_listener))
        asyncio.get_event_loop().call_later(2.0, add_listener)

    async def _event_listener(self, connection, serverpid, channel, payload):
        token, event_id = payload.split(':')
        if token != self._my_token:
            event_json = await self.get_event(event_id)
            self._notify_all(Event(**event_json))

    async def close(self):
        if self.garbage_collector_task:
            self.garbage_collector_task.cancel()
        await self.verifier.stop()
        await self.db.dispose()

    async def optimize(self):
        if not self.is_postgres:
            async with self.db.begin() as conn:
                await conn.execute(sa.text("PRAGMA analysis_limit=400"))
                await conn.execute(sa.text("PRAGMA optimize"))

    async def setup(self):
        # self.log.info("Database URL: '%s'", self.db_url)
        from sqlalchemy.ext.asyncio import create_async_engine

        self.authenticator = get_authenticator(self, Config.get('authentication', {}))

        self.verifier = Verifier(self, Config.get('verification', {}))

        self.db = create_async_engine(
            self.db_url,
            future=True,
            json_deserializer=rapidjson.loads,
            pool_pre_ping=True,
        )

        self.garbage_collector_task = start_garbage_collector(self.db)
        await self.verifier.start(self.db)

        metadata = get_metadata()
        self.EventTable = metadata.tables['events']
        self.IdentTable = metadata.tables['identity']
        TagTable = metadata.tables['tags']
        if self.is_postgres:
            from sqlalchemy.dialects.postgresql import insert
            self.tag_insert_query = insert(TagTable).on_conflict_do_nothing(index_elements=['id', 'name', 'value'])
            self.event_insert_query = insert(self.EventTable).on_conflict_do_nothing(index_elements=['id'])
        else:
            self.tag_insert_query = sa.insert(TagTable).prefix_with('OR IGNORE')
            self.event_insert_query = sa.insert(self.EventTable).prefix_with('OR IGNORE')

        self.log.debug("done setting up")

    async def get_event(self, event_id):
        """
        Shortcut for retrieving an event by id
        """
        async with self.db.begin() as conn:
            result = await conn.execute(sa.select(self.EventTable).where(self.EventTable.c.id == bytes.fromhex(event_id)))
            row = result.first()
            if row:
                return Event.from_tuple(row).to_json_object()

    async def add_event(self, event_json, auth_token=None):
        """
        Add an event from json object
        Return (status, event)
        """
        try:
            event = Event(**event_json)
        except Exception as e:
            self.log.error("bad json")
            raise StorageError("invalid: Bad JSON")

        await asyncio.get_running_loop().run_in_executor(None, self.validate_event, event)
        # check authentication
        if not await self.authenticator.can_do(auth_token, Action.save.value, event):
            raise AuthenticationError("restricted: permission denied")

        changed = False
        async with self.db.begin() as conn:
            do_save = await self.pre_save(conn, event)
            if do_save:
                result = await conn.execute(self.event_insert_query.values(
                    id=event.id_bytes,
                    created_at=event.created_at,
                    pubkey=bytes.fromhex(event.pubkey),
                    sig=bytes.fromhex(event.sig),
                    content=event.content,
                    kind=event.kind,
                    tags=event.tags,
                ))
                changed = result.rowcount == 1
                await self.post_save(conn, event, changed)
        if changed:
            self._notify_all(event)
        return event, changed

    def _notify_all(self, event):
        # notify all subscriptions
        count = 0
        with catchtime() as t:
            for client in self.clients.values():
                for sub in client.values():
                    asyncio.create_task(sub.notify(event))
                    count += 1
        if count:
            self.log.debug("notify-all took %.2fms for %d subscriptions", t(), count)

    def validate_event(self, event):
        """
        Validate basic format and signature
        """
        if Config.max_event_size and len(event.content) > Config.max_event_size:
            self.log.error("Received large event %s from %s size:%d max_size:%d",
                event.id, event.pubkey, len(event.content), Config.max_event_size
            )
            raise StorageError("invalid: 280 characters should be enough for anybody")
        if not event.verify():
            raise StorageError("invalid: Bad signature")
        if (time() - event.created_at) > Config.oldest_event:
            raise StorageError(f"invalid: {event.created_at} is too old")
        elif (time() - event.created_at) < -3600:
            raise StorageError(f"invalid: {event.created_at} is in the future")

    async def pre_save(self, conn, event):
        """
        Pre-process the event to check permissions, duplicates, etc.
        Return None to skip adding the event.
        """
        result = await conn.execute(sa.select(self.EventTable.c.id).where(self.EventTable.c.id == event.id_bytes))
        row = result.first()
        if row:
            # duplicate
            return False
        # check NIP05 verification, if enabled
        await self.verifier.verify(conn, event)

        if event.is_replaceable or event.is_paramaterized_replaceable:
            # check for older event from same pubkey
            query = sa.select(
                        self.EventTable.c.id, self.EventTable.c.created_at, self.EventTable.c.tags
                    ).where(
                        (self.EventTable.c.pubkey == bytes.fromhex(event.pubkey)) & 
                        (self.EventTable.c.kind == event.kind) & 
                        (self.EventTable.c.created_at < event.created_at)
                    )
            result = await conn.execute(query)

            delete_id = None
            if event.is_paramaterized_replaceable:
                # according to nip-33, an event with a matching "d" tag will be replaced
                # empty tags include [], [["d"]], and [["d", ""]]
                d_tag = ''
                for tag in event.tags:
                    if tag[0] == 'd':
                        if len(tag) > 1:
                            d_tag = tag[1]
                        break
                for old_id, created_at, tags in result:
                    found_tag = [tag for tag in tags if tag[0] == 'd']
                    if not d_tag:
                        if not found_tag or len(found_tag[0]) == 1 or found_tag[0][1] == '':
                            delete_id = old_id
                            old_ts = created_at
                            break
                    else:
                        tag = found_tag[0]
                        if len(tag) > 1 and tag[1] == d_tag:
                            delete_id = old_id
                            old_ts = created_at
                            break

            else:
                row = result.first()
                if row:
                    delete_id = row[0]
                    old_ts = row[1]
            if delete_id:
                self.log.info("Replacing event %s from %s@%s with %s", delete_id, event.pubkey, old_ts, event.id)
                await conn.execute(self.EventTable.delete().where(self.EventTable.c.id == delete_id))
        return True

    async def process_tags(self, conn, event):
        if event.tags:
            # update mentions
            # single-letter tags can be searched
            # delegation tags are also searched
            # expiration tags are also added for the garbage collector
            tags = set()
            for tag in event.tags:
                if tag[0] in ('delegation', 'expiration'):
                    tags.add((tag[0], tag[1]))
                elif len(tag[0]) == 1:
                    tags.add((tag[0], tag[1] if len(tag) > 1 else ''))
            if tags:
                result = await conn.execute(self.tag_insert_query,
                    [{'id': event.id_bytes, 'name': tag[0], 'value': tag[1]} for tag in tags]
                )

            if event.kind == EventKind.DELETE:
                # delete the referenced events
                for tag in event.tags:
                    name = tag[0]
                    if name == 'e':
                        event_id = tag[1]
                        query = sa.delete(self.EventTable).where((self.EventTable.c.pubkey == bytes.fromhex(event.pubkey)) & (self.EventTable.c.id == bytes.fromhex(event_id)))
                        result = await conn.execute(query)
                        self.log.info('Deleted event %s', event_id)

    async def post_save(self, conn, event, changed):
        """
        Post-process event
        (clear old metadata, update tag references)
        """

        if changed:
            if event.kind in (EventKind.SET_METADATA, EventKind.CONTACTS):
                # older metadata events can be cleared
                await conn.execute(self.EventTable.delete().where(
                        (self.EventTable.c.pubkey == bytes.fromhex(event.pubkey)) & 
                        (self.EventTable.c.kind == event.kind) & 
                        (self.EventTable.c.created_at < event.created_at)
                    )
                )
            await self.process_tags(conn, event)
            # if self.is_postgres:
            #     await conn.execute(sa.text(f"NOTIFY addevent, '{self._my_token}:{event.id}'"))

    async def run_single_query(self, query_filters):
        """
        Run a single query, yielding json events
        """
        queue = asyncio.Queue()
        sub = Subscription(self.db, '', query_filters, queue=queue, default_limit=600000, log=self.log)
        sub.prepare()
        await sub.run_query()
        while True:
            _, event = await queue.get()
            if event is None:
                break
            yield event

    async def subscribe(self, client_id, sub_id, filters, queue, auth_token=None, **kwargs):
        self.log.debug('%s/%s filters: %s', client_id, sub_id, filters)
        if sub_id in self.clients[client_id]:
            await self.unsubscribe(client_id, sub_id)

        if Config.subscription_limit and len(self.clients[client_id]) == Config.subscription_limit:
            raise StorageError("rejected: too many subscriptions")
        sub = Subscription(
                self.db,
                sub_id,
                filters,
                queue=queue,
                client_id=client_id,
                is_postgres=self.is_postgres,
                log=self.log,
                **kwargs
        )
        if sub.prepare():
            if not await self.authenticator.can_do(auth_token, Action.query.value, sub):
                raise AuthenticationError("restricted: permission denied")

            asyncio.create_task(sub.run_query())
            self.clients[client_id][sub_id] = sub
            self.log.debug("%s/%s +", client_id, sub_id)

    async def unsubscribe(self, client_id, sub_id=None):
        if sub_id:
            try:
                self.clients[client_id][sub_id].cancel()
                del self.clients[client_id][sub_id]
                self.log.debug("%s/%s -", client_id, sub_id)
            except KeyError:
                pass
        elif client_id in self.clients:
            del self.clients[client_id]

    async def num_subscriptions(self, byclient=False):
        subs = {}
        for client_id, client in self.clients.items():
            subs[client_id] = len(client)
        if byclient:
            return subs
        else:
            return {'total': sum(subs.values())}

    async def get_stats(self):
        stats = {'total': 0}
        async with self.db.begin() as conn:
            result = await conn.stream(sa.text('SELECT kind, COUNT(*) FROM events GROUP BY kind order by 2 DESC'))
            kinds = {}
            async for kind, count in result:
                kinds[kind] = count
                stats['total'] += count
            stats['kinds'] = kinds

            result = await conn.execute(sa.text('SELECT COUNT(*) FROM verification'))
            row = result.first()
            stats['num_verified'] = row[0]
            if self.is_postgres:
                result = await conn.execute(sa.text("""
                        SELECT
                            SUM(pg_total_relation_size(table_name ::text))
                        FROM (
                            -- tables from 'public'
                            SELECT table_name
                            FROM information_schema.tables
                            where table_schema = 'public' and table_type = 'BASE TABLE'
                        ) AS all_tables
                """))
                row = result.first()
                stats['db_size'] = int(row[0])
            else:
                try:
                    result = await conn.execute(sa.text('SELECT SUM("pgsize") FROM "dbstat" WHERE name in ("events", "tags")'))
                    row = result.first()
                    stats['db_size'] = row[0]
                except (sa.exc.OperationalError, sa.exc.ProgrammingError):
                    pass
        subs = await self.num_subscriptions(True)
        num_subs = 0
        num_clients = 0
        for k, v in subs.items():
            num_clients += 1
            num_subs += v
        stats['active_subscriptions'] = num_subs
        stats['active_clients'] = num_clients
        return stats

    async def get_identified_pubkey(self, identifier, domain=''):
        query = sa.select(self.IdentTable.c.pubkey, self.IdentTable.c.identifier, self.IdentTable.c.relays)
        pars = []
        if domain:
            query = query.where(self.IdentTable.c.identifier.like(f'%@{domain}'))
        if identifier:
            query = query.where(self.IdentTable.c.identifier == identifier)
        data = {
            'names': {},
            'relays': {}
        }
        self.log.debug("Getting identity for %s %s", identifier, domain)
        async with self.db.begin() as conn:
            result = await conn.stream(query)
            async for pubkey, identifier, relays in result:
                data['names'][identifier.split('@')[0]] = pubkey
                if relays:
                    data['relays'][pubkey] = relays

        return data

    async def set_identified_pubkey(self, identifier, pubkey, relays=None):
        async with self.db.begin() as conn:
            if not pubkey:
                await conn.execute(self.IdentTable.delete().where(self.IdentTable.c.identifier == identifier))
            elif not (validate_id(pubkey) and len(pubkey) == 64):
                raise StorageError("invalid public key")
            else:
                pars = [identifier, pubkey, rapidjson.dumps(relays or [])]
                await conn.execute(sa.delete(self.IdentTable).where(self.IdentTable.c.identifier == identifier))
                stmt = sa.insert(self.IdentTable).values({'identifier': identifier, 'pubkey': pubkey, 'relays': relays})
                await conn.execute(stmt)

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, ex_type, ex, tb):
        await self.close()



class Subscription:
    def __init__(self, db, sub_id, filters:list, queue=None, client_id=None, default_limit=6000, is_postgres=False, log=None):
        self.db  = db
        self.sub_id = sub_id
        self.client_id = client_id
        self.filters = filters
        self.queue = queue
        self.query_task = None
        self.default_limit = default_limit
        self.is_postgres = is_postgres
        self.log = log

    def prepare(self):
        try:
            self.query, self.filters = self.build_query(self.filters)
        except Exception:
            self.log.exception("build_query")
            return False
        return True

    def cancel(self):
        if self.query_task:
            self.query_task.cancel()

    async def run_query(self):
        self.query_task = asyncio.current_task()

        query = self.query
        self.log.debug(query)
        sub_id = self.sub_id
        queue = self.queue
        try:
            count = 0
            with catchtime() as t:
                async with self.db.connect() as conn:
                    result = await conn.stream(sa.text(query))
                    async for row in result:
                        event = Event.from_tuple(row)
                        await queue.put((sub_id, event))
                        count += 1
                await queue.put((sub_id, None))

            duration = t()
            self.log.info('%s/%s query – events:%s duration:%dms', self.client_id, self.sub_id, count, duration)
            if duration > 500:
                self.log.warning("%s/%s Long query: '%s' took %dms", self.client_id, self.sub_id, rapidjson.dumps(self.filters), duration)
        except Exception:
            self.log.exception("subscription")

    async def notify(self, event):
        # every time an event is added, all subscribers are notified.
        # this could have a performance penalty since everyone will retry their queries
        # at the same time. but overall, this may be a worthwhile optimization to reduce
        # idle load

        with catchtime() as t:
            matched = self.check_event(event, self.filters)
        duration = t()
        self.log.debug('%s/%s notify match %s %s duration:%.2fms', self.client_id, self.sub_id, event.id, matched, duration)
        if matched:
            await self.queue.put((self.sub_id, event))

    def check_event(self, event, filters):
        for filter_obj in filters:
            matched = set()
            for key, value in filter_obj.items():
                if key == 'ids':
                    matched.add(event.id in value)
                elif key == 'authors':
                    matched.add(event.pubkey in value)
                    for tag in event.tags:
                        if tag[0] == 'delegation' and tag[1] in value:
                            matched.add(True)
                elif key == 'kinds':
                    matched.add(event.kind in value)
                elif key == 'since':
                    matched.add(event.created_at >= value)
                elif key == 'until':
                    matched.add(event.created_at < value)
                elif key[0] == '#' and len(key) == 2:
                    for tag in event.tags:
                        if tag[0] == key[1]:
                            matched.add(tag[1] in value)
            if all(matched):
                return True
        return False

    def evaluate_filter(self, filter_obj, subwhere):
        for key, value in filter_obj.items():
            if key == 'ids':
                if not isinstance(value, list):
                    value = [value]
                ids = set(value)
                if ids and len(ids) < 40: # pathological queries?
                    exact = []
                    for eid in ids:
                        eid = validate_id(eid)
                        if eid:
                            if len(eid) == 64:
                                if self.is_postgres:
                                    exact.append(f"'\\x{eid}'")
                                else:
                                    exact.append(f"x'{eid}'")
                            elif len(eid) > 2:
                                if self.is_postgres:
                                    subwhere.append(f"encode(id, 'hex') LIKE '{eid}%'")
                                else:
                                    subwhere.append(f"lower(hex(id)) LIKE '{eid}%'")
                    if exact:
                        idstr = ','.join(exact)
                        subwhere.append(f'events.id IN ({idstr})')
                else:
                    # invalid query
                    raise ValueError("ids")
            elif key == 'authors' and isinstance(value, list):
                if value and len(value) < 40:
                    exact = set()
                    hexexact = set()
                    for pubkey in value:
                        pubkey = validate_id(pubkey)
                        if pubkey:
                            if len(pubkey) == 64:
                                if self.is_postgres:
                                    exact.add(f"'\\x{pubkey}'")
                                else:
                                    exact.add(f"x'{pubkey}'")
                                hexexact.add(f"'{pubkey}'")
                            # no prefix searches, for now
                    if exact:
                        astr = ','.join(exact)
                        subwhere.append(f"(pubkey IN ({astr}) OR id IN (SELECT id FROM tags WHERE name = 'delegation' AND value IN ({','.join(hexexact)})))")
                    else:
                        raise ValueError("authors")
                else:
                    # query with empty list should be invalid
                    raise ValueError("authors")
            elif key == 'kinds':
                if isinstance(value, list) and all(isinstance(k, int) for k in value):
                    subwhere.append('kind IN ({})'.format(','.join(str(int(k)) for k in value)))
                else:
                    raise ValueError("kinds")
            elif key == 'since':
                if value:
                    subwhere.append('created_at >= %d' % int(value))
                else:
                    raise ValueError("since")
            elif key == 'until':
                if value:
                    subwhere.append('created_at < %d' % int(value))
                else:
                    raise ValueError("until")
            elif key == 'limit' and isinstance(value, int):
                filter_obj['limit'] = min(max(value, 0), self.default_limit)
            elif key[0] == '#' and len(key) == 2 and value:
                pstr = []
                for val in set(value):
                    if val:
                        val = val.replace("'", "''")
                        pstr.append(f"'{val}'")
                if pstr:
                    pstr = ','.join(pstr)
                    subwhere.append(f"id IN (SELECT id FROM tags WHERE name = '{key[1]}' AND value IN ({pstr})) ")
        return filter_obj

    def build_query(self, filters):
        select = '''
            SELECT id, created_at, kind, pubkey, tags, sig, content FROM events
        '''
        where = set()
        limit = None
        new_filters = []
        for filter_obj in filters:
            subwhere = []
            try:
                filter_obj = self.evaluate_filter(filter_obj, subwhere)
            except ValueError:
                self.log.debug("bad query %s", filter_obj)
                filter_obj = {}
                subwhere = []
            if subwhere:
                subwhere = ' AND '.join(subwhere)
                where.add(subwhere)
            else:
                where.add('false')
            if 'limit' in filter_obj:
                limit = filter_obj['limit']
            new_filters.append(filter_obj)
        if where:
            select += ' WHERE (\n\t'
            select += '\n) OR (\n'.join(where)
            select += ')'
        if limit is None:
            limit = self.default_limit
        select += f'''
            LIMIT {limit}
        '''
        return select, new_filters


class BaseGarbageCollector(Periodic):
    def __init__(self, db, **kwargs):
        self.log = logging.getLogger("nostr_relay.db:gc")
        self.db = db
        self.running = True
        self.collect_interval = kwargs.get('collect_interval', 300)
        super().__init__(self.collect_interval)
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def collect(self, db):
        pass

    async def start(self):
        self.log.info("Starting garbage collector %s. Interval %s", self.__class__.__name__, self.collect_interval)
        await super().start()

    async def run_once(self):
        collected = 0
        try:
            async with self.db.begin() as conn:
                collected = await self.collect(conn)
            if collected:
                self.log.info("Collected garbage (%d events)", collected)
        except sqlite3.OperationalError as e:
            self.log.exception("collect")
            self.running = False
        except Exception:
            self.log.exception("collect")


class QueryGarbageCollector(BaseGarbageCollector):
    query = '''
        DELETE FROM events WHERE events.id IN
        (
            SELECT events.id FROM events
            LEFT JOIN tags on tags.id = events.id
            WHERE 
                (kind >= 20000 and kind < 30000)
            OR
                (tags.name = 'expiration' AND tags.value < '%NOW%')
        )
    '''

    async def collect(self, conn):
        result = await conn.execute(sa.text(self.query.replace('%NOW%', str(int(time())))))
        return max(0, result.rowcount)


def start_garbage_collector(db, options=None):
    options = options or Config.garbage_collector
    if options:
        gc_obj = call_from_path(options.pop("class", "nostr_relay.storage.db.QueryGarbageCollector"), db, **options)
        return asyncio.create_task(gc_obj.start())


