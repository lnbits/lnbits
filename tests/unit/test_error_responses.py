from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.gzip import GZipMiddleware

from lnbits.app import register_new_ratelimiter
from lnbits.exceptions import register_exception_handlers
from lnbits.settings import Settings


@pytest.fixture
def error_app(settings, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "lnbits_rate_limit_no", 2)
    monkeypatch.setattr(settings, "lnbits_rate_limit_unit", "minute")
    app = FastAPI()
    register_new_ratelimiter(app)()
    register_exception_handlers(app)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(SlowAPIMiddleware)
    (tmp_path / "existing.txt").write_text("existing")
    app.mount("/static", StaticFiles(directory=tmp_path))

    @app.get("/known")
    async def known(request: Request):
        return {"ok": True}

    @app.get("/known-missing")
    async def known_missing(request: Request):
        raise HTTPException(404, "Not Found")

    return app


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/missing", "/static/missing"])
@pytest.mark.parametrize(
    "headers",
    [{"User-Agent": "Mozilla/5.0"}, {"Accept": "text/html"}],
)
async def test_unknown_browser_url_is_small_without_rendering(
    error_app, monkeypatch, headers, path
):
    renderer = Mock(side_effect=AssertionError("Must not render the full UI"))
    monkeypatch.setattr("lnbits.exceptions.template_renderer", renderer)
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        response = await client.get(path, headers=headers)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert len(response.content) < 1000
    assert "content-encoding" not in response.headers
    assert 'href="/"' in response.text
    renderer.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path,headers",
    [("/missing", {}), ("/api/v1/missing", {"User-Agent": "Mozilla/5.0"})],
)
async def test_unknown_api_url_keeps_json(error_app, path, headers):
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        response = await client.get(path, headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.anyio
async def test_unknown_urls_share_limit_across_paths_and_methods(error_app):
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        assert (await client.get("/missing-one")).status_code == 404
        assert (await client.get("/static/missing-two")).status_code == 404
        blocked = await client.get("/missing-three")
        assert blocked.status_code == 429
        assert "Rate limit exceeded" in blocked.json()["error"]
        assert (await client.post("/missing-four")).status_code == 429
        assert (await client.get("/static/another-missing")).status_code == 429
        assert (await client.get("/static/existing.txt")).status_code == 200
        # Unknown paths cannot consume the allowance of a real endpoint.
        assert (await client.get("/known")).status_code == 200
        assert (await client.get("/known")).status_code == 200
        assert (await client.get("/known")).status_code == 429

    async with AsyncClient(
        transport=ASGITransport(app=error_app, client=("192.0.2.2", 123)),
        base_url="http://test",
    ) as other_client:
        assert (await other_client.get("/missing-three")).status_code == 404


@pytest.mark.anyio
async def test_unknown_route_limit_updates_with_admin_settings(error_app, settings):
    async with AsyncClient(
        transport=ASGITransport(app=error_app), base_url="http://test"
    ) as client:
        assert (await client.get("/missing")).status_code == 404
        settings.lnbits_rate_limit_no = 1
        register_new_ratelimiter(error_app)()
        assert (await client.get("/missing")).status_code == 404
        assert (await client.get("/another-missing")).status_code == 429


@pytest.mark.anyio
async def test_known_browser_404_keeps_full_ui_and_is_limited(error_app):
    async with AsyncClient(
        transport=ASGITransport(app=error_app),
        base_url="http://test",
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        response = await client.get("/known-missing")
        assert response.status_code == 404
        assert '<div id="vue">' in response.text
        assert (await client.get("/known-missing")).status_code == 404
        assert (await client.get("/known-missing")).status_code == 429


@pytest.mark.anyio
async def test_uninstalled_extension_keeps_message_and_limit(error_app, monkeypatch):
    monkeypatch.setattr(
        Settings, "is_ready_to_install_extension_id", lambda self, path: path == "tpos"
    )
    async with AsyncClient(
        transport=ASGITransport(app=error_app),
        base_url="http://test",
        headers={"User-Agent": "Mozilla/5.0"},
    ) as client:
        response = await client.get("/tpos")
        assert response.status_code == 403
        assert "not installed. Ask the admin to install it." in response.text
        assert '<div id="vue">' in response.text
        assert (await client.get("/tpos/other")).status_code == 403
        assert (await client.get("/tpos/another")).status_code == 429
