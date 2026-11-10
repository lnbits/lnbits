"""Catch Node startup failures before starting any bundled funding service."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import smoke_sidecars


class SidecarSmokeTests(unittest.TestCase):
    def test_node_initialization_failure_stops_before_starting_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            resources = Path(directory)
            (resources / "pins.json").write_text(
                json.dumps({"node": {"version": "24.21.0"}})
            )
            for platform, executable in (("darwin", "node"), ("win32", "node.exe")):
                with (
                    self.subTest(platform=platform),
                    patch("smoke_sidecars.sys.platform", platform),
                    patch.dict(os.environ, {"NODE_OPTIONS": "--jitless"}),
                    patch(
                        "smoke_sidecars.subprocess.check_output",
                        side_effect=subprocess.CalledProcessError(-5, [executable]),
                    ) as probe,
                    patch("smoke_sidecars.subprocess.Popen") as start,
                ):
                    with self.assertRaises(subprocess.CalledProcessError):
                        smoke_sidecars.check(resources)
                    probe.assert_called_once()
                    command = probe.call_args.args[0]
                    self.assertEqual(
                        command[:2], [str(resources / executable), "--eval"]
                    )
                    self.assertNotIn("NODE_OPTIONS", probe.call_args.kwargs["env"])
                    self.assertEqual(probe.call_args.kwargs["timeout"], 30)
                    start.assert_not_called()
