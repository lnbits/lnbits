from __future__ import annotations

import re
from re import Pattern

from playwright.sync_api import Page, expect

from tests.wasm_ext.helpers import LiveLNbitsServer


def test_public_wasm_page_loads_sandboxed_frame(
    page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    public_url = (
        f"{lnbits_server.base_url}/ext/{lnbits_server.extension_id}/public/item-123"
        "?source=test"
    )
    frame_url_part = f"/ext-frame/{lnbits_server.extension_id}/1"

    with page.expect_response(lambda response: frame_url_part in response.url) as info:
        page.goto(public_url)

    frame_response = info.value
    assert frame_response.status == 200
    assert "sandbox allow-scripts" in frame_response.headers["content-security-policy"]
    assert frame_response.headers["cache-control"] == "no-store"
    assert frame_response.headers["x-content-type-options"] == "nosniff"

    frame = page.locator("iframe.wasm-extension-frame")
    expect(frame).to_have_attribute("sandbox", "allow-scripts")
    expect(frame).to_have_attribute("allow", "clipboard-write")
    expect(frame).to_have_attribute("referrerpolicy", "no-referrer")
    expect(frame).to_have_attribute("src", _frame_src_pattern(frame_url_part))
    expect(
        page.frame_locator("iframe.wasm-extension-frame").locator("body")
    ).to_contain_text("WASM Test Public")


def test_frame_token_is_route_bound_required_and_single_use(
    page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    frame_config = page.request.post(
        f"{lnbits_server.base_url}/api/v1/ext/"
        f"{lnbits_server.extension_id}/_ui/frame",
        data={
            "path": f"/ext/{lnbits_server.extension_id}/public/item-123",
            "query": {"source": "test"},
        },
    )
    assert frame_config.status == 200
    frame_url = frame_config.json()["frameUrl"]

    missing_token = page.request.get(
        f"{lnbits_server.base_url}/ext-frame/{lnbits_server.extension_id}/1"
    )
    assert missing_token.status == 404

    wrong_route = page.request.get(
        f"{lnbits_server.base_url}{frame_url.replace('/1?', '/0?')}"
    )
    assert wrong_route.status == 404

    first_use = page.request.get(f"{lnbits_server.base_url}{frame_url}")
    assert first_use.status == 200
    assert "form-action 'none'" in first_use.headers["content-security-policy"]

    second_use = page.request.get(f"{lnbits_server.base_url}{frame_url}")
    assert second_use.status == 404


def test_private_wasm_page_uses_lnbits_shell_and_private_frame(
    authenticated_page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    page = authenticated_page
    frame_url_part = f"/ext-frame/{lnbits_server.extension_id}/0"

    with page.expect_response(lambda response: frame_url_part in response.url) as info:
        page.goto(f"{lnbits_server.base_url}/ext/{lnbits_server.extension_id}")

    assert info.value.status == 200
    expect(page.locator("body")).to_contain_text("LNbits")
    frame = page.locator("iframe.wasm-extension-frame")
    expect(frame).to_have_attribute("sandbox", "allow-scripts")
    expect(frame).to_have_attribute("src", _frame_src_pattern(frame_url_part))
    expect(
        page.frame_locator("iframe.wasm-extension-frame").locator("body")
    ).to_contain_text("WASM Test Admin")


def _frame_src_pattern(frame_url_part: str) -> Pattern[str]:
    return re.compile(f"^{re.escape(frame_url_part)}\\?frame_token=[a-f0-9]{{32}}$")
