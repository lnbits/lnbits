import asyncio
import errno
import ipaddress
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
from lnurl import LnurlResponseException
from pydantic import ValidationError

from lnbits.core.db import core_app_extra
from lnbits.core.models import User
from lnbits.core.services import lnurl
from lnbits.settings import Settings, settings
from lnbits.utils import outbound, safe_http


@pytest.fixture(autouse=True)
def policy(monkeypatch):
    monkeypatch.setattr(core_app_extra, "local_lnurl_app", None)
    monkeypatch.setattr(settings, "lnbits_baseurl", "https://instance.example/")
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", [])
    monkeypatch.setattr(settings, "lnbits_callback_url_rules", [])
    monkeypatch.setattr(settings, "lnbits_lnurl_redirect_url_rules", [])
    monkeypatch.setattr(outbound, "_is_assigned", lambda ip: False)


def dns(monkeypatch, addresses):
    resolver = AsyncMock(
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolver)
    return resolver


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["instance.example", "INSTANCE.EXAMPLE."])
async def test_hostname_blocked_before_dns_at_any_port(monkeypatch, target):
    resolver = dns(monkeypatch, ["8.8.8.8"])
    with pytest.raises(ValueError, match="this server"):
        await safe_http.validate_url(f"https://{target}:8443/secrets")
    resolver.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["assigned", "supplied"])
@pytest.mark.parametrize("target", ["8.8.8.8", "2001:4860:4860::8888"])
async def test_public_self_ip_and_dns_alias_never_connect(monkeypatch, kind, target):
    if kind == "assigned":
        monkeypatch.setattr(outbound, "_is_assigned", lambda ip: str(ip) == target)
    else:
        monkeypatch.setattr(settings, "lnbits_outbound_host_ips", [target])
    dns(monkeypatch, [target])
    async with safe_http.SafeHttpClient() as client:
        send = AsyncMock()
        monkeypatch.setattr(client.client, "send", send)
        for url in [
            httpx.URL("https://alias.example"),
            httpx.URL("https://x").copy_with(host=target),
        ]:
            with pytest.raises(ValueError, match="this server"):
                await client.get(url)
        send.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "target", ["::ffff:8.8.8.8", "64:ff9b::808:808", "2002:0808:0808::"]
)
async def test_embedded_self_ip_is_blocked(monkeypatch, target):
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", ["8.8.8.8"])
    with pytest.raises(ValueError, match="this server"):
        await outbound.check_outbound_addresses([ipaddress.ip_address(target)])


@pytest.mark.anyio
async def test_mixed_answers_and_interface_changes_are_rechecked(monkeypatch):
    dns(monkeypatch, ["8.8.8.8", "1.1.1.1"])
    assert len(await safe_http.validate_url("https://public.example")) == 2
    monkeypatch.setattr(outbound, "_is_assigned", lambda ip: str(ip) == "1.1.1.1")
    with pytest.raises(ValueError, match="this server"):
        await safe_http.validate_url("https://public.example")


@pytest.mark.anyio
async def test_redirect_to_self_never_connects(monkeypatch):
    dns(monkeypatch, ["8.8.8.8"])
    async with safe_http.SafeHttpClient(follow_redirects=True) as client:
        send = AsyncMock(
            return_value=httpx.Response(
                302, headers={"location": "https://instance.example:8443/secret"}
            )
        )
        monkeypatch.setattr(client, "_send", send)
        with pytest.raises(ValueError, match="this server"):
            await client.get("https://public.example")
        send.assert_awaited_once()


@pytest.mark.anyio
async def test_lnurl_public_self_ip_cannot_use_private_opt_in(monkeypatch):
    monkeypatch.setattr(settings, "lnbits_lnurl_allow_private_ips", True)
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", ["8.8.8.8"])
    with pytest.raises(LnurlResponseException, match="this server"):
        await lnurl._validate_lnurl_request_url(
            httpx.URL("https://8.8.8.8:8443/"), tor_socks=None
        )


