import base64
import json
import socket
from types import SimpleNamespace

import http_ece
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from lnbits.core.services.notifications import send_push_notification

pytestmark = pytest.mark.anyio


@pytest.fixture
def push_subscription(settings):
    receiver = ec.generate_private_key(ec.SECP256R1())
    signing_key = ec.generate_private_key(ec.SECP256R1())
    settings.lnbits_webpush_privkey = signing_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    auth = b"0123456789abcdef"
    public = receiver.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    endpoint = "https://push.example:8443/subscription"
    info = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": base64.urlsafe_b64encode(public).rstrip(b"=").decode(),
            "auth": base64.urlsafe_b64encode(auth).rstrip(b"=").decode(),
        },
    }
    subscription = SimpleNamespace(data=json.dumps(info), endpoint=endpoint)
    return subscription, receiver, auth, signing_key


async def test_push_preserves_encryption_signature_and_pins_destination(
    push_subscription, safe_http_mock, settings, mocker
):
    subscription, receiver, auth, signing_key = push_subscription
    settings.lnbits_callback_url_rules = [r"https://webhooks\.example"]
    unguarded_send = mocker.patch("pywebpush.requests.post")
    resolver, handler = safe_http_mock
    handler.side_effect = lambda request: httpx.Response(201)
    await send_push_notification(subscription, "Title", "Received 100 sats", "/wallet")

    resolver.assert_awaited_once()
    handler.assert_called_once()
    unguarded_send.assert_not_called()
    request = handler.call_args.args[0]
    assert str(request.url) == "https://93.184.216.34:8443/subscription"
    assert request.headers["host"] == "push.example:8443"
    assert request.extensions["sni_hostname"] == "push.example"
    assert request.headers["content-encoding"] == "aes128gcm"
    assert request.headers["ttl"] == "0"
    plaintext = http_ece.decrypt(
        request.content, private_key=receiver, auth_secret=auth, version="aes128gcm"
    )
    assert json.loads(plaintext) == {
        "title": "Title",
        "body": "Received 100 sats",
        "url": "/wallet",
    }
    token = request.headers["authorization"].split("t=", 1)[1].split(",", 1)[0]
    claims = jwt.decode(
        token,
        signing_key.public_key(),
        algorithms=["ES256"],
        audience="https://push.example:8443",
    )
    assert claims["sub"] == "mailto:alan@lnbits.com"


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "8.8.8.8"]
)
async def test_push_blocks_private_and_self_destinations(
    push_subscription, safe_http_mock, settings, address
):
    settings.lnbits_callback_allow_private_ips = True
    settings.lnbits_outbound_host_ips = ["8.8.8.8"]
    resolver, handler = safe_http_mock
    resolver.return_value = [
        (
            socket.AF_INET6 if ":" in address else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (address, 8443),
        )
    ]
    await send_push_notification(push_subscription[0], "Title", "Body")
    handler.assert_not_called()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1/push",
        "file:///tmp/secret",
        "https://user:password@push.example/push",
    ],
)
async def test_push_rejects_unsafe_endpoint(
    push_subscription, safe_http_mock, endpoint
):
    subscription = push_subscription[0]
    info = json.loads(subscription.data)
    info["endpoint"] = endpoint
    subscription.data = json.dumps(info)
    await send_push_notification(subscription, "Title", "Body")
    safe_http_mock[1].assert_not_called()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
async def test_push_never_follows_redirects(push_subscription, safe_http_mock, status):
    resolver, handler = safe_http_mock
    handler.side_effect = lambda request: httpx.Response(
        status, headers={"location": "http://127.0.0.1/internal"}
    )
    await send_push_notification(push_subscription[0], "Title", "Body")
    handler.assert_called_once()
    resolver.assert_awaited_once()


@pytest.mark.parametrize("status", [201, 400, 403, 404, 410, 500])
async def test_push_only_deletes_gone_subscription(
    push_subscription, safe_http_mock, mocker, status
):
    delete = mocker.patch(
        "lnbits.core.services.notifications.delete_webpush_subscriptions",
        new_callable=mocker.AsyncMock,
    )
    safe_http_mock[1].side_effect = lambda request: httpx.Response(status)
    subscription = push_subscription[0]
    await send_push_notification(subscription, "Title", "Body")
    if status == 410:
        delete.assert_awaited_once_with(subscription.endpoint)
    else:
        delete.assert_not_awaited()


async def test_push_transport_failure_does_not_escape_or_log_response(
    push_subscription, safe_http_mock, mocker
):
    safe_http_mock[1].side_effect = httpx.ConnectError("sensitive endpoint")
    warning = mocker.patch("lnbits.core.services.notifications.logger.warning")
    await send_push_notification(push_subscription[0], "Title", "Body")
    warning.assert_called_once_with("Push notification failed: ConnectError")


@pytest.mark.parametrize("key", [None, "", "invalid-key"])
async def test_push_invalid_signing_key_is_contained(
    push_subscription, safe_http_mock, settings, key
):
    settings.lnbits_webpush_privkey = key
    await send_push_notification(push_subscription[0], "Title", "Body")
    safe_http_mock[1].assert_not_called()
