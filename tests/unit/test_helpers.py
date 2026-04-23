import hashlib

import jwt
import pytest
from fastapi import FastAPI

from lnbits.helpers import (
    camel_to_snake,
    camel_to_words,
    check_callback_url,
    create_access_token,
    decrypt_internal_message,
    download_url,
    encrypt_internal_message,
    file_hash,
    filter_dict_keys,
    get_api_routes,
    get_db_vendor_name,
    is_camel_case,
    is_lnbits_version_ok,
    is_snake_case,
    is_valid_email_address,
    is_valid_external_id,
    is_valid_label,
    is_valid_pubkey,
    is_valid_username,
    lowercase_first_letter,
    normalize_endpoint,
    normalize_path,
    path_segments,
    sha256s,
    snake_to_camel,
    static_url_for,
    url_for,
    version_parse,
)
from lnbits.settings import Settings


@pytest.mark.anyio
def test_check_callback_url_not_allowed(settings: Settings):
    settings.lnbits_callback_url_rules = [
        "https?://([a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})(:\\d+)?"
    ]
    with pytest.raises(ValueError, match="Callback not allowed. URL: xx. Netloc: ."):
        check_callback_url("xx")

    with pytest.raises(
        ValueError,
        match="Callback not allowed. URL: http://localhost:3000/callback. "
        "Netloc: localhost:3000. Please check your admin settings.",
    ):
        check_callback_url("http://localhost:3000/callback")

    with pytest.raises(
        ValueError,
        match="Callback not allowed. URL: https://localhost:3000/callback. "
        "Netloc: localhost:3000. Please check your admin settings.",
    ):
        check_callback_url("https://localhost:3000/callback")

    with pytest.raises(
        ValueError,
        match="Callback not allowed. URL: http://192.168.2.2:3000/callback. "
        "Netloc: 192.168.2.2:3000. Please check your admin settings.",
    ):
        check_callback_url("http://192.168.2.2:3000/callback")


@pytest.mark.anyio
def test_check_callback_url_no_rules(settings: Settings):
    settings.lnbits_callback_url_rules = [
        "https?://([a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})(:\\d+)?"
    ]
    settings.lnbits_callback_url_rules.append(".*")
    check_callback_url("xyz")


@pytest.mark.anyio
def test_check_callback_url_allow_all(settings: Settings):
    settings.lnbits_callback_url_rules = []
    check_callback_url("xyz")


@pytest.mark.anyio
def test_check_callback_url_allowed(settings: Settings):
    settings.lnbits_callback_url_rules = [
        "https?://([a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})(:\\d+)?"
    ]
    check_callback_url("http://google.com/callback")
    check_callback_url("http://google.com:80/callback")
    check_callback_url("http://google.com:8080/callback")
    check_callback_url("https://google.com/callback")
    check_callback_url("https://google.com:443/callback")


@pytest.mark.anyio
def test_check_callback_url_multiple_rules(settings: Settings):
    with pytest.raises(
        ValueError,
        match="Callback not allowed. URL: http://localhost:3000/callback. "
        "Netloc: localhost:3000. Please check your admin settings.",
    ):
        check_callback_url("http://localhost:3000/callback")

    settings.lnbits_callback_url_rules.append("http://localhost:3000")
    check_callback_url("http://localhost:3000/callback")  # should not raise

    with pytest.raises(
        ValueError,
        match="Callback not allowed. URL: https://localhost:3000/callback. "
        "Netloc: localhost:3000. Please check your admin settings.",
    ):
        check_callback_url("https://localhost:3000/callback")

    settings.lnbits_callback_url_rules.append("https://localhost:3000")
    check_callback_url("https://localhost:3000/callback")  # should not raise


def test_get_db_vendor_name(settings: Settings):
    original_database_url = settings.lnbits_database_url
    try:
        settings.lnbits_database_url = None
        assert get_db_vendor_name() == "SQLite"

        settings.lnbits_database_url = "postgres://localhost/db"
        assert get_db_vendor_name() == "PostgreSQL"

        settings.lnbits_database_url = "cockroachdb://localhost/db"
        assert get_db_vendor_name() == "CockroachDB"
    finally:
        settings.lnbits_database_url = original_database_url


def test_url_helpers(settings: Settings):
    assert url_for("/api/v1/wallet", external=False, usr="user") == (
        "/api/v1/wallet?usr=user&"
    )
    assert url_for("/api/v1/wallet", external=True, usr="user") == (
        f"http://{settings.host}:{settings.port}/api/v1/wallet?usr=user&"
    )
    assert static_url_for("static", "bundle.min.js") == (
        f"/static/bundle.min.js?v={settings.server_startup_time}"
    )


