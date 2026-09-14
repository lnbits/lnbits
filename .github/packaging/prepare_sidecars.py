"""Prepare bundled runtimes at build time; never download at application startup."""

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def download(url, digest, destination):
    request = urllib.request.Request(  # noqa: S310 - HTTPS runtime downloads
        url, headers={"User-Agent": "LNbits-packaging"}
    )
    checksum = hashlib.sha256()
    with (
        urllib.request.urlopen(request, timeout=60) as response,  # noqa: S310
        destination.open("wb") as stream,
    ):
        while block := response.read(1024 * 1024):
            checksum.update(block)
            stream.write(block)
    if checksum.hexdigest() != digest:
        raise RuntimeError(f"Checksum mismatch for {destination.name}")
    return checksum.hexdigest()


def download_spark(staging, pin):
    tag = pin["release"]
    revision = pin["revision"]
    print(f"Spark sidecar release: {tag} ({revision})", flush=True)
    archive = staging / "spark.tar.gz"
    download(
        f"https://api.github.com/repos/lnbits/spark_sidecar/tarball/{revision}",
        pin["sha256"],
        archive,
    )
    extracted = staging / "spark"
    extracted.mkdir()
    return unpack(archive, extracted)


def unpack(archive, destination):
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as contents:
            contents.extractall(destination)  # noqa: S202 - verified runtime archive
    else:
        with tarfile.open(archive) as contents:
            contents.extractall(destination, filter="data")
    return next(destination.iterdir())


def main():
    here = Path(__file__).resolve().parent
    pins = json.loads((here / "sidecars/pins.json").read_text())
    system = {"linux": "linux", "darwin": "darwin", "win32": "win"}[sys.platform]
    arch = {"x86_64": "x64", "AMD64": "x64", "arm64": "arm64", "aarch64": "arm64"}[
        platform.machine()
    ]
    target = f"{system}-{arch}"
    output = Path("build/sidecars").resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="lnbits-sidecars-") as folder:
        staging = Path(folder)
        version = pins["node"]["version"]
        suffix = (
            "zip" if system == "win" else "tar.gz" if system == "darwin" else "tar.xz"
        )
        filename = f"node-v{version}-{target}.{suffix}"
        archive = staging / filename
        download(
            f"https://nodejs.org/dist/v{version}/{filename}",
            pins["node"]["sha256"][target],
            archive,
        )
        extracted = staging / "node"
        extracted.mkdir()
        node = unpack(archive, extracted)
        executable = "node.exe" if system == "win" else "node"
        shutil.copy2(
            node / ("node.exe" if system == "win" else "bin/node"), output / executable
        )
        shutil.copy2(node / "LICENSE", output / "NODE-LICENSE.txt")

        source = download_spark(staging, pins["spark"])
        spark = output / "spark"
        spark.mkdir()
        for filename in (
            "package.json",
            "package-lock.json",
            "README.md",
        ):
            shutil.copy2(source / filename, spark / filename)
        for module in source.glob("*.mjs"):
            shutil.copy2(module, spark / module.name)
        npm = shutil.which("npm.cmd" if system == "win" else "npm")
        if not npm:
            raise RuntimeError("npm is required to prepare the Spark sidecar")
        subprocess.run(  # noqa: S603
            [npm, "ci", "--omit=dev", "--ignore-scripts"], cwd=spark, check=True
        )
        subprocess.run(  # noqa: S603
            [npm, "audit", "--omit=dev", "--audit-level=high"], cwd=spark, check=True
        )
        # The SDK also publishes mobile native libraries; Node never loads them.
        sdk = spark / "node_modules/@buildonspark/spark-sdk"
        for directory in ("android", "ios"):
            shutil.rmtree(sdk / directory, ignore_errors=True)
        shutil.rmtree(spark / "node_modules/.bin", ignore_errors=True)

        if system != "win":
            version = pins["phoenixd"]["version"]
            target = f"{'macos' if system == 'darwin' else system}-{arch}"
            filename = f"phoenixd-{version}-{target}.zip"
            archive = staging / filename
            download(
                f"https://github.com/ACINQ/phoenixd/releases/download/v{version}/{filename}",
                pins["phoenixd"]["sha256"][target],
                archive,
            )
            extracted = staging / "phoenixd"
            extracted.mkdir()
            source = unpack(archive, extracted)
            shutil.copy2(source / "phoenixd", output / "phoenixd")
            (output / "phoenixd").chmod(0o755)
            shutil.copy2(
                here / "sidecars/PHOENIXD-LICENSE.txt", output / "PHOENIXD-LICENSE.txt"
            )
        shutil.copy2(here / "sidecars/supervisor.mjs", output / "supervisor.mjs")
        (output / "pins.json").write_text(json.dumps(pins, indent=2) + "\n")
    print(f"Prepared bundled funding sources in {output}")


if __name__ == "__main__":
    main()
