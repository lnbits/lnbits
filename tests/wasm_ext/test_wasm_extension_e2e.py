from __future__ import annotations

import json
import re
from re import Pattern
from typing import Any

from playwright.sync_api import Frame, Page, expect

from tests.wasm_ext.helpers import EXTENSION_ID, REPO_ROOT, LiveLNbitsServer


def test_permission_grant_dialog_logic_is_compact_and_explicit(page: Page) -> None:
    permissions = _fixture_permissions()
    page.goto("about:blank")
    page.add_script_tag(path=str(REPO_ROOT / "lnbits/static/js/pages/extensions.js"))

    result = page.evaluate(
        """
        ({permissions, translations}) => {
          const methods = window.PageExtensions.methods
          const context = {
            extensions: [{id: 'watchonly', name: 'Watchonly'}],
            permissionGrant: {show: false, permissions: [], resolve: null},
            selectedExtension: {isWasm: true},
            selectedRelease: null,
            showManageExtensionDialog: false,
            $t: key => translations[key] || key
          }
          Object.assign(context, methods)

          const release = {extension_type: 'wasm', permissions}
          const pendingGrant = context.resolveExtensionPermissionGrant(release)
          const opened =
            context.permissionGrant.show === true &&
            context.showManageExtensionDialog === true
          const items = context.permissionGrantDisplayItems()
          context.grantExtensionPermissions()

          return pendingGrant.then(grantedPermissions => ({
            opened,
            closed:
              context.permissionGrant.show === false &&
              context.showManageExtensionDialog === false,
            grantedPermissionIds: grantedPermissions.map(permission => permission.id),
            items
          }))
        }
        """,
        {"permissions": permissions, "translations": _permission_translations()},
    )

    assert result["opened"] is True
    assert result["closed"] is True
    assert result["grantedPermissionIds"] == [
        permission["id"] for permission in permissions
    ]

    items = result["items"]
    assert [item["id"] for item in items] == [
        "wallet.pay_invoice",
        "wallet.list",
        "wallet.balance.read",
        "extension.api.request",
        "ui.camera.scan_qr",
        "ext.storage.read_write",
        "ext.storage.read_public",
        "wallet.create_invoice_public",
        "wallet.create_invoice",
        "utils.basic",
    ]

    by_id = {item["id"]: item for item in items}
    assert by_id["wallet.pay_invoice"]["risk"]["level"] == "high"
    assert by_id["extension.api.request"]["risk"]["level"] == "high"
    assert by_id["ext.storage.read_write"]["risk"]["level"] == "low"
    assert by_id["wallet.create_invoice"]["risk"]["level"] == "low"
    assert by_id["ui.camera.scan_qr"]["risk"]["level"] == "low"

    assert by_id["ext.storage.read_write"]["label"] == (
        "Read & Write extension storage"
    )
    assert by_id["ext.storage.read_public"]["badges"] == [
        {"key": "tip_jars", "label": "tip_jars"}
    ]
    assert by_id["ext.storage.read_public"]["fieldGroups"] == [
        {
            "table": "tip_jars",
            "fields": [
                "id",
                "title",
                "description",
                "currency",
                "suggested_amounts",
            ],
        }
    ]
    assert by_id["extension.api.request"]["badges"] == [
        {"key": "watchonly", "label": "Watchonly"}
    ]
    assert by_id["extension.api.request"]["extensionAccess"] == [
        {"id": "watchonly", "name": "Watchonly", "access": ["read", "write"]}
    ]
    assert by_id["wallet.create_invoice_public"]["invoicePolicies"] == [
        {"table": "tip_jars", "walletField": "wallet_id"}
    ]


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