@pytest.mark.anyio
async def test_local_payment_metadata_and_callback_use_no_network(monkeypatch):
    app = FastAPI()
    calls = []

    @app.get("/.well-known/lnurlp/alice", openapi_extra={"x-lnbits-local-lnurl": True})
    async def metadata(request: Request):
        calls.append(request)
        return {"callback": "https://instance.example/api/v1/lnurl/wallet/alice/cb"}

    @app.get(
        "/api/v1/lnurl/wallet/alice/cb", openapi_extra={"x-lnbits-local-lnurl": True}
    )
    async def callback(request: Request, amount: int):
        calls.append(request)
        return {"pr": "test-invoice", "amount": amount}

    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    send = AsyncMock(side_effect=AssertionError("Must not connect to the host"))
    monkeypatch.setattr(lnurl, "_send_lnurl_request", send)
    resolver = dns(monkeypatch, [])
    data = await lnurl.request_lnurl_json(
        "https://instance.example/.well-known/lnurlp/alice"
    )
    result = await lnurl.request_lnurl_json(data["callback"], params={"amount": 123000})
    assert result == {"pr": "test-invoice", "amount": 123000}
    assert all(
        "authorization" not in r.headers and "cookie" not in r.headers for r in calls
    )
    send.assert_not_awaited()
    resolver.assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["response", "body"])
async def test_local_lnurl_timeout_cancels_stalled_request(monkeypatch, phase):
    app = FastAPI()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def stall():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    @app.get("/.well-known/lnurlp/alice", openapi_extra={"x-lnbits-local-lnurl": True})
    async def metadata():
        if phase == "response":
            await stall()
            return {}

        async def body():
            yield b"{"
            await stall()

        return StreamingResponse(body(), media_type="application/json")

    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    with pytest.raises(
        LnurlResponseException, match="Local LNURL request failed"
    ) as exc:
        await lnurl.request_lnurl_json(
            "https://instance.example/.well-known/lnurlp/alice", timeout=1
        )
    assert started.is_set()
    assert cancelled.is_set()
    assert isinstance(exc.value.__cause__, asyncio.TimeoutError)


def test_local_lnurl_requires_registered_opted_in_get_route(monkeypatch):
    app = FastAPI()
    router = APIRouter(prefix="/example_ext")

    @router.get("/pay/{link_id}", openapi_extra={"x-lnbits-local-lnurl": True})
    async def metadata(link_id: str):
        return {"id": link_id}

    @router.get("/admin")
    async def admin():
        return {}

    @router.post("/post", openapi_extra={"x-lnbits-local-lnurl": True})
    async def post_only():
        return {}

    app.include_router(router)
    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    url = httpx.URL("https://instance.example/example_ext/pay/abc")
    assert lnurl._is_local_lnurl_url(url)
    for path in ("/example_ext/admin", "/example_ext/post", "/other_ext/pay/abc"):
        assert not lnurl._is_local_lnurl_url(url.copy_with(path=path))
    # Removed or upgraded routes must not retain stale permission.
    app.router.routes = []
    assert not lnurl._is_local_lnurl_url(url)


def test_shadowed_or_mounted_route_cannot_borrow_lnurl_permission(monkeypatch):
    app = FastAPI()

    @app.get("/example_ext/pay/{link_id}")
    async def unmarked(link_id: str):
        return {}

    @app.get("/example_ext/pay/{link_id}", openapi_extra={"x-lnbits-local-lnurl": True})
    async def marked(link_id: str):
        return {}

    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    url = httpx.URL("https://instance.example/example_ext/pay/abc")
    assert not lnurl._is_local_lnurl_url(url)
    mounted = FastAPI()
    mounted.mount("/", app)
    monkeypatch.setattr(core_app_extra, "local_lnurl_app", mounted)
    assert not lnurl._is_local_lnurl_url(url)


