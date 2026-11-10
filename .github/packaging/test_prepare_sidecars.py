"""Pinned release and integrity checks do not depend on live GitHub state."""

import hashlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import prepare_sidecars


class PrepareSidecarsTests(unittest.TestCase):
    def test_macos_prebuilds_keep_only_the_target_architecture(self):
        for arch in ("arm64", "x64"):
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as folder:
                modules = Path(folder) / "node_modules"
                variants = (
                    "darwin-arm64",
                    "darwin-x64",
                    "darwin-x64+arm64",
                    "ios-arm64",
                    "ios-x64-simulator",
                    "linux-arm64",
                    "win32-x64",
                )
                for package in ("bare-buffer", "nested/node_modules/bare-crypto"):
                    root = modules / package
                    root.mkdir(parents=True)
                    (root / "index.js").write_text("// shared runtime code")
                    for variant in variants:
                        binary = root / "prebuilds" / variant / "native.bare"
                        binary.parent.mkdir(parents=True)
                        binary.write_bytes(b"native prebuild")
                    (root / "prebuilds/README.md").write_text("license information")
                prepare_sidecars.prune_prebuilds(modules, "darwin", arch)
                for package in ("bare-buffer", "nested/node_modules/bare-crypto"):
                    root = modules / package
                    self.assertEqual(
                        {path.name for path in (root / "prebuilds").iterdir()},
                        {f"darwin-{arch}", "darwin-x64+arm64", "README.md"},
                    )
                    self.assertEqual(
                        (
                            root / "prebuilds" / f"darwin-{arch}" / "native.bare"
                        ).read_bytes(),
                        b"native prebuild",
                    )
                    self.assertTrue((root / "index.js").is_file())

    def test_other_platforms_keep_their_existing_prebuilds(self):
        for system in ("linux", "win"):
            with self.subTest(system=system), tempfile.TemporaryDirectory() as folder:
                modules = Path(folder) / "node_modules"
                binary = modules / "package/prebuilds/darwin-arm64/native.bare"
                binary.parent.mkdir(parents=True)
                binary.write_bytes(b"unchanged")
                prepare_sidecars.prune_prebuilds(modules, system, "x64")
                self.assertEqual(binary.read_bytes(), b"unchanged")

    def test_pinned_revision_and_checksum_are_used(self):
        pin = {"release": "v0.1.4", "revision": "a" * 40, "sha256": "archive-digest"}
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("prepare_sidecars.download") as download,
            patch("prepare_sidecars.unpack", return_value=Path(folder) / "source"),
            patch("builtins.print"),
        ):
            source = prepare_sidecars.download_spark(Path(folder), pin)
            self.assertEqual(source, Path(folder) / "source")
            download.assert_called_once_with(
                "https://api.github.com/repos/lnbits/spark_sidecar/tarball/"
                + pin["revision"],
                pin["sha256"],
                Path(folder) / "spark.tar.gz",
            )

    def test_missing_archive_fails_without_falling_back(self):
        pin = {"release": "v0.1.4", "revision": "a" * 40, "sha256": "archive-digest"}
        with (
            patch(
                "prepare_sidecars.download",
                side_effect=urllib.error.HTTPError(
                    "https://api.github.com", 404, "Not Found", {}, None
                ),
            ) as download,
            patch("prepare_sidecars.unpack") as unpack,
            patch("builtins.print"),
        ):
            with self.assertRaises(urllib.error.HTTPError):
                prepare_sidecars.download_spark(Path("unused"), pin)
            download.assert_called_once()
            unpack.assert_not_called()

    def test_download_records_digest_and_still_enforces_pinned_checksums(self):
        content = b"runtime archive"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            for digest in (None, expected, "incorrect"):
                with patch(
                    "prepare_sidecars.urllib.request.urlopen",
                    return_value=io.BytesIO(content),
                ):
                    if digest != expected:
                        with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                            prepare_sidecars.download(
                                "https://example.com/runtime",
                                digest,
                                Path(folder) / "archive",
                            )
                    else:
                        self.assertEqual(
                            prepare_sidecars.download(
                                "https://example.com/runtime",
                                digest,
                                Path(folder) / "archive",
                            ),
                            expected,
                        )