def test_static_assets_are_strictly_whitelisted(
    page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    assets_base = f"{lnbits_server.base_url}/ext-assets/{lnbits_server.extension_id}"

    script = page.request.get(f"{assets_base}/app.js")
    assert script.status == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert script.headers["x-content-type-options"] == "nosniff"
    assert script.headers["cache-control"] == "no-store"

    core_script = page.request.get(f"{assets_base}/_lnbits/vue.global.prod.js")
    assert core_script.status == 200
    assert core_script.headers["content-type"].startswith("text/javascript")
    assert core_script.headers["x-content-type-options"] == "nosniff"

    unsupported_extension = page.request.get(f"{assets_base}/data.json")
    assert unsupported_extension.status == 404

    html_like_javascript = page.request.get(f"{assets_base}/html-like.js")
    assert html_like_javascript.status == 404


def test_frame_config_exposes_permissions_and_filters_public_routes(
    authenticated_page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    public_config = authenticated_page.request.post(
        _frame_config_url(lnbits_server),
        data={
            "path": f"/ext/{lnbits_server.extension_id}/public/item-123",
            "query": {"source_id": "abc", "empty": None},
        },
    )
    assert public_config.status == 200
    public_bridge = public_config.json()["bridge"]
    assert public_bridge["public"] is True
    assert public_bridge["routeParams"] == {"itemId": "item-123"}
    assert public_bridge["query"] == {"sourceId": "abc"}
    assert {route["path"] for route in public_bridge["apiRoutes"]} == {
        f"/api/v1/ext/{lnbits_server.extension_id}/jars/{{jar_id}}",
        f"/api/v1/ext/{lnbits_server.extension_id}/invoice",
    }

    private_config = authenticated_page.request.post(
        _frame_config_url(lnbits_server),
        data={"path": f"/ext/{lnbits_server.extension_id}", "query": {}},
    )
    assert private_config.status == 200
    private_bridge = private_config.json()["bridge"]
    assert private_bridge["public"] is False
    assert set(private_bridge["permissions"]) == {
        permission["id"] for permission in _fixture_permissions()
    }
    assert {route["path"] for route in private_bridge["apiRoutes"]} == {
        f"/api/v1/ext/{lnbits_server.extension_id}/wallets",
        f"/api/v1/ext/{lnbits_server.extension_id}/payments",
        f"/api/v1/ext/{lnbits_server.extension_id}/jars/{{jar_id}}",
        f"/api/v1/ext/{lnbits_server.extension_id}/invoice",
    }


def test_private_frame_config_and_api_routes_require_auth(
    page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    private_config = page.request.post(
        _frame_config_url(lnbits_server),
        data={"path": f"/ext/{lnbits_server.extension_id}", "query": {}},
    )
    assert private_config.status == 401

    private_api = page.request.get(
        f"{lnbits_server.base_url}/api/v1/ext/{lnbits_server.extension_id}/wallets"
    )
    assert private_api.status == 401

    public_config = page.request.post(
        _frame_config_url(lnbits_server),
        data={
            "path": f"/ext/{lnbits_server.extension_id}/public/item-123",
            "query": {},
        },
    )
    assert public_config.status == 200


def test_bridge_context_and_denied_api_request(
    page: Page,
    lnbits_server: LiveLNbitsServer,
) -> None:
    frame_url_part = f"/ext-frame/{lnbits_server.extension_id}/1"

    with page.expect_response(lambda response: frame_url_part in response.url):
        page.goto(
            f"{lnbits_server.base_url}/ext/{lnbits_server.extension_id}"
            "/public/item-123?source=test"
        )

    frame = _wasm_frame(page, frame_url_part)
    assert frame.evaluate("() => window.lnbitsWasmTestBridge.ready()") is True

    context_response = frame.evaluate("""
        () => window.lnbitsWasmTestBridge.request({
          action: 'context'
        })
        """)
    assert context_response == {
        "type": "lnbits-extension:response",
        "id": "wasm-test-1",
        "ok": True,
        "data": {
            "extensionId": EXTENSION_ID,
            "public": True,
            "routeParams": {"itemId": "item-123"},
            "query": {"source": "test"},
        },
    }

    denied_response = frame.evaluate("""
        () => window.lnbitsWasmTestBridge.request({
          action: 'api',
          method: 'GET',
          path: '/api/v1/wallets'
        })
        """)
    assert denied_response["ok"] is False
    assert denied_response["error"] == "Extension API route is not allowed."

    unknown_response = frame.evaluate("""
        () => window.lnbitsWasmTestBridge.request({
          action: 'unknown'
        })
        """)
    assert unknown_response["ok"] is False
    assert unknown_response["error"] == "Unknown extension bridge action."


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


def _frame_config_url(lnbits_server: LiveLNbitsServer) -> str:
    return (
        f"{lnbits_server.base_url}/api/v1/ext/"
        f"{lnbits_server.extension_id}/_ui/frame"
    )


def _fixture_permissions() -> list[dict[str, Any]]:
    config = json.loads(
        (REPO_ROOT / "tests/fixtures" / EXTENSION_ID / "config.json").read_text()
    )
    permissions = config["permissions"]
    assert isinstance(permissions, list)
    return permissions


def _permission_translations() -> dict[str, str]:
    return {
        "extension_permission_access_read": "Read",
        "extension_permission_access_write": "Write",
        "extension_permission_ext_storage_read_public": (
            "Read public extension storage"
        ),
        "extension_permission_ext_storage_read_write": (
            "Read & Write extension storage"
        ),
        "extension_permission_extension_api_request": "Use other extensions",
        "extension_permission_risk_high": "High risk",
        "extension_permission_risk_low": "Low risk",
        "extension_permission_risk_medium": "Medium risk",
        "extension_permission_ui_camera_scan_qr": "Scan QR codes",
        "extension_permission_utils_basic": "Use basic LNbits utilities",
        "extension_permission_wallet_balance_read": "View wallet balances",
        "extension_permission_wallet_create_invoice": "Create invoices",
        "extension_permission_wallet_create_invoice_public": (
            "Create Lightning invoices from public pages"
        ),
        "extension_permission_wallet_list": "List wallets",
        "extension_permission_wallet_pay_invoice": "Pay invoices",
        "extension_permission_warning_extension_api_request_write": (
            "This extension can write to another extension."
        ),
        "extension_permission_warning_wallet_pay_invoice": (
            "This extension can spend from selected wallets."
        ),
    }


def _wasm_frame(page: Page, frame_url_part: str) -> Frame:
    frame = page.frame(url=lambda url: frame_url_part in url)
    assert frame is not None
    return frame
