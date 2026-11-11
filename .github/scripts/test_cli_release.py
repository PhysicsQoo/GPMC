#!/usr/bin/env python3
"""Offline archive contract tests for the minimal CLI distribution."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from types import SimpleNamespace

MODULE_FILE = Path(__file__).with_name("cli-release.py")
spec = importlib.util.spec_from_file_location("cli_release", MODULE_FILE)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class CliArchiveTest(unittest.TestCase):
    def build(self, folder: Path) -> SimpleNamespace:
        binary = folder / "gpmc"
        # Fake but correctly identified x86_64 ELF header. The native
        # scientific tests run separately on actual compiled executables.
        binary.write_bytes(b"\x7fELF\x02\x01" + bytes(12) + struct.pack("<H", 62))
        deps = folder / "deps"
        deps.write_text("libgmp.so.10, libmpfr.so.4", encoding="ascii")
        return SimpleNamespace(
            version="candidate", target="linux-almalinux8-x86_64",
            source_sha="a" * 40, binary=str(binary),
            dependencies=str(deps), output_dir=str(folder / "out")
        )

    def test_package_verifies_and_excludes_shared_libraries(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.build(Path(d))
            cli.package(args)
            name = cli.archive_name(args.version, args.target)
            import tarfile
            with tarfile.open(Path(args.output_dir) / name, "r:gz") as tar:
                self.assertEqual(set(tar.getnames()), cli.expected_members(args.target))
                self.assertFalse(any(name.startswith("libs/") for name in tar.getnames()))

    def test_checksum_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.build(Path(d))
            cli.package(args)
            archive = Path(args.output_dir) / cli.archive_name(args.version, args.target)
            archive.write_bytes(archive.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                cli.verify(args)

    def test_wrong_source_sha_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.build(Path(d))
            cli.package(args)
            args.source_sha = "b" * 40
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                cli.verify(args)

    def test_bad_version_or_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            cli.archive_name("v1.0.0-rc.1", cli.MACHINES[0])
        with self.assertRaises(ValueError):
            cli.archive_name("v1.0.0", "windows-unknown")


if __name__ == "__main__":
    unittest.main()
