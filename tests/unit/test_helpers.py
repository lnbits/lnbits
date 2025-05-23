import pytest

from lnbits.helpers import check_callback_url
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
