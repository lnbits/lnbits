import hashlib


def encrypt(string: str):
    return hashlib.sha256(string.encode()).hexdigest()
