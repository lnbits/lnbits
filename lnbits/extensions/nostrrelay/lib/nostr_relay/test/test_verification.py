import time
import rapidjson
import os.path
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from . import BaseTestsWithStorage

from nostr_relay.storage import get_storage
from nostr_relay.config import Config
from nostr_relay.verification import Verifier
from nostr_relay.errors import VerificationError


PK1 = 'f6d7c79924aa815d0d408bc28c1a23af208209476c1b7691df96f7d7b72a2753'
PK2 = '8f50290eaa19f3cefc831270f3c2b5ddd3f26d11b0b72bc957067d6811bc618d'


class MockSessionGet:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self): 
        return self.response
  
    async def __aexit__(self, exc_type, exc, tb): 
        pass


class VerificationTests(BaseTestsWithStorage):
    def make_profile(self, privkey, identifier=None):
        meta = {}
        if identifier:
            meta['nip05'] = identifier

        event = self.make_event(privkey, content=rapidjson.dumps(meta), kind=0, as_dict=False)
        return event

    async def test_disabled(self):
        async with self.storage.db.begin() as conn:
            assert await self.storage.verifier.verify(conn, self.make_profile(PK1))

    async def test_enabled_unverified(self):
        verifier = Verifier(self.storage, {'nip05_verification': 'enabled', 'blacklist': 'baddomain.biz'})

        async with self.storage.db.begin() as conn:
            with self.assertRaises(VerificationError) as e:
                profile = self.make_profile(PK1, identifier='test@localhost')
                profile.content = 'abcd'
                await verifier.verify(conn, profile)
            assert e.exception.args[0] == 'rejected: metadata must have nip05 tag'

            with self.assertRaises(VerificationError) as e:
                await verifier.verify(conn, self.make_profile(PK1))
            assert e.exception.args[0] == 'rejected: metadata must have nip05 tag'

            # bad domains
            with self.assertRaises(VerificationError) as e:
                event = self.make_profile(PK1, identifier='test@baddomain.biz')
                await verifier.verify(conn, event)
            assert e.exception.args[0] == 'rejected: metadata must have nip05 tag'

            with self.assertRaises(VerificationError) as e:
                event = self.make_profile(PK1, identifier='test@localhost/foo')
                await verifier.verify(conn, event)
            assert e.exception.args[0] == 'rejected: metadata must have nip05 tag'

            with self.assertRaises(VerificationError) as e:
                await verifier.verify(conn, self.make_event(PK1, kind=1, as_dict=False))
            assert e.exception.args[0] == 'rejected: pubkey 5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d must be verified'

    async def test_enabled_candidate(self):
        verifier = Verifier(self.storage, {'nip05_verification': 'enabled', 'blacklist': 'baddomain.biz'})

        async with self.storage.db.begin() as conn:
            assert await verifier.verify(conn, self.make_profile(PK1, identifier='test@localhost'))

            verifier = Verifier(self.storage, {'nip05_verification': 'passive', 'blacklist': 'baddomain.biz'})
            assert await verifier.verify(conn, self.make_profile(PK1, identifier='test@localhost'))

            assert await verifier.verify(conn, self.make_profile(PK1))


    def mock_session(self, mock):
        response = AsyncMock()

        session = MagicMock()
        session.get.return_value.__aenter__.return_value = SimpleNamespace(json=response)

        mock.return_value.__aenter__.return_value = session
        return response

    @patch('nostr_relay.verification.Verifier.get_aiohttp_session')
    async def test_process_verifications(self, mock):
        verifier = Verifier(self.storage, {'nip05_verification': 'enabled', 'blacklist': 'baddomain.biz'})

        response = self.mock_session(mock)

        async with self.storage.db.begin() as conn:
            assert await verifier.verify(conn, self.make_profile(PK1, identifier='test@localhost'))
            candidate = await verifier.queue.get()

            # returns bad json
            for resp in ('.', {}, {'names': 'foo'}, {'names': {'test': '1234'}}):
                response.return_value = resp
                success, failure = await verifier.process_verifications([candidate])

                assert failure[0][1] == 'test@localhost'
                assert not success

            # good json
            pubkey = candidate[3]

            response.return_value = {'names': {'test': pubkey}}
            success, failure = await verifier.process_verifications([candidate])

            assert success

            # bad domain
            candidate[1] = 'test@baddomain.biz'
            success, failure = await verifier.process_verifications([candidate])

            assert not failure
            assert not success

    @patch('nostr_relay.verification.Verifier.get_aiohttp_session')
    async def test_verify_verified(self, mock):
        """
        Test that a verified identity can post
        """
        response = self.mock_session(mock)
        response.return_value = {'names': {'test': '5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d'}}

        verifier = Verifier(self.storage, {'nip05_verification': 'enabled'})

        profile_event = self.make_profile(PK1, identifier='test@localhost')
        await self.storage.add_event(profile_event.to_json_object())
        await self.storage.add_event(self.make_profile(PK2, identifier='foo@localhost').to_json_object())
        async with self.storage.db.begin() as conn:
            assert await verifier.verify(conn, profile_event)
            asyncio.create_task(verifier.start(self.storage.db))
            await asyncio.sleep(1)
            await verifier.stop()

            assert await verifier.verify(conn, self.make_event(PK1, as_dict=False, kind=1, content='yes'))

    @patch('nostr_relay.verification.Verifier.get_aiohttp_session')
    async def test_batch_query_expiration(self, mock):
        """
        Test that the batch query reverifies accounts
        """
        response = self.mock_session(mock)
        response.return_value = {'names': {'test': '5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d'}}

        verifier = Verifier(self.storage, {'nip05_verification': 'enabled', 'expiration': 2, 'update_frequency': 1})

        profile_event = self.make_profile(PK1, identifier='test@localhost')
        await self.storage.add_event(profile_event.to_json_object())
        await self.storage.add_event(self.make_profile(PK2, identifier='foo@localhost').to_json_object())
        async with self.storage.db.begin() as conn:
            assert await verifier.verify(conn, profile_event)
            asyncio.create_task(verifier.start(self.storage.db))
            await asyncio.sleep(1)

            assert await verifier.verify(conn, self.make_event(PK1, as_dict=False, kind=1, content='yes'))
            await asyncio.sleep(1.2)
            assert await verifier.verify(conn, self.make_event(PK1, as_dict=False, kind=1, content='yes'))
            await verifier.stop()
