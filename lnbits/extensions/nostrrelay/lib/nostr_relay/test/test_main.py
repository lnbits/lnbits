import asyncio
import os.path
import os
import unittest
import logging
import time
import threading

import sqlalchemy as sa
from falcon import testing, errors

from nostr_relay.config import Config
from nostr_relay.web import create_app
from nostr_relay.storage import get_storage
from nostr_relay.auth import Authenticator
from nostr_relay.event import Event, PrivateKey
from nostr_relay.errors import StorageError


from nostr_relay import __version__

from . import BaseTestsWithStorage

PK1 = 'f6d7c79924aa815d0d408bc28c1a23af208209476c1b7691df96f7d7b72a2753'
PK2 = '8f50290eaa19f3cefc831270f3c2b5ddd3f26d11b0b72bc957067d6811bc618d'

EVENTS = [
    {"id": "0d7721e1ee4a343f623cfb86374cc2d4688784bd264b5bc26079843169f28d88", "pubkey": "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d", "created_at": 1672325827, "kind": 0, "tags": [], "content": "{\"name\": \"test1\", \"nip05\": \"test@st.germa.in\", \"description\": \"test account\"}", "sig": "bb748c84613eb9073d4dc99fc6df0c96aa43fd380c2c058a71f67a8f0fe012e5c40d74aa81c4c233a092eb307c7b5b8a4499e3403e0a54469ad1db1575916cf5"},
    {"id": "46981a47c7e28f720a2609a5872c62b6e8b9ae612db3f8320b68be446ad77e11", "pubkey": "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d", "created_at": 1672412227, "kind": 1, "tags": [], "content": "hello world", "sig": "d81c89008bcb9e27a0fc3454fef6b481034cfeaaf0c48e65299fa9af85e35e2c27e36a2478ba8a402a14ed3c332e4b7a43d7682e9d5baea0a7a9083fc26dba00"},
    {"id": "ea54cf0e912b3fc482ee842195c8db670df6d958b2ae86e039b7c56690d81ef9", "pubkey": "44c7a871ce6224d8d274b494f8f68827cb966e3aaba723a14db8dd22e0542e7d", "created_at": 1672325827, "kind": 1, "tags": [["p", "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d"], ["e", "46981a47c7e28f720a2609a5872c62b6e8b9ae612db3f8320b68be446ad77e11"]], "content": "hello pk1", "sig": "73106b28855337fd2546a04d02cec76c1673428811acc42bc2b69cedc03554024b8ca8bb841b9991b728db3be89760486be147b2fb03e3f4e16ca83a356d56ef"},
]

REPLACE_EVENTS = [
    {"id": "ae0816fff8d0363a189f22cf8ade674c386963cab39d68b28b19a7b5eae90cbd", "pubkey": "44c7a871ce6224d8d274b494f8f68827cb966e3aaba723a14db8dd22e0542e7d", "created_at": 1672324827, "kind": 11111, "tags": [], "content": "replace me", "sig": "0f9bfe1047dfc37a020c8b0196703ec553b22cf9b6258c3e7b4e8a67991fd788813018e90558f18d3337e48152e2e0fa50a8b925e35ad91a8db603c517092f28"},
    {"id": "2270926268812f4886d4499bc9a29a84223e5554985496843278e1472fab3837", "pubkey": "44c7a871ce6224d8d274b494f8f68827cb966e3aaba723a14db8dd22e0542e7d", "created_at": 1672326827, "kind": 11111, "tags": [], "content": "replaced", "sig": "d48846d5a7d344d60ba66c97ebe923d5f61b2e3970fd92682795ba5ff91137f288fd234ce5cafdaddc9b0f6408085c46c7255994eb3850e99ebbc05e3108f2c6"}
]