def test_core_public_lnurl_routes_explicitly_opt_in(monkeypatch):
    from lnbits.core.views.lnurl_api import lnurl_router

    app = FastAPI()
    app.include_router(lnurl_router)
    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    for path in ("/.well-known/lnurlp/alice", "/api/v1/lnurl/wallet/alice/cb"):
        assert lnurl._is_local_lnurl_url(httpx.URL("https://instance.example" + path))
    assert not lnurl._is_local_lnurl_url(
        httpx.URL("https://instance.example/api/v1/lnurlscan/test")
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "https://instance.example/admin/api/v1/settings",
        "https://instance.example/example_ext/admin",
        "https://instance.example/example_ext/auth?wipe=true",
        "https://instance.example/unknown/api/v1/lnurl/cb/charge",
        "https://instance.example:8443/.well-known/lnurlp/alice",
        "http://instance.example/.well-known/lnurlp/alice",
        "https://user:secret@instance.example/.well-known/lnurlp/alice",
        "https://instance.example/.well-known/lnurlp/%61lice",
        "https://instance.example/lnurlp/abc/../../admin",
    ],
)
async def test_internal_dispatch_does_not_allow_arbitrary_self_requests(
    monkeypatch, url
):
    send = AsyncMock()
    monkeypatch.setattr(lnurl, "_send_lnurl_request", send)
    assert not lnurl._is_local_lnurl_url(httpx.URL(url))
    with pytest.raises(LnurlResponseException):
        await lnurl.request_lnurl_json(url)
    send.assert_not_awaited()


@pytest.mark.anyio
async def test_internal_redirect_is_checked_and_missing_app_fails_closed(monkeypatch):
    monkeypatch.setattr(core_app_extra, "local_lnurl_app", None)
    with pytest.raises(LnurlResponseException, match="this server"):
        await lnurl.request_lnurl_json("https://instance.example/example_ext/pay/abc")
    app = FastAPI()

    @app.get("/example_ext/pay/abc", openapi_extra={"x-lnbits-local-lnurl": True})
    async def redirect():
        from fastapi.responses import RedirectResponse

        return RedirectResponse("https://instance.example:8443/secret")

    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    monkeypatch.setattr(settings, "lnbits_lnurl_redirect_url_rules", [".*"])
    with pytest.raises(LnurlResponseException, match="this server"):
        await lnurl.request_lnurl_json("https://instance.example/example_ext/pay/abc")


def test_environment_addresses_are_validated_and_readonly():
    configured = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        lnbits_outbound_host_ips="8.8.8.8,2001:4860:4860::8888,8.8.8.8",
    )
    assert configured.lnbits_outbound_host_ips == ["8.8.8.8", "2001:4860:4860::8888"]
    assert "lnbits_outbound_host_ips" in Settings.readonly_fields()
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,  # pyright: ignore[reportCallIssue]
            lnbits_outbound_host_ips=["attacker.example"],
        )


def test_bind_detection_sends_no_packets_and_fails_closed(monkeypatch):
    # Restore the real function replaced by the fixture.
    assigned = REAL_IS_ASSIGNED
    sock = Mock()
    sock.__enter__ = Mock(return_value=sock)
    sock.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(outbound.socket, "socket", Mock(return_value=sock))
    assert assigned(ipaddress.ip_address("8.8.8.8"))
    sock.bind.assert_called_once_with(("8.8.8.8", 0))
    sock.send.assert_not_called()
    sock.connect.assert_not_called()
    sock.bind.side_effect = OSError(errno.EADDRNOTAVAIL, "not assigned")
    assert not assigned(ipaddress.ip_address("8.8.8.8"))
    sock.bind.side_effect = OSError(errno.EMFILE, "resource exhaustion")
    with pytest.raises(ValueError, match="Cannot validate"):
        assigned(ipaddress.ip_address("8.8.8.8"))


def test_real_loopback_bind_detection():
    assert REAL_IS_ASSIGNED(ipaddress.ip_address("127.0.0.1"))


