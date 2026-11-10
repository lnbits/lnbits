from html.parser import HTMLParser
from http import HTTPStatus

import pytest
from fastapi import FastAPI, HTTPException, Request

from lnbits.exceptions import render_html_error
from lnbits.middleware import InstalledExtensionMiddleware


class ErrorElementParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attributes = None

    def handle_starttag(self, tag, attrs):
        if tag == "lnbits-error" and self.attributes is None:
            self.attributes = dict(attrs)


@pytest.fixture
def browser_request():
    return Request(
        {
            "type": "http",
            "path": "/lnurlwallet",
            "headers": [(b"accept", b"text/html")],
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )


@pytest.mark.parametrize(
    "message",
    [
        '"><script>alert(1)</script>',
        '" onmouseover="alert(1)',
        "Quotes \" ' & angle brackets < >",
        "&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;",
    ],
)
@pytest.mark.parametrize("http_error", [True, False])
def test_error_template_preserves_message_as_attribute(
    browser_request, message, http_error
):
    exc = (
        HTTPException(status_code=400, detail=message)
        if http_error
        else ValueError(message)
    )

    response = render_html_error(browser_request, exc)

    expected_status_code = 400 if http_error else 500
    assert response is not None
    assert response.status_code == expected_status_code
    parser = ErrorElementParser()
    parser.feed(bytes(response.body).decode())
    assert parser.attributes == {"code": str(expected_status_code), "message": message}


def test_disabled_extension_error_escapes_message(browser_request):
    message = "Extension '\"><script>alert(1)</script>' disabled"
    middleware = InstalledExtensionMiddleware(app=FastAPI())

    response = middleware._response_by_accepted_type(
        browser_request.scope,
        browser_request.scope["headers"],
        message,
        HTTPStatus.NOT_FOUND,
    )

    assert response.status_code == 404
    parser = ErrorElementParser()
    parser.feed(bytes(response.body).decode())
    assert parser.attributes == {
        "code": str(HTTPStatus.NOT_FOUND),
        "message": message,
    }
