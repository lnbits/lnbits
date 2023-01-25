"""
Exceptions used for nostr-relay
"""


class StorageError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class VerificationError(Exception):
    pass
