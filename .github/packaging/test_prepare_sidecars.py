"""Release resolution and integrity checks do not depend on live GitHub state."""

import hashlib
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import prepare_sidecars


class PrepareSidecarsTests(unittest.TestCase):
    def test_latest_release_is_resolved_to_a_commit_and_recorded(self):
        revision = "a" * 40
        with (
            tempfile.TemporaryDirectory() as folder,
            patch(
                "prepare_sidecars.github_json",
                side_effect=[{"tag_name": "v1.2.3"}, {"sha": revision}],
            ) as github,
            patch(
                "prepare_sidecars.download", return_value="archive-digest"
            ) as download,
            patch("prepare_sidecars.unpack", return_value=Path(folder) / "source"),
            patch("builtins.print"),
        ):
            source, metadata = prepare_sidecars.download_spark(Path(folder))
            self.assertEqual(source, Path(folder) / "source")
            self.assertEqual(
                [call.args[0] for call in github.call_args_list],
                ["releases/latest", "commits/v1.2.3"],
            )
            self.assertTrue(download.call_args.args[0].endswith("/tarball/" + revision))
            self.assertEqual(
                metadata,
                {"release": "v1.2.3", "revision": revision, "sha256": "archive-digest"},
            )

    def test_missing_release_fails_without_downloading_a_branch(self):
        with (
            patch(
                "prepare_sidecars.github_json",
                side_effect=urllib.error.HTTPError(
                    "https://api.github.com", 404, "Not Found", {}, None
                ),
            ),
            patch("prepare_sidecars.download") as download,
        ):
            with self.assertRaises(urllib.error.HTTPError):
                prepare_sidecars.download_spark(Path("unused"))
            download.assert_not_called()

    def test_download_records_digest_and_still_enforces_pinned_checksums(self):
        content = b"runtime archive"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            for digest in (None, expected, "incorrect"):
                with patch(
                    "prepare_sidecars.urllib.request.urlopen",
                    return_value=io.BytesIO(content),
                ):
                    if digest == "incorrect":
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