DELEGATION_EVENT = { "id": "a080fd288b60ac2225ff2e2d815291bd730911e583e177302cc949a15dc2b2dc",  "pubkey": "62903b1ff41559daf9ee98ef1ae67cc52f301bb5ce26d14baba3052f649c3f49",  "created_at": 1660896109,  "kind": 1, "tags":[["delegation","86f0689bd48dcd19c67a19d994f938ee34f251d8c39976290955ff585f2db42e","kind=1&created_at>1640995200","c33c88ba78ec3c760e49db591ac5f7b129e3887c8af7729795e85a0588007e5ac89b46549232d8f918eefd73e726cb450135314bfda419c030d0b6affe401ec1"]],  "content": "Hello world",  "sig": "cd4a3cd20dc61dcbc98324de561a07fd23b3d9702115920c0814b5fb822cc5b7c5bcdaf3fa326d24ed50c5b9c8214d66c75bae34e3a84c25e4d122afccb66eb6"}



class DBTests(BaseTestsWithStorage):
    async def test_add_bad_event(self):
        with self.assertRaises(StorageError) as e:
            await self.storage.add_event([1,2,3])
        assert e.exception.args[0] == 'invalid: Bad JSON'

        with self.assertRaises(StorageError) as e:
            evt = self.make_event(PK1, pubkey=PK2)
            await self.storage.add_event(evt)
        assert e.exception.args[0] == 'invalid: Bad signature'

        with self.assertRaises(StorageError) as e:
            evt = self.make_event(PK1, created_at=123)
            await self.storage.add_event(evt)
        assert e.exception.args[0] == 'invalid: 123 is too old'

        with self.assertRaises(StorageError) as e:
            t = int(time.time() + 86400)
            evt = self.make_event(PK1, created_at=t)
            await self.storage.add_event(evt)
        assert e.exception.args[0] == f'invalid: {t} is in the future'

        with self.assertRaises(StorageError) as e:
            evt = self.make_event(PK1, content='x' * 64000)
            await self.storage.add_event(evt)
        assert e.exception.args[0] == f'invalid: 280 characters should be enough for anybody'

    async def test_add_event(self):
        event, changed = await self.storage.add_event(EVENTS[0])
        assert event.id == EVENTS[0]['id']
        assert changed

        event, changed = await self.storage.add_event(EVENTS[0])
        assert event.id == EVENTS[0]['id']
        assert not changed

    async def test_replaceable_event(self):
        evt1 = self.make_event(PK1, kind=11111, content='event 1', tags=[['e', '1234'], ['foo', 'bar']])
        event, changed = await self.storage.add_event(evt1)
        assert event.id == evt1['id']

        evt2 = self.make_event(PK1, kind=11111, content='event 2')
        event, changed = await self.storage.add_event(evt2)
        assert event.id == evt2['id']

        # first event should be gone
        evt = await self.storage.get_event(evt1['id'])
        assert evt is None

        # an event from a different pubkey won't replace event 2
        evt3 = self.make_event(PK2, kind=11111, content='event 3')
        event, changed = await self.storage.add_event(evt2)
        assert event.id == evt2['id']
        evt = await self.storage.get_event(evt2['id'])
        assert evt['content'] == 'event 2'

    async def test_expiration_tag(self):
        expiring_event = {"id": "075040fbf395db975fccf36948908474994f70c871be0d1755459851438577d1", "pubkey": "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d", "created_at": 1672325827, "kind": 1, "tags": [["expiration", 1672329427]], "content": "this will expire", "sig": "77509c595b5e4e86a74dc1fa0b4a484a8bca6acc89e2e32b9794c9e0c59a0313521295e8c4b6b844be5ce83bab2cb7230bc0d9761fbf3845a2cd04dab2d70cda"}
        distant_future_event = {"id": "eb41e9b29e08aa73bb73ebe6daa73ce59b484cfe62b95449d0bcd551186ee61c", "pubkey": "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d", "created_at": 1672325827, "kind": 1, "tags": [["expiration", 1987990393]], "content": "this will expire in a long time", "sig": "046d4ad7eb8b7b64528cfcde2f4171d8ad375467447a134dbd14b764973a237f977c3f8a5d3ba6cfcc5ed07d0fa68b222a18c81c2c9c115bdd55734c7006877b"}

        await self.storage.add_event(expiring_event)
        await self.storage.add_event(distant_future_event)
        assert (await self.storage.get_event(expiring_event["id"]))['id'] == expiring_event['id']
        assert (await self.storage.get_event(distant_future_event["id"]))['id'] == distant_future_event['id']

        # stop and restart garbage collector to have it run immediately
        from nostr_relay.storage.db import start_garbage_collector
        # self.storage.garbage_collector.stop()
        self.storage.garbage_collector = start_garbage_collector(self.storage.db, {'collect_interval': 2})

        await asyncio.sleep(2.5)
        assert (await self.storage.get_event(expiring_event["id"])) is None
        self.storage.garbage_collector.cancel()
        assert (await self.storage.get_event(distant_future_event["id"]))['id'] == distant_future_event['id']

    async def test_ephemeral_event(self):
        from nostr_relay.storage.db import start_garbage_collector
        self.storage.garbage_collector_task = start_garbage_collector(self.storage.db, {'collect_interval': 2})
        ephemeral_event = {"id": "2696df86ce47142b7d272408e222b7a9fc4b2cc3a428bf2debf5d730ae2f42c7", "pubkey": "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d", "created_at": 1672325827, "kind": 22222, "tags": [], "content": "ephemeral", "sig": "66f8a055bb3c3fc3fe0ca0ead4d5558d69627dc4f40c7320228d9e4c266509f6ac8a2ff085abbd1a9d3b0c733529bf3fcd87d43f731990467181ed1995aad5bc"}

        assert (await self.storage.add_event(ephemeral_event))[1]
        assert (await self.storage.get_event(ephemeral_event['id']))['id'] == '2696df86ce47142b7d272408e222b7a9fc4b2cc3a428bf2debf5d730ae2f42c7'
        await asyncio.sleep(2.2)
        assert (await self.storage.get_event(ephemeral_event['id'])) is None

    async def test_delete_event(self):
        evt1 = self.make_event(PK1, kind=1, content='delete me')
        event, changed = await self.storage.add_event(evt1)

        delete_event = self.make_event(PK2, kind=5)
        await self.storage.add_event(delete_event)
        assert (await self.storage.get_event(evt1['id'])) is not None

        delete_event = self.make_event(PK2, kind=5, tags=[['e', evt1['id']]])
        await self.storage.add_event(delete_event)
        assert (await self.storage.get_event(evt1['id'])) is not None

        delete_event = self.make_event(PK1, kind=5, tags=[['e', evt1['id']]])
        await self.storage.add_event(delete_event)
        assert (await self.storage.get_event(evt1['id'])) is None

    async def test_delegation_event(self):
        event, changed = await self.storage.add_event(DELEGATION_EVENT)
        assert changed
        import json
        async for event in self.storage.run_single_query([{"authors": ["86f0689bd48dcd19c67a19d994f938ee34f251d8c39976290955ff585f2db42e"]}]):
            assert event.id == DELEGATION_EVENT['id']

    async def test_get_stats(self):
        for evt in EVENTS:
            await self.storage.add_event(evt)

        queue = asyncio.Queue()
        sub = await self.storage.subscribe('test', 'test', [{'kinds': [1]}], queue)
        stats = await self.storage.get_stats()
        assert stats['total'] == 3
        assert stats['active_subscriptions'] == 1
        await self.storage.unsubscribe('test')

    async def test_set_idp_identifier(self):
        await self.storage.set_identified_pubkey('test@localhost', '5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d', relays='ws://localhost:6969')

        data = await self.storage.get_identified_pubkey('test@localhost')
        assert data == {
            'names': {
                'test': '5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d'
            },
            'relays': {
                '5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d': 'ws://localhost:6969'
            }
        }

        data = await self.storage.get_identified_pubkey('', domain='foo.com')
        assert data == {'names': {}, 'relays': {}}

        with self.assertRaises(StorageError):
            await self.storage.set_identified_pubkey('test@localhost', 'asd')

        await self.storage.set_identified_pubkey('test@localhost', '')
        data = await self.storage.get_identified_pubkey('test@localhost')
        assert data['names'] == {}

    async def test_nip33(self):
        """
        Test that parameterized replaceable events work
        """
        replace_event = self.make_event(PK1, kind=31000, tags=[["d", "replace1"]], content="first")
        await self.storage.add_event(replace_event)
        # similar event won't replace
        await self.storage.add_event(self.make_event(PK1, kind=31000, tags=[["d", "replace2"]]))
        assert await self.storage.get_event(replace_event['id'])

        # event with same tag will replace
        replaced = self.make_event(PK1, kind=31000, tags=[["d", "replace1"]])
        await self.storage.add_event(replaced)
        assert not await self.storage.get_event(replace_event['id'])
        assert await self.storage.get_event(replaced['id'])

        # empty d-tag
        empty_dtag = self.make_event(PK1, kind=31000, tags=[["d"]], content="empty")
        await self.storage.add_event(empty_dtag)
        assert await self.storage.get_event(replaced['id'])

        empty_2 = self.make_event(PK1, kind=31000, tags=[], content="empty 2")
        await self.storage.add_event(empty_2)
        assert not await self.storage.get_event(empty_dtag['id'])

        # no tag
        no_tag = self.make_event(PK1, kind=32000, tags=[], content="empty")
        await self.storage.add_event(no_tag)
        d_tag = self.make_event(PK1, kind=32000, tags=[['d']], content="dtag")
        await self.storage.add_event(d_tag)

        assert not await self.storage.get_event(no_tag['id'])
        replaced = self.make_event(PK1, kind=32000, tags=[["d", "replace again"]])
        await self.storage.add_event(replaced)
        assert await self.storage.get_event(d_tag['id'])


