import enum
import logging
import secrets
from time import time
from datetime import datetime

import sqlalchemy as sa

from .event import Event
from .errors import StorageError, AuthenticationError
from .util import call_from_path
from .storage import get_metadata


AuthTable = sa.Table(
    'auth',
    get_metadata(),
    sa.Column('pubkey', sa.Text(), primary_key=True),
    sa.Column('roles', sa.Text()),
    sa.Column('created', sa.DateTime())
)


class Role(enum.Enum):
    anonymous = 'a'
    reader = 'r'
    writer = 'w'
    admin = 's'


class Action(enum.Enum):
    query = 'query'
    save = 'save'
    read_dm = 'read_dm'



class Authenticator:
    """
    Authenticate, according to NIP-42
    """
    def __init__(self, storage, options):
        self.default_roles = set(Role.anonymous.value)
        self.storage = storage
        self.actions, self.valid_urls, self.is_enabled = self.parse_options(options)
        self.log = logging.getLogger('nostr_relay.auth')
        if self.is_enabled:
            self.log.info("Authentication enabled.")

    def parse_options(self, options):
        actions = {Action.save.value: self.default_roles, Action.query.value: self.default_roles}
        valid_urls = options.get('relay_urls', 'ws://localhost:6969')
        for action, roles in options.get('actions', {}).items():
            if isinstance(action, Action):
                action = action.value
            if isinstance(roles, Role):
                roles = roles.value
            actions[action] = set(roles)
        enabled = options.get('enabled', False)
        return actions, valid_urls, enabled

    def get_challenge(self, remote_addr):
        """
        Return a suitably random challenge
        caller is responsible for remembering the challenge and passing it on to authenticate()
        """
        return secrets.token_hex(16)

    def check_auth_event(self, auth_event, challenge):
        """
        Validate the authentication event
        """
        if not auth_event.verify():
            raise AuthenticationError("invalid: Bad signature")
        if auth_event.kind != 22242:
            raise AuthenticationError("invalid: Wrong kind. Must be 22242.")
        since = time() - auth_event.created_at
        if since >= 600:
            raise AuthenticationError("invalid: Too old")
        elif since <= -600:
            raise AuthenticationError("invalid: Too new")
        found_relay = found_challenge = False
        for tag in auth_event.tags:
            if tag[0] == 'relay':
                if tag[1] not in self.valid_urls:
                    raise AuthenticationError("invalid: Wrong domain")
                found_relay = True
            elif tag[0] == 'challenge':
                if tag[1] != challenge:
                    raise AuthenticationError("invalid: Wrong challenge")
                found_challenge = True
        if not (found_relay and found_challenge):
            raise AuthenticationError("invalid: Missing required tags")

    async def evaluate_target(self, auth_token, action, target):
        if action == Action.read_dm.value:
            if auth_token.get('pubkey') != target.pubkey:
                return False
        elif action == Action.save.value:
            if auth_token.get('pubkey') == target.pubkey:
                return True
        # TODO: implement per-object permissions here
        return True

    async def get_roles(self, pubkey):
        """
        Get the roles assigned to the public key
        """
        async with self.storage.db.begin() as conn:
            result = await conn.execute(sa.select(AuthTable.c.roles).where(AuthTable.c.pubkey == pubkey))
            row = result.fetchone()
        if row:
            return set(row[0].lower())
        else:
            return self.default_roles

    async def get_all_roles(self):
        """
        Return all roles in authentication table
        """
        async with self.storage.db.begin() as conn:
            result = await conn.stream(sa.select(AuthTable.c.pubkey, AuthTable.c.roles))
            async for pubkey, role in result:
                yield pubkey, set((role or '').lower())

    async def set_roles(self, pubkey: str, roles: str):
        """
        Assign roles to the given public key
        """
        async with self.storage.db.begin() as conn:
            await conn.execute(sa.insert(AuthTable).values(pubkey=pubkey, roles=roles, created=datetime.now()))

    async def authenticate(self, auth_event_json: dict, challenge: str=''):
        """
        Authenticate, using the authentication event described in NIP-42

        This will always return a token which can be used with can_do(auth_token, action)
        """
        auth_event = Event(**auth_event_json)
        self.check_auth_event(auth_event, challenge)

        token = {
            'pubkey': auth_event.pubkey,
            'roles': await self.get_roles(auth_event.pubkey),
            'now': time(),
        }
        self.log.info("Authenticated %s. roles:%s", auth_event.pubkey, token['roles'])
        return token

    async def can_do(self, auth_token: dict, action: str, target=None):
        """
        Return boolean whether the auth_token can perform the action (on the optional target)
        auth_token is an opaque value returned from authenticate()

        target can be any object and will be evaluated by evaluate_target(auth_token, action, target)
        """
        can_do = True
        if self.is_enabled:
            if action in self.actions:
                can_do = bool(self.actions[action].intersection(auth_token.get('roles', self.default_roles)))
                if can_do and target:
                    can_do = await self.evaluate_target(auth_token, action, target)
        return can_do


def get_authenticator(storage, configuration: dict):
    """
    Return an authenticator object, according to the configuration dict
    """

    classpath = configuration.get('authenticator_class', 'nostr_relay.auth.Authenticator')
    return call_from_path(classpath, storage, configuration)

