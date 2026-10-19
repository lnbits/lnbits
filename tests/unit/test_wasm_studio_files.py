import json
import os
import sys
from unittest.mock import AsyncMock

import pytest

from lnbits.core.wasm_ext.studio_files import DraftFiles, source_digest
from lnbits.core.wasm_ext.studio_process import run_worker, worker_environment
from lnbits.core.wasm_ext.studio_service import mandatory_instructions


@pytest.mark.parametrize(
    "path",
    [
        "../data/history.json",
        "/escape.py",
        "src/../../escape.py",
        "src\\escape.py",
        ".env",
        "wasm/module.wasm",
        "Makefile",
        "src/componentize-py.toml",
    ],
)
def test_agent_rejects_paths_and_executable_build_configuration(tmp_path, path):
    draft = tmp_path / "ext"
    draft.mkdir()
    with pytest.raises(ValueError):
        DraftFiles(draft).write(path, "forbidden")
    assert not list(draft.iterdir())


def test_agent_rejects_symlinks_hardlinks_and_non_regular_files(tmp_path):
    draft = tmp_path / "ext"
    draft.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("private")
    linked = draft / "linked.py"
    linked.symlink_to(outside)
    with pytest.raises((OSError, ValueError)):
        DraftFiles(draft).read("linked.py")
    with pytest.raises(ValueError):
        DraftFiles(draft).write("linked.py", "changed")
    linked.unlink()
    os.link(outside, linked)
    with pytest.raises(ValueError):
        DraftFiles(draft).read("linked.py")
    linked.unlink()
    os.mkfifo(linked)
    with pytest.raises(ValueError):
        DraftFiles(draft).read("linked.py")
    assert outside.read_text() == "private"


def test_safe_file_edits_and_snapshot_identity(tmp_path):
    files = DraftFiles(tmp_path)
    files.write("src/app.py", "first\n")
    first = files.snapshot()
    files.write("src/app.py", "second\n")
    assert first["src/app.py"] == b"first\n"
    assert source_digest(first) != source_digest(files.snapshot())
    files.delete("src/app.py")
    assert files.snapshot() == {}


def test_mandatory_instructions_and_clean_worker_environment(tmp_path, monkeypatch):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    instructions = mandatory_instructions()
    for name in ("wasm-extensions.md", "wasm-extensions-studio.md"):
        assert (root / "docs" / name).read_text() in instructions
    assert (root / "docs/wasm-extensions-cli.md").read_text() not in instructions
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-builder")
    monkeypatch.setenv("LNBITS_DATABASE_URL", "must-not-reach-builder")
    environment = worker_environment(tmp_path)
    assert "must-not-reach-builder" not in json.dumps(environment)
    assert environment["HOME"].startswith(str(tmp_path))


@pytest.mark.anyio
async def test_worker_timeout_and_stop_kill_the_worker(tmp_path, mocker):
    mocker.patch("lnbits.core.wasm_ext.studio_process._check_memory", AsyncMock())
    with pytest.raises(ValueError, match="time limit"):
        await run_worker(
            [sys.executable, "-I", "-c", "while True: pass"], tmp_path, timeout=0
        )
    (tmp_path / "stop").touch()
    with pytest.raises(ValueError, match="Stopped"):
        await run_worker([sys.executable, "-I", "-c", "while True: pass"], tmp_path)
