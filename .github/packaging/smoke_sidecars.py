"""Offline native runtime checks: versions, Spark authentication and owned shutdown."""

# ruff: noqa: S101, S603
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def check(resources):
    pins = json.loads((resources / "pins.json").read_text())
    node = resources / ("node.exe" if sys.platform == "win32" else "node")
    env = dict(os.environ)
    if sys.platform == "linux":
        env["LD_LIBRARY_PATH"] = os.pathsep.join(
            filter(None, (str(resources / "lib"), env.get("LD_LIBRARY_PATH")))
        )
    version = subprocess.check_output([str(node), "--version"], env=env, text=True)
    assert version.strip() == f"v{pins['node']['version']}"
    if sys.platform != "win32":
        version = subprocess.check_output(
            [str(resources / "phoenixd"), "--version"], env=env, text=True
        )
        assert f"phoenixd version {pins['phoenixd']['version']}-" in version
    with tempfile.TemporaryDirectory(prefix="lnbits-funding-smoke-") as folder:
        with socket.create_server(("127.0.0.1", 0)) as sock:
            port = sock.getsockname()[1]
        # No mnemonic means no wallet initialization or Lightning/Spark traffic.
        env.update(
            SPARK_MNEMONIC="",
            SPARK_SIDECAR_HOST="127.0.0.1",
            SPARK_SIDECAR_PORT=str(port),
            SPARK_SIDECAR_API_KEY="smoke-test",
            SPARK_ONCHAIN_ENABLED="false",
            SPARK_SIDECAR_STATE_PATH=str(Path(folder) / "state.json"),
        )
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(
                [str(node), str(resources / "supervisor.mjs"), "spark"],
                cwd=folder,
                env=env,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=log,
            )
            try:
                client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/health",
                    headers={"X-Api-Key": "smoke-test"},
                )
                deadline = time.monotonic() + 30
                while True:
                    assert process.poll() is None, "Spark runtime exited during startup"
                    try:
                        with client.open(request, timeout=1) as response:
                            assert json.load(response)["status"] == "ok"
                        break
                    except urllib.error.URLError:
                        assert time.monotonic() < deadline, "Spark startup timed out"
                        time.sleep(0.1)
                try:
                    client.open(f"http://127.0.0.1:{port}/health", timeout=1)
                except urllib.error.HTTPError as exc:
                    assert exc.code == 401
                else:
                    raise AssertionError("Spark accepted a request without credentials")
                process.stdin.close()
                assert process.wait(timeout=20) == 0
                with socket.socket() as probe:
                    assert probe.connect_ex(("127.0.0.1", port)) != 0
            except BaseException:
                log.seek(0)
                print(log.read().decode(errors="replace"), file=sys.stderr)
                raise
            finally:
                if process.poll() is None:
                    process.stdin.close()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    print("Bundled funding runtimes passed offline smoke checks")


if __name__ == "__main__":
    source = Path(sys.argv[1]).resolve()
    if source.is_dir():
        check(source)
    else:
        # Exercise the files actually shipped inside Linux/Windows onefile builds.
        from PyInstaller.archive.readers import CArchiveReader

        archive = CArchiveReader(str(source))
        with tempfile.TemporaryDirectory(prefix="lnbits-bundled-runtimes-") as folder:
            for name, entry in archive.toc.items():
                path = Path(name.replace("\\", "/"))
                if path.parts[0] != "sidecars" or ".." in path.parts:
                    continue
                destination = Path(folder) / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                content = archive.extract(name)
                if entry[-1] == "n":
                    destination.symlink_to(content.rstrip(b"\0").decode())
                else:
                    destination.write_bytes(content)
                    if entry[-1] == "b":
                        destination.chmod(0o755)
            check(Path(folder) / "sidecars")