class APITests(BaseTestsWithStorage):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.conductor = testing.ASGIConductor(create_app(storage=self.storage))

    async def send_event(self, ws, event, get_response=False):
        await ws.send_json(["EVENT", event])
        if get_response:
            return await ws.receive_json()

    async def get_event(self, ws, event_id, check=True, exists=True, req_name="checkid"):
        await ws.send_json(["REQ", req_name, {"ids": [event_id]}])
        data = await ws.receive_json()
        if check:
            if exists:
                assert data[0] == 'EVENT'
                assert data[1] == req_name
                assert data[2]["id"] == event_id
            else:
                assert data == ["EOSE", req_name]
        if exists:
            end = await ws.receive_json()
            assert end == ["EOSE", req_name]
        return data


class MainTests(APITests):
    async def test_get_event(self):
        async with self.conductor.simulate_ws('/') as ws:
            await self.send_event(ws, EVENTS[0], True)
        result = await self.conductor.simulate_get(f'/e/{EVENTS[0]["id"]}')
        data = result.json
        assert data == EVENTS[0]

    async def test_get_meta(self):
        doc = {
            'contact': 5678,
            'description': 'test relay description',
            'name': 'test relay',
            'pubkey': 1234,
            'software': 'https://code.pobblelabs.org/fossil/nostr_relay',
            'supported_nips': [
                1,
                2,
                5,
                9,
                11,
                12,
                15,
                20,
                26,
                33,
                40,
                # 42,
            ],
            'version': __version__,
        }
        result = await self.conductor.simulate_get('/', headers={'Accept': 'application/nostr+json'})

        assert result.json == doc

    async def test_get_index(self):
        result = await self.conductor.simulate_get('/')
        assert result.text == 'try using a nostr client :-)'
        Config.redirect_homepage = 'https://nostr.net/'
        result = await self.conductor.simulate_get('/')
        assert result.headers['location'] == 'https://nostr.net/'

    async def test_bad_protocol(self):
        async with self.conductor.simulate_ws('/') as ws:
            await ws.send_json({"bad": 1})
            await ws.send_json([{"bad": 1}])
            await ws.send_json(["BAD", {"bad": 1}])

    async def test_send_bad_events(self):
        async with self.conductor.simulate_ws('/') as ws:
            # send a too-large event
            large_event = EVENTS[1].copy()
            large_event['content'] = 'x' * 8192
            await self.send_event(ws, large_event)
            data = await ws.receive_json()
            assert data[2] == False
            assert data[3] == 'invalid: 280 characters should be enough for anybody'
            # send an event with wrong signature
            bad_sig = EVENTS[1].copy()
            bad_sig['content'] = 'bad'
            await self.send_event(ws, bad_sig)
            data = await ws.receive_json()
            assert data[2] == False
            assert data[3] == 'invalid: Bad signature'
            # send a non-json event
            await self.send_event(ws, 'bad event')
            data = await ws.receive_json()
            assert data[2] == False
            assert data[3] == 'invalid: Bad JSON'

    async def test_send_event(self):
        async with self.conductor.simulate_ws('/') as ws:
            data = await self.send_event(ws, EVENTS[0], True)
            assert data == ['OK', '0d7721e1ee4a343f623cfb86374cc2d4688784bd264b5bc26079843169f28d88', True, '']
            data = await self.send_event(ws, EVENTS[0], True)
            assert data == ['OK', '0d7721e1ee4a343f623cfb86374cc2d4688784bd264b5bc26079843169f28d88', False, 'duplicate: exists']

    async def test_req(self):
        async with self.conductor.simulate_ws('/') as ws:
            for event in EVENTS:
                await self.send_event(ws, event, True)
            await ws.send_json(["REQ", "test", {"ids": [EVENTS[1]["id"]]}, {"#p": EVENTS[1]['pubkey']}])
            data = await ws.receive_json()
            assert data == ['EVENT', 'test', EVENTS[1]]
            data = await ws.receive_json()
            assert data == ['EOSE', 'test']
            await ws.send_json(["CLOSE", "test"])

            await ws.send_json(["REQ", "test2", {"kinds": [0]}])
            data = await ws.receive_json()
            assert data[2]['id'] == '0d7721e1ee4a343f623cfb86374cc2d4688784bd264b5bc26079843169f28d88'
            data = await ws.receive_json()
            assert data == ['EOSE', 'test2']

            # test replacing a subscription
            await ws.send_json(["REQ", "test2", {"kinds": [1]}])
            data = await ws.receive_json()
            assert data[2]['kind'] == 1

    async def test_req_after_add(self):
        """
        test subscribing then receiving new additions
        """
        async with self.conductor.simulate_ws('/') as ws:
            await self.send_event(ws, EVENTS[1], True)
            await ws.send_json(["REQ", "test", {
                    "kinds": [1], 
                    "authors": ["5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d"],
                    "since": 1671325827,
                    "until": 1672528000
                },
                {
                    "#e": [EVENTS[1]["id"]],
                    "authors": [EVENTS[2]['pubkey']], 
                    "ids": [EVENTS[2]["id"]],
                    "limit": "10"
                },
            ])

            data = await ws.receive_json()
            assert data == ['EVENT', 'test', EVENTS[1]]
            
            data = await ws.receive_json()
            assert data == ['EOSE', 'test']

            await ws.send_json(["REQ", "missing", {"kinds": [1000]}])
            data = await ws.receive_json()
            assert data == ['EOSE', 'missing']

            # now add a new event
            data = await self.send_event(ws, EVENTS[2], True)
            if data[0] == 'OK':
                await asyncio.sleep(1)
                data = await ws.receive_json()
            assert data == ['EVENT', 'test', EVENTS[2]]
    
    async def test_prefix_search(self):
        async with self.conductor.simulate_ws('/') as ws:
            await self.send_event(ws, EVENTS[1], True)
            eid = EVENTS[1]['id']
            await ws.send_json(["REQ", "prefix", {"ids": [eid[:4]]}])
            data = await ws.receive_json()
            assert data == ['EVENT', 'prefix', EVENTS[1]]

    async def test_bad_req(self):
        async with self.conductor.simulate_ws('/') as ws:
            # unsubscribe from nonexistent req
            await ws.send_json(["REQ", "unknown", {}])
            data = await ws.receive_json()
            assert data == ['EOSE', 'unknown']
            await ws.send_json(["REQ", "toobroad", {"ids": []}, {"authors": [], "kinds": []}])
            data = await ws.receive_json()
            assert data == ['EOSE', 'toobroad']

            await ws.send_json(["REQ", "junk", 
                {"ids": [None]}, 
                {"authors": [None, 1], "kinds": [None]}, 
                {"kinds": ['a']}, 
                {'since': None, "authors": ["x"]},
                {'until': 'a'},
                {'until': None},
                {'authors': []},
            ])
            data = await ws.receive_json()
            assert data == ['EOSE', 'junk']

    async def test_tag_search(self):
        async with self.conductor.simulate_ws("/") as ws:
            tag_event = {"id": "0b5d4c896b9f8b74feb0a63f8c50536b094ae948049d4c3ab967afc98250cee3", "pubkey": "5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d", "created_at": 1672325827, "kind": 1, "tags": [["t", "test"], ["t", "foo"], ["h", "home"]], "content": "got tags", "sig": "fbbd5fcf0e385d39d6120735f49c52ccc9f278670d7ce0c4ff774ff454fd810c4d18c005db681bbb5754d19351b922570f18d3fa8fae697c0480ebfccbed06e7"}
            await self.send_event(ws, tag_event, True)
            await ws.send_json(["REQ", "tag", {"#t": ["test", "foo", "baz"]}])
            data = await ws.receive_json()
            assert data == ["EVENT", "tag", tag_event]
            data = await ws.receive_json()
            assert data == ["EOSE", "tag"]

            await ws.send_json(["REQ", "tag", {"#h": [";'); drop table event"]}, {"#t": ["'''''hello"]}])
            data = await ws.receive_json()
            assert data == ["EOSE", "tag"]


    async def test_origin_blacklist(self):
        with self.assertRaises(errors.WebSocketDisconnected):
            async with self.conductor.simulate_ws('/', headers={'origin': 'http://bad.actor'}):
                pass

    async def test_rate_limit(self):
        """
        Test config rate limits "CLOSE" events
        """
        async with self.conductor.simulate_ws("/", remote_addr='1.1.1.1') as ws:
            for i in range(11):
                await ws.send_json(["CLOSE", "rate-limit"])
            data = await ws.receive_json()
            assert data == ["NOTICE", "rate-limited"]
            for i in range(10):
                data = await self.send_event(ws, EVENTS[1], True)
                assert data[3] != 'rate-limited: slow down'
            data = await self.send_event(ws, EVENTS[1], True)
            assert data[3] == 'rate-limited: slow down'

    async def test_timeout(self):
        """
        Test time out waiting for next message
        """
        Config.message_timeout = 1.5
        async with self.conductor.simulate_ws("/") as ws:
            await self.send_event(ws, EVENTS[1], True)
            await asyncio.sleep(1.6)
            with self.assertRaises(errors.WebSocketDisconnected):
                data = await ws.send_json(["REQ", "test", {"kinds": 0}])

        Config.message_timeout = None

    async def test_too_many_subscriptions(self):
        """
        Test subscription limit
        """
        Config.subscription_limit = 2
        async with self.conductor.simulate_ws("/") as ws:
            await ws.send_json(["REQ", "t1", {"kinds": [1,2]}])
            data = await ws.receive_json()
            assert data == ['EOSE', 't1']
            await ws.send_json(["REQ", "t2", {"kinds": [3,4]}])
            data = await ws.receive_json()
            assert data == ['EOSE', 't2']
            await ws.send_json(["REQ", "t3", {"kinds": [5,6]}])
            data = await ws.receive_json()
            assert data == ['NOTICE', 'rejected: too many subscriptions']
        Config.subscription_limit = None