def test_docker_launcher_supplies_host_and_extra_addresses(tmp_path):
    bash = which("bash")
    sh = which("sh")
    assert bash and sh
    hostname = tmp_path / "hostname"
    hostname.write_text(f"#!{sh}\nprintf '8.8.8.8 2001:4860:4860::8888 \\n'\n")
    hostname.chmod(0o700)
    docker = tmp_path / "docker"
    docker.write_text(f"#!{sh}\nprintf '%s\\n' \"$@\"\n")
    docker.chmod(0o700)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "LNBITS_OUTBOUND_HOST_IPS": "1.1.1.1",
    }
    result = subprocess.run(  # noqa: S603 - fixed local script, stubbed docker
        [
            bash,
            str(Path("tools/docker-run.sh").resolve()),
            "--name",
            "test instance",
            "lnbits/test",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [
        "run",
        "--env",
        "LNBITS_OUTBOUND_HOST_IPS=8.8.8.8,2001:4860:4860::8888,1.1.1.1",
        "--name",
        "test instance",
        "lnbits/test",
    ]
    hostname.write_text(f"#!{sh}\nexit 1\n")
    result = subprocess.run(  # noqa: S603 - fixed local script, stubbed docker
        [bash, str(Path("tools/docker-run.sh").resolve()), "lnbits/test"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert not result.stdout


REAL_IS_ASSIGNED = outbound._is_assigned


@pytest.mark.anyio
async def test_deployment_mapped_ipv4_address_also_blocks_plain_ipv4(monkeypatch):
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", ["::ffff:8.8.8.8"])
    with pytest.raises(ValueError, match="this server"):
        await outbound.check_outbound_addresses([ipaddress.ip_address("8.8.8.8")])


@pytest.mark.anyio
@pytest.mark.parametrize("super_user", [False, True])
async def test_security_status_only_rendered_for_superuser(monkeypatch, super_user):
    from lnbits.core.views import generic

    renderer = Mock()
    monkeypatch.setattr(generic, "template_renderer", lambda: renderer)
    now = datetime.now(timezone.utc)
    user = User(id="a" * 32, created_at=now, updated_at=now, super_user=super_user)
    await generic.index(Request({"type": "http"}), user=user)
    context = renderer.TemplateResponse.call_args.args[2]
    assert bool(context["outbound_protection"]) is super_user


def test_container_gap_is_reported_until_host_addresses_supplied(monkeypatch):
    monkeypatch.setattr(outbound.Path, "exists", lambda _: True)
    assert outbound.outbound_protection_status()["container_without_host_ips"]
    monkeypatch.setattr(settings, "lnbits_outbound_host_ips", ["8.8.8.8"])
    assert not outbound.outbound_protection_status()["container_without_host_ips"]


@pytest.mark.parametrize("target", ["bücher.example", "xn--bcher-kva.example"])
def test_hostname_guard_normalizes_international_names(monkeypatch, target):
    monkeypatch.setattr(settings, "lnbits_baseurl", "https://bücher.example/")
    with pytest.raises(ValueError, match="this server"):
        outbound.check_outbound_hostname(target)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "metadata_path,callback_path",
    [
        ("/example_ext/pay/item", "/example_ext/pay/cb/item"),
        ("/example_ext/v2/withdraw/device", "/example_ext/v2/withdraw/cb/cGF5bG9hZA=="),
        ("/example_ext/custom/route/21", "/example_ext/callback"),
    ],
)
async def test_same_instance_extension_lnurl_flow_stays_inside_app(
    monkeypatch, metadata_path, callback_path
):
    app = FastAPI()
    seen = []

    @app.get(metadata_path, openapi_extra={"x-lnbits-local-lnurl": True})
    async def metadata():
        return {"callback": "https://instance.example" + callback_path}

    @app.get(callback_path, openapi_extra={"x-lnbits-local-lnurl": True})
    async def callback(request: Request, k1: str, pr: str):
        seen.append(request)
        return {"status": "OK", "k1": k1, "pr": pr}

    monkeypatch.setattr(core_app_extra, "local_lnurl_app", app)
    send = AsyncMock(side_effect=AssertionError("Must not connect to the host"))
    monkeypatch.setattr(lnurl, "_send_lnurl_request", send)
    resolver = dns(monkeypatch, [])
    data = await lnurl.request_lnurl_json("https://instance.example" + metadata_path)
    response = await lnurl.request_lnurl_json(
        data["callback"], params={"k1": "charge", "pr": "test-invoice"}
    )
    assert response == {"status": "OK", "k1": "charge", "pr": "test-invoice"}
    assert len(seen) == 1
    assert "authorization" not in seen[0].headers
    assert "cookie" not in seen[0].headers
    resolver.assert_not_awaited()
    send.assert_not_awaited()
