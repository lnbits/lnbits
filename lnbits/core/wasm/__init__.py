WASM_HOST_API_VERSION = "1.0"

WASM_HOST_MANIFEST = {
    "version": WASM_HOST_API_VERSION,
    "host_functions": [
        "db_get",
        "db_set",
        "db_secret_get",
        "db_secret_set",
        "http_request",
        "ws_publish",
    ],
    "routes": [
        {"method": "GET", "path": "/{ext_id}/", "public": False},
        {"method": "GET", "path": "/{ext_id}/public/{key}", "public": True},
        {
            "method": "GET",
            "path": "/{ext_id}/api/v1/kv/{key}",
            "permission": "ext.db.read_write",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/kv/{key}",
            "permission": "ext.db.read_write",
        },
        {
            "method": "GET",
            "path": "/{ext_id}/api/v1/public/kv/{key}",
            "public": True,
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/secret/{key}",
            "permission": "ext.db.read_write",
        },
        {
            "method": "DELETE",
            "path": "/{ext_id}/api/v1/secret/{key}",
            "permission": "ext.db.read_write",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/public/call/{handler}",
            "public": True,
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/watch",
            "permission": "ext.payments.watch",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/watch_tag",
            "permission": "ext.payments.watch",
        },
        {
            "method": "DELETE",
            "path": "/{ext_id}/api/v1/watch_tag",
            "permission": "ext.payments.watch",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/schedule",
            "permission": "ext.tasks.schedule",
        },
        {
            "method": "DELETE",
            "path": "/{ext_id}/api/v1/schedule",
            "permission": "ext.tasks.schedule",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/sql/query",
            "permission": "ext.db.sql",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/sql/exec",
            "permission": "ext.db.sql",
        },
        {
            "method": "POST",
            "path": "/{ext_id}/api/v1/proxy",
            "permission": "api.METHOD:/path",
        },
    ],
}
