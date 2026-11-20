import os

import pytest
from starlette.requests import Request

from lnbits.helpers import _cached_template_renderer, template_renderer


@pytest.fixture(autouse=True)
def clear_template_cache():
    _cached_template_renderer.cache_clear()
    yield
    _cached_template_renderer.cache_clear()


@pytest.fixture
def template_request():
    return Request(
        {
            "type": "http",
            "path": "/",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )


def test_templates_compile_once_for_repeated_renders(template_request, mocker):
    renderer = template_renderer()
    compile_template = mocker.spy(renderer.env, "compile")
    first = renderer.TemplateResponse(template_request, "error.html", {})
    compiled = compile_template.call_count
    second = template_renderer().TemplateResponse(template_request, "error.html", {})

    assert compiled > 0
    assert compile_template.call_count == compiled
    assert first.body == second.body


def test_cached_templates_refresh_settings_and_asset_mode(
    template_request, settings, tmp_path
):
    (tmp_path / "probe.html").write_text(
        "{{ SITE_TITLE }}|{{ SETTINGS.siteTitle }}|"
        "{{ LNBITS_DENOMINATION }}|{{ INCLUDED_JS|join(',') }}"
    )
    settings.lnbits_site_title = "Before"
    settings.bundle_assets = True
    first = template_renderer([tmp_path]).TemplateResponse(
        template_request, "probe.html", {}
    )
    assert b"Before|Before|" in first.body
    assert b"bundle.min.js" in first.body

    settings.lnbits_site_title = "After"
    settings.lnbits_denomination = "bits"
    settings.bundle_assets = False
    second = template_renderer([tmp_path]).TemplateResponse(
        template_request, "probe.html", {}
    )
    assert b"After|After|bits|" in second.body
    assert b"bundle.min.js" not in second.body


def test_template_folder_list_is_not_mutated_or_shared(template_request, tmp_path):
    folders = [tmp_path / "one", tmp_path / "two"]
    for folder in folders:
        folder.mkdir()
        (folder / "probe.html").write_text(folder.name)
    first_order = list(folders)
    first = template_renderer(folders).TemplateResponse(
        template_request, "probe.html", {}
    )
    second = template_renderer(list(reversed(folders))).TemplateResponse(
        template_request, "probe.html", {}
    )
    assert folders == first_order
    assert first.body == b"one"
    assert second.body == b"two"


def test_cached_template_reloads_changed_file(template_request, tmp_path):
    path = tmp_path / "probe.html"
    path.write_text("Before")
    first = template_renderer([tmp_path]).TemplateResponse(
        template_request, "probe.html", {}
    )
    mtime = path.stat().st_mtime
    path.write_text("After")
    os.utime(path, (mtime + 2, mtime + 2))
    second = template_renderer([tmp_path]).TemplateResponse(
        template_request, "probe.html", {}
    )
    assert first.body == b"Before"
    assert second.body == b"After"


def test_cached_templates_do_not_reuse_request_context(template_request, tmp_path):
    (tmp_path / "probe.html").write_text("{{ user|default('anonymous') }}")
    first = template_renderer([tmp_path]).TemplateResponse(
        template_request, "probe.html", {"user": "first-user"}
    )
    second = template_renderer([tmp_path]).TemplateResponse(
        template_request, "probe.html", {}
    )
    assert first.body == b"first-user"
    assert second.body == b"anonymous"
