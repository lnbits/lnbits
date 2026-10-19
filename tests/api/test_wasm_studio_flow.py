import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from wasmtime import wat2wasm

from lnbits.core.crud.extensions import (
    delete_installed_extension,
    get_installed_extension,
)
from lnbits.core.wasm_ext import studio_service
from lnbits.core.wasm_ext.studio_files import DraftFiles
from lnbits.settings import WasmStudioModel


@pytest.fixture
async def studio_flow(app, tmp_path, settings, mocker, superuser_token, http_client):
    mocker.patch.object(settings, "lnbits_data_folder", str(tmp_path))
    mocker.patch.object(
        settings, "lnbits_wasm_extensions_path", str(tmp_path / "installed")
    )
    mocker.patch.object(settings, "lnbits_extensions_deactivate_all", False)
    mocker.patch.object(
        settings,
        "lnbits_wasm_studio_models",
        [
            WasmStudioModel(
                name="Test", provider="openai", model="test", api_key="private-api-key"
            )
        ],
    )
    application = mocker.spy(studio_service, "initialize_studio")
    mocker.patch.object(
        studio_service, "ensure_worker", return_value=Path("/trusted/python")
    )

    async def worker(command, data, *, payload, handle, **kwargs):
        if command[-1].endswith("agent.py"):
            assert "private-api-key" == payload["model"]["api_key"]
            assert "# WASM Extension Studio" in payload["instructions"]
            await handle({"text": "Updating the draft.\n"})
            denied = await handle(
                {"tool": "write", "path": "../data/history.json", "content": "escape"}
            )
            assert denied and "error" in denied
            await handle(
                {
                    "tool": "write",
                    "path": "ui/index.html",
                    "content": "<html>Draft change</html>",
                }
            )
            await handle({"history": []})
            return
        (Path(payload["scratch"]) / "module.wasm").write_bytes(_component())
        await handle({"log": "Compiled"})

    mocker.patch.object(studio_service, "run_worker", side_effect=worker)
    ext_id = "studio_" + uuid4().hex[:8]
    url = "/api/v1/extension/studio/" + ext_id
    headers = {"Authorization": "Bearer " + superuser_token}
    response = await http_client.post(
        url,
        headers=headers,
        json={"new": True, "name": "Studio test", "description": "Test"},
    )
    assert response.status_code == 200, response.text
    yield ext_id, url, headers, tmp_path
    await delete_installed_extension(ext_id=ext_id)
    if application.call_args:
        instance = application.call_args.args[0]
        studio_service._remove_routes(instance, ext_id)
        studio_service._remove_routes(instance, response.json()["id"])


@pytest.mark.anyio
async def test_wasm_studio_chat_build_undo_and_exact_deployment(
    studio_flow, http_client, settings
):
    ext_id, url, headers, _ = studio_flow
    models = await http_client.get(
        "/api/v1/extension/studio/models/configured", headers=headers
    )
    assert "private-api-key" not in models.text
    assert "api_key" not in models.text
    response = await http_client.post(
        url + "/chat",
        headers=headers,
        json={"prompt": "Change the page", "model": models.json()[0]["id"]},
    )
    assert response.status_code == 202
    state = await _finished(http_client, url, headers)
    assert any(
        message["content"] == "Editing ui/index.html" for message in state["messages"]
    )
    workspace = studio_service.studio_workspace(ext_id, settings.super_user)
    assert (workspace / "ext/ui/index.html").read_text() == "<html>Draft change</html>"
    assert not (workspace / "data/history.json").read_text() == "escape"
    review = (await http_client.get(url + "/review", headers=headers)).json()
    denied = await http_client.post(
        url + "/build", headers=headers, json={"digest": review["digest"]}
    )
    assert denied.status_code == 400
    await http_client.post(
        url + "/build",
        headers=headers,
        json={"digest": review["digest"], "approved": True},
    )
    state = await _finished(http_client, url, headers)
    assert state["build"], state["messages"]
    assert (
        await http_client.get("/api/v1/ext/" + state["id"] + "/hello", headers=headers)
    ).json() == {"ok": True}
    build = state["build"]
    # An edit after Build must not alter either preview or the deployed source.
    DraftFiles(workspace / "ext").write(
        "ui/index.html", "<html>Later unbuilt edit</html>"
    )
    assert (
        workspace / "data" / build["path"] / "ui/index.html"
    ).read_text() == "<html>Draft change</html>"
    await http_client.post(
        url + "/deploy",
        headers=headers,
        json={"digest": build["digest"], "build_id": build["id"], "approved": True},
    )
    state = await _finished(http_client, url, headers)
    assert state.get("deployed_build") == build["id"], state["messages"]
    installed = await get_installed_extension(ext_id)
    assert installed
    assert (
        installed.wasm_ext_dir / "ui/index.html"
    ).read_text() == "<html>Draft change</html>"
    assert not (installed.wasm_ext_dir / "data").exists()
    await http_client.post(
        url + "/undo",
        headers=headers,
        json={"checkpoint": state["checkpoints"][0]["id"]},
    )
    state = await _finished(http_client, url, headers)
    assert "ready to build" in (workspace / "ext/ui/index.html").read_text()
    assert state["build"]["id"] == build["id"]


