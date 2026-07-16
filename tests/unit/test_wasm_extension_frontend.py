import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_wasm_frontend_assets_are_registered_in_component_bundle():
    package_json = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    components = package_json["bundle"]["components"]

    assert "js/wasm-extension-component.js" in components
    assert "js/components/lnbits-extension-permissions.js" in components
    assert "js/components/admin/lnbits-admin-wasm-runtime.js" in components
    assert "js/components/admin/lnbits-admin-wasm-limit-config.js" in components


def test_wasm_frontend_bridge_restricts_api_routes_and_realtime_actions():
    bridge = (ROOT / "lnbits/static/js/wasm-extension-component.js").read_text(
        encoding="utf-8"
    )

    assert "allowedApiRoute(method, path)" in bridge
    assert "url.origin !== window.location.origin" in bridge
    assert "Extension API route is not allowed." in bridge
    assert "extensionRoute(path)" in bridge
    assert "Extension route must stay inside this extension." in bridge
    assert "message.action === 'payment.subscribe'" in bridge
    assert "message.action === 'payment.unsubscribe'" in bridge
    assert "message.action === 'websocket.subscribe'" in bridge
    assert "message.action === 'websocket.unsubscribe'" in bridge
    assert "message.action === 'navigation.replace'" in bridge
    assert "hasBridgePermission('websocket.subscribe')" in bridge
    assert "/api/v1/ext/ws/${encodeURIComponent(" in bridge
    assert "/api/v1/ws/${encodeURIComponent(paymentHash)}" in bridge
    assert "message.action === 'ui.scan_qr'" in bridge


def test_wasm_extension_install_ui_requests_permissions_before_install_paths():
    extensions_page = (ROOT / "lnbits/static/js/pages/extensions.js").read_text(
        encoding="utf-8"
    )
    permissions_template = (
        ROOT / "lnbits/templates/components/lnbits-extension-permissions.vue"
    ).read_text(encoding="utf-8")
    wasm_bulk_update_skip_message = (
        "Skipping ${ext.id}; this extension update requires permission approval."
    )

    assert "await this.resolveExtensionPermissionGrant(release)" in extensions_page
    assert "permissions: grantedPermissions" in extensions_page
    assert "release.extension_type === 'wasm'" in extensions_page
    assert "this.selectedExtension?.isWasm === true" in extensions_page
    assert "saveManagedExtensionPermissions()" in extensions_page
    assert (
        "`/api/v1/extension/${this.selectedExtension.id}/permissions`"
        in extensions_page
    )
    assert "editableAppendPublicLimits" in permissions_template
    assert "max_rows_per_source" in permissions_template
    assert "editableWebsocketPublishLimits" in permissions_template
    assert "max_messages_per_second" in permissions_template
    assert wasm_bulk_update_skip_message in extensions_page


def test_wasm_admin_frontend_calls_runtime_limit_and_invocation_endpoints():
    runtime = (
        ROOT / "lnbits/static/js/components/admin/lnbits-admin-wasm-runtime.js"
    ).read_text(encoding="utf-8")
    limits = (
        ROOT / "lnbits/static/js/components/admin/lnbits-admin-wasm-limit-config.js"
    ).read_text(encoding="utf-8")

    assert "/api/v1/extension/wasm/invocations/current" in runtime
    assert "/api/v1/extension/wasm/invocations?" in runtime
    assert "/api/v1/extension/wasm/invocations/stats?" in runtime
    assert "/api/v1/extension/wasm/runtime-limits/extensions" in limits
    assert "/api/v1/extension/wasm/runtime-limits/${encodeURIComponent(" in limits