@pytest.mark.parametrize(
    ("value", "validator"),
    [
        ("alice@example.com", is_valid_email_address),
        ("alice_1", is_valid_username),
        ("Label 1", is_valid_label),
        ("external-id-1", is_valid_external_id),
        ("a" * 64, is_valid_pubkey),
    ],
)
def test_validation_helpers_valid(value, validator):
    assert validator(value) is True


@pytest.mark.parametrize(
    ("value", "validator"),
    [
        ("alice@example", is_valid_email_address),
        ("_alice", is_valid_username),
        ("bad/label", is_valid_label),
        ("contains spaces", is_valid_external_id),
        ("xyz", is_valid_pubkey),
    ],
)
def test_validation_helpers_invalid(value, validator):
    assert validator(value) is False


def test_is_valid_external_id_rejects_long_and_multiline_values():
    assert is_valid_external_id("x" * 257) is False
    assert is_valid_external_id("evil\nnewline") is False


def test_access_token_and_internal_message_helpers(settings: Settings):
    token = create_access_token(
        {"sub": "alice", "usr": None, "email": "alice@example.com"},
        token_expire_minutes=1,
    )
    payload = jwt.decode(token, settings.auth_secret_key, ["HS256"])
    assert payload["sub"] == "alice"
    assert payload["email"] == "alice@example.com"
    assert "usr" not in payload
    assert "exp" in payload

    assert encrypt_internal_message(None) is None
    assert decrypt_internal_message(None) is None

    encrypted = encrypt_internal_message("secret-message", urlsafe=True)
    assert encrypted is not None
    assert decrypt_internal_message(encrypted, urlsafe=True) == "secret-message"


def test_filter_dict_keys_returns_copy_when_no_filters():
    original = {"a": 1, "b": 2}

    clone = filter_dict_keys(original, None)
    filtered = filter_dict_keys(original, ["b", "missing"])

    assert clone == original
    assert clone is not original
    assert filtered == {"b": 2}


def test_version_helpers(settings: Settings):
    original_version = settings.version
    try:
        settings.version = "1.2.3"
        assert version_parse("1.2.3rc4") == version_parse("1.2.3")
        assert version_parse("invalid-version") == version_parse("0.0.0")
        assert is_lnbits_version_ok("1.2.0", "2.0.0") is True
        assert is_lnbits_version_ok("2.0.0", None) is False
        assert is_lnbits_version_ok(None, "1.2.3") is False
    finally:
        settings.version = original_version


def test_download_url_rejects_non_http_schemes(tmp_path):
    with pytest.raises(
        ValueError, match="Invalid URL: ftp://example.com. Must start with 'http'"
    ):
        download_url("ftp://example.com", tmp_path / "download.bin")


def test_file_hash(tmp_path):
    filename = tmp_path / "payload.txt"
    filename.write_text("hello world")

    assert file_hash(filename) == hashlib.sha256(b"hello world").hexdigest()


def test_get_api_routes_extracts_v1_paths():
    app = FastAPI()

    @app.get("/api/v1/payments")
    async def payments():
        return {}

    @app.get("/myext/api/v1/settings")
    async def extension_settings():
        return {}

    @app.get("/health")
    async def health():
        return {}

    routes = get_api_routes([*app.routes, object()])

    assert routes == {
        "/api/v1/payments": "Payments",
        "/myext/api/v1": "Myext",
    }


def test_path_and_case_helpers():
    assert path_segments("/wallet/path") == ["wallet", "path"]
    assert path_segments("/upgrades/ext/assets/app.js") == ["assets", "app.js"]
    assert normalize_path(None) == "/"
    assert normalize_path("/upgrades/ext/assets/app.js") == "/assets/app.js"
    assert normalize_endpoint("example.com/") == "https://example.com"
    assert normalize_endpoint("ws://socket.example.com") == "ws://socket.example.com"
    assert (
        normalize_endpoint("http://example.com/", add_proto=False)
        == "http://example.com"
    )

    assert camel_to_words("CamelCaseName") == "Camel Case Name"
    assert camel_to_snake("CamelCaseName") == "camel_case_name"
    assert snake_to_camel("snake_case_name") == "snakeCaseName"
    assert snake_to_camel("snake_case_name", capitalize_first=True) == "SnakeCaseName"
    assert is_camel_case("CamelCase1") is True
    assert is_camel_case("camelCase") is False
    assert is_snake_case("snake_case_1") is True
    assert is_snake_case("SnakeCase") is False
    assert lowercase_first_letter("Hello") == "hello"
    assert sha256s("hello") == hashlib.sha256(b"hello").hexdigest()
