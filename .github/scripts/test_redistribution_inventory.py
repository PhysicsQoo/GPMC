#!/usr/bin/env python3
"""Offline negative-contract tests for the release redistribution inventory."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("redistribution-inventory.py")
spec = importlib.util.spec_from_file_location("gpmc_redistribution_inventory", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
WIN_AUDIT = Path(__file__).with_name("windows-runtime-audit.py")
win_spec = importlib.util.spec_from_file_location("gpmc_windows_runtime_audit", WIN_AUDIT)
win_module = importlib.util.module_from_spec(win_spec)
win_spec.loader.exec_module(win_module)
SOURCE = "a" * 40
TARGET = "linux-almalinux8-x86_64"


def make_archive(path: Path, *, altered: bool = False, traversal: bool = False,
                 duplicate: bool = False, omit_notice: bool = False,
                 missing_admission: bool = False) -> None:
    binary = b"example-gpmc"
    libs = {f"libs/{name}": name.encode() for name in
            ("libgmp.so.10", "libgmpxx.so.4", "libmpfr.so.4")}
    hashed = {name.split("/", 1)[1]: hashlib.sha256(data).hexdigest()
              for name, data in libs.items()}
    abi = json.dumps({"target": TARGET, "binary_sha256": module.digest(binary),
                      "distribution_admitted": False}).encode()
    prov = json.dumps({
        "project": "PhysicsQoo/GPMC",
        "source_commit": SOURCE,
        "platform": TARGET,
        "release_version": "candidate",
        "executable_sha256": module.digest(binary),
        "abi_report_sha256": module.digest(abi),
        "bundled_library_sha256": hashed,
        "admission": "native-build-and-science-smoke-only",
        "distribution_admitted": False,
    }).encode()
    files = {
        "gpmc": binary, "abi-report.json": abi, "provenance.json": prov,
        "dependencies.txt": b"gmp-6.3\nmpfr-4.2\n",
        **libs,
        **{n: b"placeholder notice" for n in module.NOTICE_PATHS},
    }
    if missing_admission:
        # Rebuild the otherwise valid provenance without the admission marker.
        updated = json.loads(files["provenance.json"])
        del updated["distribution_admitted"]
        files["provenance.json"] = json.dumps(updated).encode()
    if omit_notice:
        del files[sorted(module.NOTICE_PATHS)[0]]
    if altered:
        files["libs/libgmp.so.10"] = b"tampered-library"
    if traversal:
        files["../untrusted"] = b"bad"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            item = tarfile.TarInfo(name)
            item.size = len(data)
            tar.addfile(item, io.BytesIO(data))
        if duplicate:
            name = "gmp-duplicate"
            item = tarfile.TarInfo("gmp")
            item.size = 0
            tar.addfile(item, io.BytesIO(b""))
            tar.addfile(item, io.BytesIO(b""))


class RedistributionInventoryContract(unittest.TestCase):
    def test_unreviewed_binary_yields_inventory_not_license_pass(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive)
            record = module.inventory(archive, TARGET, SOURCE)
            self.assertFalse(record["distribution_admitted"])
            self.assertFalse(record["all_corresponding_sources_delivered"])
            self.assertEqual(3, len(record["bundled_libraries"]))
            self.assertTrue(all(x["corresponding_source_sha256"] is None
                                for x in record["bundled_libraries"]))

    def test_tampered_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive, altered=True)
            with self.assertRaisesRegex(ValueError, "hashes"):
                module.inventory(archive, TARGET, SOURCE)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive, traversal=True)
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                module.inventory(archive, TARGET, SOURCE)

    def test_duplicate_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive, duplicate=True)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                module.inventory(archive, TARGET, SOURCE)

    def test_missing_notice_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive, omit_notice=True)
            with self.assertRaisesRegex(ValueError, "notices"):
                module.inventory(archive, TARGET, SOURCE)

    def test_installed_dll_owner_is_not_an_approved_source_certificate(self):
        def completed(out):
            return type("Result", (), {"stdout": out})()
        with mock.patch.object(win_module.subprocess, "run", side_effect=[
            completed("mingw-w64-ucrt-x86_64-gmp\n"),
            completed("mingw-w64-ucrt-x86_64-gmp 6.3.0-2\n"),
        ]):
            owner = win_module.installed_package_owner(Path("/ucrt64/bin/libgmp-10.dll"))
        self.assertEqual(owner["package"], "mingw-w64-ucrt-x86_64-gmp")
        self.assertEqual(owner["version"], "6.3.0-2")
        self.assertIn("not-corresponding-source", owner["evidence"])

    def test_tag_draft_inventory_checks_from_checkout_root(self):
        workflow = (SCRIPT.parent.parent / "workflows" /
                    "native-release.yml").read_text(encoding="utf-8")
        prepare = (workflow.split("  prepare-draft:", 1)[1]
                   .split("  create-draft:", 1)[0])
        self.assertIn('archive="dist/gpmc-$RELEASE_VERSION-$target.tar.gz"', prepare)
        self.assertIn("python3 .github/scripts/redistribution-inventory.py", prepare)
        self.assertNotIn("          cd dist\n          for target", prepare)
        self.assertIn("sha256sum gpmc-*.tar.gz", prepare)
        release = workflow.split("  create-draft:", 1)[1]
        self.assertIn("--draft --prerelease --latest=false", release)
        self.assertIn("contents: write", release)

    def test_pr_validates_release_manifest_without_creating_draft(self):
        workflow = (SCRIPT.parent.parent / "workflows" /
                    "native-release.yml").read_text(encoding="utf-8")
        prepare = (workflow.split("  prepare-draft:", 1)[1]
                   .split("  create-draft:", 1)[0])
        self.assertNotIn(
            "if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')\n    needs:",
            prepare,
        )
        self.assertIn("RELEASE_ASSET_MANIFEST_PREFLIGHT_PASS", prepare)
        self.assertIn(
            "RELEASE_VERSION: ${{ github.ref_type == 'tag' && github.ref_name || 'candidate' }}",
            prepare,
        )
        self.assertIn(
            "SOURCE_SHA: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}",
            prepare,
        )
        release = workflow.split("  create-draft:", 1)[1]
        self.assertNotIn("contents: write", prepare)
        self.assertNotIn("gh release create", prepare)
        self.assertIn("if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')", release)
        self.assertIn("needs: [prepare-draft]", release)
        self.assertIn("contents: write", release)
        self.assertIn("gh release create", release)

    def test_windows_release_source_tracks_checkout_head(self):
        # GITHUB_SHA on a pull_request job is GitHub's synthetic merge SHA.
        # Producer archives must reference the pinned checkout identity.
        workflow = (SCRIPT.parent.parent / "workflows" /
                    "native-release.yml").read_text(encoding="utf-8")
        start = workflow.index("      - name: Build, audit DLL closure and package Windows candidate")
        stop = workflow.index("      - name: Set up independent native Windows Python", start)
        windows = workflow[start:stop]
        self.assertIn('revision="$(cat source-revision.txt)"', windows)
        self.assertNotIn('revision="$GITHUB_SHA"', windows)
        self.assertEqual(4, workflow.count(
            "ref: ${{ github.event_name == 'pull_request' && "
            "github.event.pull_request.head.sha || github.sha }}"))

    def test_nonexact_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive)
            with self.assertRaisesRegex(ValueError, "non-exact"):
                module.inventory(archive, TARGET, SOURCE[:12])

    def test_release_inventory_requires_explicit_false_admission(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive)
            self.assertIs(module.inventory(archive, TARGET, SOURCE)["distribution_admitted"], False)
            make_archive(archive, missing_admission=True)
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                module.inventory(archive, TARGET, SOURCE)

    def test_native_packager_explicitly_marks_nonadmission(self):
        producer = (SCRIPT.parent / "native-release-bundle.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"distribution_admitted": False,', producer)
        self.assertGreaterEqual(producer.count('"distribution_admitted": False,'), 2)
        self.assertIn('"admission": "native-build-and-science-smoke-only",', producer)

    def test_build_workflow_pins_pr_checkout_and_provenance(self):
        workflow = (SCRIPT.parent.parent / "workflows" /
                    "build-cross-platform.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)
        self.assertIn('tested_checkout_sha=%s', workflow)
        self.assertIn('$(cat build/source-revision.txt)', workflow)
        self.assertNotIn('tested_checkout_sha=%s\\n\' "$GITHUB_SHA"', workflow)

    def test_never_issues_distribution_approval(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive)
            record = module.inventory(archive, TARGET, SOURCE)
            self.assertIs(record["distribution_admitted"], False)
            self.assertIs(record["macos_developer_id_and_notarization_verified"], False)
            self.assertFalse(record["all_runtime_licenses_reviewed"])

    def test_mismatched_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d) / "candidate.tar.gz"
            make_archive(archive)
            with self.assertRaisesRegex(ValueError, "mismatch"):
                module.inventory(archive, TARGET, "b" * 40)


if __name__ == "__main__":
    unittest.main()
