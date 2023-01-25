"""
This handles pubkey verification according to NIP-05

if Config.nip05_verification is set to 'enabled',
the verification table will be consulted for every event addition.
If set to 'passive', the table will be consulted, but failures will only be logged.

When a kind=0 (metadata) event is saved, it will be considered a candidate
for verification if it contains a nip05 tag.

Every Config.verification_update_frequency, the verifications will be reprocessed.
"""
import asyncio
import logging
import time
import rapidjson
from datetime import datetime, timedelta
import sqlalchemy as sa

from .errors import VerificationError
from .util import Periodic, timeout
from nostr_relay.storage import get_metadata


_metadata = get_metadata()

Verification = sa.Table(
    'verification',
    _metadata,
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('identifier', sa.Text()),
    sa.Column('metadata_id', _metadata.tables['events'].c.id.type, sa.ForeignKey('events.id', ondelete='CASCADE')),
    sa.Column('verified_at', sa.TIMESTAMP()),
    sa.Column('failed_at', sa.TIMESTAMP())
)
sa.Index('identifieridx', Verification.c.identifier)
sa.Index('metadataidx', Verification.c.metadata_id)
sa.Index('verifiedidx', Verification.c.verified_at)

EventTable = _metadata.tables['events']


class Verifier(Periodic):

    def __init__(self, storage, options:dict = None):
        self.storage = storage
        self.options = options or {}
        self.options.setdefault('update_frequency', 3600)
        self.options.setdefault('expiration', 86400)
        Periodic.__init__(self, self.options['update_frequency'])
        self._candidate = None
        self._last_run = 0
        self.queue = asyncio.Queue()
        # nip05_verification can be "enabled", "disabled", or "passive"
        self.is_enabled = options.get('nip05_verification', '') == 'enabled'
        self.should_verify = options.get('nip05_verification', '') in ('enabled', 'passive')
        if self.should_verify:
            self.log = logging.getLogger(__name__)

    async def update_metadata(self, cursor, event):
        # metadata events are evaluated as candidates
        try:
            meta = rapidjson.loads(event.content)
        except Exception:
            self.log.exception("bad metadata")
        else:
            identifier = meta.get('nip05', '')
            self.log.debug("Found identifier %s in event %s", identifier, event)
            if '@' in identifier:
                # queue this identifier as a candidate
                domain = identifier.split('@', 1)[1].lower()
                if self.check_allowed_domains(domain):
                    await self.queue.put([None, identifier, 0, event.pubkey, event.id_bytes])
                    return True
                else:
                    self.log.error("Illegal domain in identifier %s", identifier)
        return False

    def check_allowed_domains(self, domain):
        if '/' in domain:
            return False
        if self.options.get('whitelist'):
            return domain in self.options['whitelist']
        elif self.options.get('blacklist'):
            return domain not in self.options['blacklist']
        return True

    async def verify(self, conn, event):
        """
        Check an event against the NIP-05
        verification table
        """
        if not self.should_verify:
            return True

        
        if event.kind == 0:
            is_candidate = await self.update_metadata(conn, event)
            if not is_candidate:
                if self.is_enabled:
                    raise VerificationError("rejected: metadata must have nip05 tag")
                else:
                    self.log.warning("Attempt to save metadata event %s from %s without nip05 tag", event.id, event.pubkey)
            else:
                return True

        query = sa.select(Verification.c.id, Verification.c.identifier, Verification.c.verified_at, Verification.c.failed_at, EventTable.c.created_at).select_from(
                sa.join(Verification, self.storage.EventTable, Verification.c.metadata_id == self.storage.EventTable.c.id, isouter=True)
            ).where(
                (self.storage.EventTable.c.pubkey == bytes.fromhex(event.pubkey))
            )

        result = await conn.execute(query)
        row = result.fetchone()

        if not row:
            if self.is_enabled:
                raise VerificationError(f"rejected: pubkey {event.pubkey} must be verified")
            else:
                self.log.warning('pubkey %s is not verified.', event.pubkey)
        else:
            vid, identifier, verified_at, failed_at, created_at = row
            self.log.debug("Checking verification for %s verified:%s created:%s", identifier, verified_at, created_at)
            now = datetime.utcnow()
            if (now - timedelta(seconds=self.options['expiration'])) > verified_at:
                # verification has expired
                if self.is_enabled:
                    raise VerificationError(f"rejected: verification expired for {identifier}")
                else:
                    self.log.warning("verification expired for %s on %s", identifier, verified_at)

            uname, domain = identifier.split('@', 1)
            domain = domain.lower()
            if not self.check_allowed_domains(domain):
                if self.is_enabled:
                    raise VerificationError(f"rejected: {domain} not allowed")
                else:
                    self.log.warning("verification for %s not allowed", identifier)
        self.log.debug("Verified %s", event.pubkey)
        return True

    async def run_once(self):
        candidates = []
        try:
            if (time.time() - self._last_run) > self.options['update_frequency']:
                self.log.debug("running batch query %s", self._last_run)
                last_verified_date = (datetime.utcnow() - timedelta(seconds=self.options['expiration']))
                query = sa.select(Verification.c.id, Verification.c.identifier, Verification.c.verified_at, EventTable.c.pubkey, Verification.c.metadata_id).select_from(
                    sa.join(Verification, self.storage.EventTable, Verification.c.metadata_id == self.storage.EventTable.c.id, isouter=True)
                ).where(
                    (EventTable.c.pubkey != None) & (Verification.c.verified_at <= last_verified_date)
                )

                async with self.db.begin() as cursor:
                    try:
                        results = await cursor.stream(query)
                        async for row in results:
                            candidates.append(row)
                    except Exception:
                        self.log.exception('batch query')
                        return
                        # vid, identifier, verified_at, pubkey = row
        except Exception:
            self.log.exception("batch_query")
            return
        if self._candidate:
            candidates.append(self._candidate)

        try:
            success, failure = await self.process_verifications(candidates)
        except Exception:
            self.log.exception("process_verifications")
        else:
            if success or failure:
                async with self.db.begin() as conn:
                    for vid, identifier, metadata_id in success:
                        if vid is None:
                            # first time verifying
                            await conn.execute(sa.insert(Verification).values({'identifier': identifier, 'metadata_id': metadata_id, 'verified_at': datetime.utcnow()}))
                        else:
                            await conn.execute(sa.update(Verification).where(Verification.c.id == vid).values({'verified_at': datetime.utcnow()}))
                    for vid, identifier, metadata_id in failure:
                        if vid is None:
                            # don't persist first time candidates
                            continue
                        else:
                            await conn.execute(sa.update(Verification).where(Verification.c.id == vid).values({'failed_at': datetime.utcnow()}))
                self.log.info("Saved success:%d failure:%d", len(success), len(failure))
        self._last_run = time.time()

    def get_aiohttp_session(self):
        import aiohttp
        return aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0), json_serialize=rapidjson.dumps)

    async def process_verifications(self, candidates):
        success = []
        failure = []
        async with self.get_aiohttp_session() as session:
            for vid, identifier, verified_at, pubkey, metadata_id in candidates:
                if not isinstance(pubkey, str):
                    pubkey = pubkey.hex()
                self.log.info("Checking verification for %s. Last verified %s", identifier, verified_at)
                uname, domain = identifier.split('@', 1)
                domain = domain.lower()
                if not self.check_allowed_domains(domain):
                    # how did this record get here?
                    self.log.warning("skipping verification for disallowed domain %s", identifier)
                    continue
                # request well-known url
                url = f'https://{domain}/.well-known/nostr.json?name={uname}'
                self.log.info("Requesting %s", url)

                try:
                    async with session.get(url) as response:
                        data = await response.json(loads=rapidjson.loads)
                    names = data['names']
                    assert isinstance(names, dict)
                except Exception:
                    self.log.exception("Failure verifying %s from %s", identifier, url)
                    failure.append([vid, identifier, metadata_id])
                else:
                    if names.get(uname, '') != pubkey:
                        self.log.warning("Could not verify %s=%s from %s", identifier, pubkey, url)
                        failure.append([vid,  identifier, metadata_id])
                    else:
                        self.log.info("Verified %s=%s from %s", identifier, pubkey, url)
                        success.append([vid, identifier, metadata_id])

        return success, failure

    async def wait_function(self):
        self._candidate = None
        try:
            async with timeout(self.options['update_frequency']):
                self._candidate = await self.queue.get()
            if self._candidate is None:
                self.running = False
            self.log.debug("Got candidate %s", self._candidate)
        except asyncio.TimeoutError:
            self.log.debug("timed out waiting for queue")

    async def start(self, db):

        if self.should_verify:
            self.log.info("Starting verification task. Interval %s", self.options['update_frequency'])
            self.db = db
            await super().start()

    def is_processing(self):
        return not self.queue.empty()
