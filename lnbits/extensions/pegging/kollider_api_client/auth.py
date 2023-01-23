import base64
import hashlib
import hmac
import json
import time


def generate_signature(secret, path=None, method=None, body=None):

    timestamp = int(time.time())
    secret = base64.b64decode(secret)
    what = str(timestamp)

    if method:
        what += method
    if path:
        what += path
    if body:
        what += json.dumps(body, sort_keys=True).replace(" ", "")
    print(what)

    signature = hmac.new(secret, what.encode(), digestmod=hashlib.sha256).digest()

    return (timestamp, base64.b64encode(signature).decode("utf-8"))


def auth_header(secret, method, path, body):
    (timestamp, sig) = generate_signature(secret, path, method, body)
    header = {
        "k-signature": sig,
        "k-timestamp": str(timestamp),
    }
    return header
