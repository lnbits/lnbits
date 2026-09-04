import pytest
from starlette.requests import Request

from lnbits.helpers import template_renderer


@pytest.mark.parametrize("bundle_assets", [True, False])
def test_homepage_renders_node_template_with_client_bindings(settings, bundle_assets):
    settings.bundle_assets = bundle_assets
    request = Request(
        {
            "type": "http",
            "path": "/",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )

    response = template_renderer().TemplateResponse(
        request, "base.html", {"public": True}
    )

    assert response.status_code == 200
    html = response.body.decode()
    assert 'id="page-node"' in html
    # Jinja must leave these values for Vue to evaluate in the browser.
    assert "phoenixd.version ||" in html
    assert "phoenixd.blockheight ??" in html
    assert 'v-text="phoenixd.fee_credit_sat"' in html
