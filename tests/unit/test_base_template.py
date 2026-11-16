import json
import re

import pytest
from starlette.requests import Request

from lnbits.helpers import template_renderer


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/wallet/example",
        "/extension/",
        "/wallet/quotes'\"\\&<>",
        "/wallet/</script><script>example</script>",
    ],
)
def test_base_template_preserves_rendered_route(path):
    request = Request(
        {
            "type": "http",
            "path": path,
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )

    response = template_renderer().TemplateResponse(
        request, "base.html", {"public": True}
    )
    html = bytes(response.body).decode()
    route = re.search(r"const RENDERED_ROUTE = (.+)\n", html)

    assert route is not None
    assert json.loads(route[1]) == "/" + path.strip("/")
    assert "<" not in route[1]
    assert 'v-if="$route.path.startsWith(RENDERED_ROUTE)"' in html
