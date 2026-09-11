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
