import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from problem1.local import resolve_tools


class LocalToolTests(unittest.TestCase):
    def test_explicit_paths_override_machine_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "tools.json"
            saved.write_text(json.dumps({"gem5": "/saved/gem5", "mcpat": "/saved/mcpat",
                                         "hotspot": "/saved/hotspot", "host": "another host"}))
            args = argparse.Namespace(gem5="/cli/gem5", mcpat=None, hotspot=None)
            with patch("problem1.local.TOOL_FILE", saved), patch.dict(
                "os.environ", {"GEM5_BINARY": "/env/gem5", "MCPAT_BINARY": "/env/mcpat"}, clear=True
            ):
                resolve_tools(args)
            self.assertEqual(vars(args), {"gem5": "/cli/gem5", "mcpat": "/env/mcpat",
                                          "hotspot": "/saved/hotspot"})

    def test_unregistered_machine_can_use_path(self):
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(gem5=None, mcpat=None, hotspot=None)
            with patch("problem1.local.TOOL_FILE", Path(directory) / "absent.json"), \
                 patch.dict("os.environ", {}, clear=True), \
                 patch("problem1.local.shutil.which", side_effect=lambda name: "/tools/" + name):
                resolve_tools(args)
            self.assertEqual(vars(args), {"gem5": "/tools/gem5.opt", "mcpat": "/tools/mcpat",
                                          "hotspot": "/tools/hotspot"})
