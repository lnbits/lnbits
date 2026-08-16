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


def test_wasm_extension_routes_keep_global_wallet_dialog_mounted():
    base_template = (ROOT / "lnbits/templates/base.html").read_text(encoding="utf-8")
    wallet_dialog_start = base_template.index("<lnbits-wallet-new")
    wallet_dialog_end = base_template.index(
        "></lnbits-wallet-new>", wallet_dialog_start
    )
    wallet_dialog = base_template[wallet_dialog_start:wallet_dialog_end]

    assert 'v-if="g.user && !g.isPublicPage"' in wallet_dialog
    assert "!$route.path.startsWith('/ext/')" not in wallet_dialog


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
    assert "message.action === 'websocket.send'" in bridge
    assert "sendWebsocket(message)" in bridge
    assert "Unknown websocket subscription." not in bridge
    assert "if (!subscription) {\n        return\n      }" in bridge
    assert "message.action === 'navigation.replace'" in bridge
    assert "message.action === 'navigation.open_new_tab'" in bridge
    assert "openNewTab(message)" in bridge
    assert "newTabUrl(rawUrl)" in bridge
    assert "copyNewTabLink()" in bridge
    assert "navigator.clipboard.writeText(prompt.url)" in bridge
    assert 'label="Copy Link"' in bridge
    assert "window.open(prompt.url, '_blank', 'noopener,noreferrer')" in bridge
    assert "Only HTTP and HTTPS links can be opened." in bridge
    assert "This link is not on the same domain as this LNbits page." in bridge
    assert "message.action === 'storage.session.get'" in bridge
    assert "message.action === 'storage.session.set'" in bridge
    assert "bridgeSessionStorageKey(rawKey)" in bridge
    assert "lnbits.ext.session.${this.bridge.extensionId}.${key}" in bridge
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


def test_extension_install_ui_warns_only_for_python_releases():
    extensions_template = (ROOT / "lnbits/templates/pages/extensions.vue").read_text(
        encoding="utf-8"
    )

    assert "release.extension_type !== 'wasm'" in extensions_template
    assert (
        "'Python extensions have full server access. Trust the source.'"
        in extensions_template
    )
    assert '<q-icon name="info"' in extensions_template


def test_extension_details_render_in_isolated_frame():
    extensions_page = (ROOT / "lnbits/static/js/pages/extensions.js").read_text(
        encoding="utf-8"
    )
    extensions_template = (ROOT / "lnbits/templates/pages/extensions.vue").read_text(
        encoding="utf-8"
    )

    assert 'v-html="selectedExtensionDetails.description_md"' not in extensions_template
    assert ':srcdoc="selectedExtensionDetailsDescription"' in extensions_template
    assert (
        'sandbox="allow-popups allow-popups-to-escape-sandbox"' in extensions_template
    )
    assert 'referrerpolicy="no-referrer"' in extensions_template

    assert "\"default-src 'none'\"" in extensions_page
    assert "\"script-src 'none'\"" in extensions_page
    assert "\"script-src-attr 'none'\"" in extensions_page
    assert "attributeName === 'xlink:href'" in extensions_page
    assert "['http:', 'https:'].includes(url.protocol)" in extensions_page
    assert "link.setAttribute('target', '_blank')" in extensions_page
    assert "link.setAttribute('rel', 'noopener noreferrer')" in extensions_page
    assert "title: 'Open external link?'" not in extensions_page


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
