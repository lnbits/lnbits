import html
import json


def python_scaffold(ext_id: str, name: str, description: str) -> dict[str, bytes]:
    manifest = {
        "id": ext_id,
        "name": name,
        "short_description": description,
        "version": "0.1.0",
        "extension_type": "wasm",
        "wasm": {
            "module": "wasm/module.wasm",
            "wit": "wasm/lnbits-extension.wit",
            "world": "studio-extension",
            "exports": [{"name": "hello", "visibility": "authenticated"}],
        },
        "ui_routes": [
            {"path": "/" + ext_id, "entrypoint": "ui/index.html", "auth": "user"}
        ],
        "api_routes": [
            {"method": "GET", "path": "/hello", "export": "hello", "auth": "user"}
        ],
        "permissions": [],
    }
    return {
        "config.json": (json.dumps(manifest, indent=2) + "\n").encode(),
        "src/app.py": (
            b"import json\nimport wit_world\n\n\nclass WitWorld(wit_world.WitWorld):\n "
            b"   def hello(self, request_json: str) -> str:\n        return"
            b' json.dumps({"ok": True, "message": "Hello from Python WASM!"})\n'
        ),
        "wasm/lnbits-extension.wit": (
            b"package lnbits:extension;\n\nworld studio-extension {\n    export hello:"
            b" func(request-json: string) -> string;\n}\n"
        ),
        "ui/index.html": (
            '<!doctype html>\n<html><head><meta charset="utf-8">'
            f'<title>{html.escape(name)}</title><link rel="stylesheet" '
            f'href="/ext-assets/{ext_id}/studio.css"></head><body>'
            f"<h1>{html.escape(name)}</h1><p>Your extension is ready to build.</p>"
            "</body></html>\n"
        ).encode(),
        "static/studio.css": (
            b"body { font-family: system-ui, sans-serif; margin: 0; padding: 32px; "
            b"color: #202124; background: #fff; }\n"
            b"@media (prefers-color-scheme: dark) { body { color: #f4f4f5; "
            b"background: #18181b; } }\n"
        ),
    }
