import json
import re

import pytest
from starlette.requests import Request

from lnbits.helpers import template_renderer


@pytest.mark.parametrize("template", ["base.html", "print.html"])
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
def test_base_template_preserves_rendered_route(path, template):
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

    response = template_renderer().TemplateResponse(request, template, {"public": True})
    html = bytes(response.body).decode()
    route = re.search(r"const RENDERED_ROUTE = (.+)\n", html)

    assert route is not None
    assert json.loads(route[1]) == "/" + path.strip("/")
    assert "<" not in route[1]
    if template == "base.html":
        assert 'v-if="$route.path.startsWith(RENDERED_ROUTE)"' in html
