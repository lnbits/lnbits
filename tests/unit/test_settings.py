import pytest
from pydantic import ValidationError

from lnbits.settings import EditableSettings, RedirectPath, Settings, UpdateSettings

lnurlp_redirect_path = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
}
lnurlp_redirect_path_with_headers = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
    "header_filters": {"accept": "application/nostr+json"},
}

lnaddress_redirect_path = {
    "from_path": "/.well-known/lnurlp",
    "redirect_to_path": "/api/v1/well-known",
}

nostrrelay_redirect_path = {
    "from_path": "/",
    "redirect_to_path": "/api/v1/relay-info",
    "header_filters": {"accept": "application/nostr+json"},
}


@pytest.fixture()
def lnurlp():
    return RedirectPath(ext_id="lnurlp", **lnurlp_redirect_path)


@pytest.fixture()
def lnurlp_with_headers():
    return RedirectPath(
        ext_id="lnurlp_with_headers", **lnurlp_redirect_path_with_headers
    )


@pytest.fixture()
def lnaddress():
    return RedirectPath(ext_id="lnaddress", **lnaddress_redirect_path)


@pytest.fixture()
def nostrrelay():
    return RedirectPath(ext_id="nostrrelay", **nostrrelay_redirect_path)


def test_redirect_path_self_not_in_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert not lnurlp.in_conflict(lnurlp), "Path is not in conflict with itself."
    assert not lnaddress.in_conflict(lnaddress), "Path is not in conflict with itself."
    assert not nostrrelay.in_conflict(
        nostrrelay
    ), "Path is not in conflict with itself."

    assert not lnurlp.in_conflict(nostrrelay)

    assert not nostrrelay.in_conflict(lnurlp)


def test_redirect_path_not_in_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):

    assert not lnurlp.in_conflict(nostrrelay)

    assert not nostrrelay.in_conflict(lnurlp)

    assert not lnaddress.in_conflict(nostrrelay)

    assert not nostrrelay.in_conflict(lnaddress)


def test_redirect_path_in_conflict(lnurlp: RedirectPath, lnaddress: RedirectPath):
    assert lnurlp.in_conflict(lnaddress)
    assert lnaddress.in_conflict(lnurlp)


def test_redirect_path_find_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert lnurlp.find_in_conflict([nostrrelay, lnaddress])
    assert lnurlp.find_in_conflict([lnaddress, nostrrelay])
    assert lnaddress.find_in_conflict([nostrrelay, lnurlp])
    assert lnaddress.find_in_conflict([lnurlp, nostrrelay])


def test_redirect_path_find_no_conflict(
    lnurlp: RedirectPath, lnaddress: RedirectPath, nostrrelay: RedirectPath
):
    assert not nostrrelay.find_in_conflict([lnurlp, lnaddress])
    assert not lnurlp.find_in_conflict([nostrrelay])
    assert not lnaddress.find_in_conflict([nostrrelay])


def test_redirect_path_in_conflict_with_headers(
    lnurlp: RedirectPath, lnurlp_with_headers: RedirectPath
):
    assert lnurlp.in_conflict(lnurlp_with_headers)
    assert lnurlp_with_headers.in_conflict(lnurlp)


def test_redirect_path_matches_with_headers(
    lnurlp: RedirectPath, lnurlp_with_headers: RedirectPath
):
    headers_list = list(lnurlp_with_headers.header_filters.items())
    assert lnurlp.redirect_matches(
        path=lnurlp_with_headers.from_path,
        req_headers=headers_list,
    )
    assert lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"],
        req_headers=[("ACCEPT", "APPlication/nostr+json")],
    )
    assert lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"],
        req_headers=[("accept", "application/nostr+json"), ("my_header", "my_value")],
    )

    assert not lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"], req_headers=[]
    )
    assert not lnurlp_with_headers.redirect_matches(
        path=lnurlp_redirect_path["from_path"],
        req_headers=[("accept", "application/json")],
    )
    assert not lnurlp_with_headers.redirect_matches(path="/random/path", req_headers=[])
    assert not lnurlp_with_headers.redirect_matches(path="/random_path", req_headers=[])
    assert not lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp", req_headers=[]
    )
    assert lnurlp.redirect_matches(path="/.well-known/lnurlp", req_headers=[])
    assert lnurlp.redirect_matches(
        path="/.well-known/lnurlp/some/other/path", req_headers=[]
    )
    assert lnurlp.redirect_matches(
        path="/.well-known/lnurlp/some/other/path",
        req_headers=headers_list,
    )
    assert not lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp", req_headers=[]
    )
    assert not lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp/some/other/path", req_headers=[]
    )
    assert lnurlp_with_headers.redirect_matches(
        path="/.well-known/lnurlp/some/other/path",
        req_headers=headers_list,
    )


def test_redirect_path_new_path_from(lnurlp: RedirectPath):
    assert lnurlp.new_path_from("") == "/lnurlp/api/v1/well-known"
    assert lnurlp.new_path_from("/") == "/lnurlp/api/v1/well-known"
    assert lnurlp.new_path_from("/path") == "/lnurlp/api/v1/well-known"
    assert lnurlp.new_path_from("/path/more") == "/lnurlp/api/v1/well-known"

    assert lnurlp.new_path_from("/.well-known/lnurlp") == "/lnurlp/api/v1/well-known"
    assert (
        lnurlp.new_path_from("/.well-known/lnurlp/path")
        == "/lnurlp/api/v1/well-known/path"
    )
    assert (
        lnurlp.new_path_from("/.well-known/lnurlp/path/more")
        == "/lnurlp/api/v1/well-known/path/more"
    )


def test_settings_loads_env_and_dotenv_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "lnbits_admin_users=alice,bob",
                "STRIKE_API_ENDPOINT=https://dotenv.strike.example",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LNBITS_ALLOWED_USERS", ' ["carol", "dave"] ')
    monkeypatch.setenv("STRIKE_API_KEY", "secret-key")
    monkeypatch.setenv("STRIKE_API_ENDPOINT", "https://env.strike.example")

    settings = Settings()

    assert settings.lnbits_admin_users == ["alice", "bob"]
    assert settings.lnbits_allowed_users == ["carol", "dave"]
    assert settings.strike_api_endpoint == "https://env.strike.example"
    assert settings.strike_api_key == "secret-key"


def test_editable_settings_from_dict_ignores_unknown_fields():
    editable_settings = EditableSettings.from_dict(
        {"lnbits_admin_users": ["alice"], "unknown_setting": "ignored"}
    )

    assert editable_settings.lnbits_admin_users == ["alice"]
    assert "unknown_setting" not in editable_settings.model_dump()


def test_update_settings_splits_string_lists_and_forbids_extra_fields():
    updated = UpdateSettings.model_validate(
        {
            "lnbits_admin_users": "alice,bob",
            "strike_api_endpoint": "https://api.strike.me/v1",
            "strike_api_key": "secret-key",
        }
    )

    assert updated.lnbits_admin_users == ["alice", "bob"]
    assert updated.strike_api_endpoint == "https://api.strike.me/v1"
    assert updated.strike_api_key == "secret-key"

    with pytest.raises(ValidationError):
        UpdateSettings.model_validate({"unknown_setting": True})


def test_update_settings_schema_does_not_include_env_names():
    schema = UpdateSettings.model_json_schema()

    assert "properties" in schema
    assert all("env_names" not in prop for prop in schema["properties"].values())