@pytest.mark.anyio
async def test_wasm_studio_rejects_stale_build_approval_and_parallel_jobs(
    studio_flow, http_client, settings, mocker
):
    ext_id, url, headers, _ = studio_flow
    review = (await http_client.get(url + "/review", headers=headers)).json()
    workspace = studio_service.studio_workspace(ext_id, settings.super_user)
    DraftFiles(workspace / "ext").write("ui/index.html", "changed")
    await http_client.post(
        url + "/build",
        headers=headers,
        json={"digest": review["digest"], "approved": True},
    )
    state = await _finished(http_client, url, headers)
    assert not state["build"]
    assert "changed after review" in state["messages"][-1]["content"]
    with studio_service.studio_lock(workspace):
        response = await http_client.post(
            url + "/build",
            headers=headers,
            json={"digest": review["digest"], "approved": True},
        )
        assert response.status_code == 409


@pytest.mark.anyio
async def test_wasm_studio_operations_are_admin_only(
    studio_flow, http_client, user_headers_from
):
    _, url, _, _ = studio_flow
    http_client.cookies.clear()
    for headers, expected in (({}, 401), (user_headers_from, 403)):
        for method, suffix, data in (
            ("GET", "", None),
            ("GET", "/review", None),
            ("POST", "/stop", None),
            ("POST", "/chat", {"prompt": "hello", "model": "a" * 64}),
        ):
            response = await http_client.request(
                method, url + suffix, headers=headers, json=data
            )
            assert response.status_code == expected


@pytest.mark.anyio
async def test_wasm_studio_failed_build_keeps_preview_and_conflicting_deploy_is_refused(
    studio_flow, http_client, settings, mocker
):
    ext_id, url, headers, _ = studio_flow
    review = (await http_client.get(url + "/review", headers=headers)).json()
    await http_client.post(
        url + "/build",
        headers=headers,
        json={"digest": review["digest"], "approved": True},
    )
    built = await _finished(http_client, url, headers)
    assert built["build"], built["messages"]
    workspace = studio_service.studio_workspace(ext_id, settings.super_user)
    DraftFiles(workspace / "ext").write("ui/index.html", "new source")
    mocker.patch.object(
        studio_service, "run_worker", side_effect=ValueError("Compilation rejected")
    )
    review = (await http_client.get(url + "/review", headers=headers)).json()
    await http_client.post(
        url + "/build",
        headers=headers,
        json={"digest": review["digest"], "approved": True},
    )
    failed = await _finished(http_client, url, headers)
    assert failed["build"] == built["build"]
    assert (
        await http_client.get("/api/v1/ext/" + built["id"] + "/hello", headers=headers)
    ).status_code == 200
    approval = {
        "digest": built["build"]["digest"],
        "build_id": built["build"]["id"],
        "approved": True,
    }
    await http_client.post(url + "/deploy", headers=headers, json=approval)
    deployed = await _finished(http_client, url, headers)
    assert deployed.get("deployed_build") == built["build"]["id"]
    target = settings.wasm_extensions_dir / ext_id / "ui/index.html"
    target.write_text("New production version")
    review = (await http_client.get(url + "/review?built=true", headers=headers)).json()
    assert review["production_changed"]
    await http_client.post(url + "/deploy", headers=headers, json=approval)
    refused = await _finished(http_client, url, headers)
    assert "Production changed" in refused["messages"][-1]["content"]
    assert target.read_text() == "New production version"


async def _finished(client, url, headers):
    for _ in range(200):
        response = await client.get(url, headers=headers)
        assert response.status_code == 200
        state = response.json()
        if not state["busy"]:
            return state
        await asyncio.sleep(0.01)
    pytest.fail("Studio operation did not finish")


def _component():
    return wat2wasm(r"""(component
      (core module $m
        (memory (export "memory") 1)
        (data (i32.const 0) "\08\00\00\00\0b\00\00\00{\22ok\22:true}")
        (func (export "realloc") (param i32 i32 i32 i32) (result i32) i32.const 1024)
        (func (export "hello") (param i32 i32) (result i32) i32.const 0))
      (core instance $i (instantiate $m))
      (func (export "hello") (param "input" string) (result string)
        (canon lift (core func $i "hello") (memory $i "memory")
          (realloc (func $i "realloc")))))""")