class AuthTests(APITests):
    async def asyncSetUp(self):
        Config.authentication = {"enabled": True, "actions": {"save": "w", "query": "r"}}
        await super().asyncSetUp()
        self.readonly = ('f6d7c79924aa815d0d408bc28c1a23af208209476c1b7691df96f7d7b72a2753', '5faaae4973c6ed517e7ed6c3921b9842ddbc2fc5a5bc08793d2e736996f6394d', 'r')
        self.writeonly = ('e93505f081570221255f05341f4fbaeaf682d59d2e2472d7dd02d566f6372178', '647bf6e686fde33dfbfd4f3d987bc13b1c202f952b70dc3539d8d85172b40561', 'w')
        self.readwrite = ('9679a595bdb5fe4330a263c96201eac204dfe24b2e2dc36ac12698faf9275130', '1bd80e4430c40a6fa9f59582124b5a6fbc1815e26455801e6b1edf113554de03', 'rw')
        self.unknown = ('94cdca784fd5a951cc1a4672e86847f957f29b35b7ac9476bc891d68e5b68b34', 'a0f1e845b43508847d10cb7ac7928cd9dafc9b82d0b3c4c08b264e177b4355de', 's')

        for _, pubkey, role in (self.readonly, self.writeonly, self.readwrite, self.unknown):
            await self.storage.authenticator.set_roles(pubkey, role)

    async def asyncTearDown(self):
        from nostr_relay.auth import AuthTable
        async with self.storage.db.begin() as conn:
            await conn.execute(AuthTable.delete())
        await super().asyncTearDown()

    async def get_challenge(self, ws):
        data = await ws.receive_json()
        assert data[0] == 'AUTH'
        return data[1]

    def make_auth_event(self, privkey, pubkey, created_at=None, challenge='', relay='ws://localhost:6969', **kwargs):
        tags = [
            ['relay', relay],
            ['challenge', challenge]
        ]
        return self.make_event(privkey, pubkey=pubkey, kind=22242, created_at=created_at, tags=tags, **kwargs)

    async def test_auth_message(self):
        """
        Test AUTH message type
        """
        async with self.conductor.simulate_ws("/") as ws:
            # server sends AUTH message challenge
            challenge = await self.get_challenge(ws)

            # send one with a bad signature
            await ws.send_json(["AUTH", self.make_auth_event(self.unknown[0], self.readonly[1], challenge=challenge)])
            data = await ws.receive_json()
            assert data == ['NOTICE', 'invalid: Bad signature']

            await ws.send_json(["AUTH", self.make_auth_event(self.readonly[0], self.readonly[1], challenge=challenge, created_at=time.time() - 3600)])
            data = await ws.receive_json()
            assert data == ['NOTICE', 'invalid: Too old']

            # correct auth sends no response
            await ws.send_json(["AUTH", self.make_auth_event(self.readonly[0], self.readonly[1], challenge=challenge)])

    async def test_role_permissions(self):
        """
        Test read/write roles
        """
        # test write permission
        async with self.conductor.simulate_ws("/") as ws:
            challenge = await self.get_challenge(ws)

            response = await self.send_event(ws, EVENTS[1], True)
            assert response[2] == False
            assert response[3] == 'restricted: permission denied'

            await ws.send_json(["AUTH", self.make_auth_event(self.writeonly[0], self.writeonly[1], challenge=challenge)])

            response = await self.send_event(ws, EVENTS[1], True)
            assert response[2] == True
            assert response[3] == ''

            # role is write only, so read will fail
            await ws.send_json(["REQ", "read", {"ids": [EVENTS[1]["id"]]}])
            data = await ws.receive_json()
            assert data == ['NOTICE', 'restricted: permission denied']

        # test read permission
        async with self.conductor.simulate_ws("/") as ws:
            challenge = await self.get_challenge(ws)

            response = await self.send_event(ws, EVENTS[2], True)
            assert response[2] == False
            assert response[3] == 'restricted: permission denied'

            await ws.send_json(["REQ", "read", {"ids": [EVENTS[1]["id"]]}])
            data = await ws.receive_json()
            assert data == ['NOTICE', 'restricted: permission denied']

            # authenticate as read only role
            await ws.send_json(["AUTH", self.make_auth_event(self.readonly[0], self.readonly[1], challenge=challenge)])
            response = await self.send_event(ws, EVENTS[2], True)
            assert response[2] == False
            assert response[3] == 'restricted: permission denied'

            await ws.send_json(["REQ", "read", {"ids": [EVENTS[1]["id"]]}])
            data = await ws.receive_json()
            assert data[0] == 'EVENT'
            assert data[1] == 'read'
            assert data[2]['id'] == EVENTS[1]['id']

        # test unknown role
        async with self.conductor.simulate_ws("/") as ws:
            challenge = await self.get_challenge(ws)
            await ws.send_json(["AUTH", self.make_auth_event(self.unknown[0], self.unknown[1], challenge=challenge)])

            # authenticated, but can't do anything
            response = await self.send_event(ws, EVENTS[2], True)
            assert response[2] == False
            assert response[3] == 'restricted: permission denied'

            await ws.send_json(["REQ", "read", {"ids": [EVENTS[1]["id"]]}])
            data = await ws.receive_json()
            assert data == ['NOTICE', 'restricted: permission denied']


if __name__ == "__main__":
    unittest.main()


