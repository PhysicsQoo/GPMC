#!/usr/bin/env python3
"""Build a fail-closed, source-pinned redistribution *inventory* from a GPMC archive.

This is an evidence inventory, NOT a legal opinion or permission to publish.
In particular, the installed binary's exact corresponding source, copyright
notices, replacement rights and Apple production signing are not inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

TARGETS = frozenset((
    "linux-almalinux8-x86_64", "linux-almalinux8-aarch64",
    "macos15-x86_64", "macos15-arm64",
    "windows-ucrt64-x86_64", "windows-clangarm64-aarch64",
))
NOTICE_PATHS = frozenset((
    "licenses/LICENSE.md",
    "licenses/flow-cutter-pace17/LICENSE",
    "licenses/preprocessor/lib_sharpsat_td/LICENSE",
    "licenses/mpfr/copying.txt",
))
MAX_MEMBER_BYTES = 80 * 1024 * 1024
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def family(name: str) -> tuple[str, str | None]:
    lower = name.lower()
    if "gmpxx" in lower:
        return "GNU GMP C++", "LGPL-3.0-or-later OR GPL-2.0-or-later (upstream reference only)"
    if "gmp" in lower:
        return "GNU GMP", "LGPL-3.0-or-later OR GPL-2.0-or-later (upstream reference only)"
    if "mpfr" in lower:
        return "GNU MPFR", "LGPL-3.0-or-later (upstream reference only)"
    return "unclassified runtime", None


def inventory(archive_path: Path, target: str, source_sha: str) -> dict:
    if target not in TARGETS or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Unknown target or non-exact source commit")
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Unreasonably large release archive")

    with tarfile.open(archive_path, mode="r:gz") as archive:
        entries = archive.getmembers()
        if not entries or len(entries) > 80:
            raise ValueError("Invalid archive member count")
        if any(not m.isfile() or m.size > MAX_MEMBER_BYTES
               or m.name.startswith("/") or ".." in Path(m.name).parts
               or not re.fullmatch(r"[A-Za-z0-9_.+/-]+", m.name)
               for m in entries):
            raise ValueError("Unsafe or unexpected archive member")
        names = [m.name for m in entries]
        if len(set(names)) != len(names):
            raise ValueError("Duplicate archive member")
        required = NOTICE_PATHS | {"abi-report.json", "provenance.json", "dependencies.txt"}
        binary_name = "gpmc.exe" if target.startswith("windows-") else "gpmc"
        if not required.issubset(names) or binary_name not in names:
            raise ValueError("Archive lacks required notices or executable")
        contents = {m.name: archive.extractfile(m).read() for m in entries}

    provenance = json.loads(contents["provenance.json"])
    abi = json.loads(contents["abi-report.json"])
    if (provenance.get("project") != "PhysicsQoo/GPMC"
            or provenance.get("source_commit") != source_sha
            or provenance.get("platform") != target
            or provenance.get("executable_sha256") != digest(contents[binary_name])
            or provenance.get("abi_report_sha256") != digest(contents["abi-report.json"])
            or abi.get("target") != target
            or abi.get("binary_sha256") != digest(contents[binary_name])
            or abi.get("distribution_admitted") is not False
            or provenance.get("distribution_admitted") is not False):
        raise ValueError("Source/binary/ABI/admission provenance mismatch")

    if target.startswith("windows-"):
        libraries = {name: data for name, data in contents.items() if name.lower().endswith(".dll")}
        if any("/" in name for name in libraries):
            raise ValueError("Windows runtime DLL must be at archive root")
    else:
        libraries = {name.split("/", 1)[1]: data for name, data in contents.items()
                     if name.startswith("libs/") and name.count("/") == 1}
    if len(libraries) < 3:
        raise ValueError("Missing runtime dependency closure")
    actual_hashes = {name: digest(data) for name, data in sorted(libraries.items())}
    if provenance.get("bundled_library_sha256") != actual_hashes:
        raise ValueError("Bundled library hashes do not match provenance")

    package_owners = {}
    brew_versions = {}
    if target.startswith("windows-"):
        package_owners = abi.get("assessment", {}).get("installed_dll_package_owners", {})
        if not isinstance(package_owners, dict) or set(package_owners) != set(libraries):
            raise ValueError("Missing exact installed package ownership for Windows runtime DLLs")
        for name, owner in package_owners.items():
            if not isinstance(owner, dict) or not owner.get("package") or not owner.get("version"):
                raise ValueError(f"Incomplete local package ownership record: {name}")
    elif target.startswith("macos"):
        brew_versions = provenance.get("installed_homebrew_formula_versions", {})
        if not isinstance(brew_versions, dict) or set(brew_versions) != {"gmp", "mpfr"}:
            raise ValueError("Missing build-time Homebrew formula versions")
    dependency_text = contents["dependencies.txt"].decode("utf-8", errors="replace")
    components = []
    for name in sorted(libraries):
        group, upstream_license = family(name)
        owner = package_owners.get(name, {})
        formula = "mpfr" if "mpfr" in name else "gmp"
        build_formula = formula if target.startswith("macos") else None
        components.append({
            "filename": name,
            "sha256": actual_hashes[name],
            "component_family_hint": group,
            "upstream_license_reference_not_verified_for_binary": upstream_license,
            "actual_binary_package": owner.get("package") or (f"Homebrew {build_formula}" if build_formula else None),
            "actual_package_version": owner.get("version") or brew_versions.get(formula),
            "package_identity_is_build_time_hint_only": True,
            "corresponding_source_url": None,
            "corresponding_source_sha256": None,
            "source_and_patch_correspondence_verified": False,
            "copyright_and_notice_reviewed": False,
            "replacement_or_relinking_verified": False,
        })
    return {
        "schema": 1,
        "scope": "candidate-redistribution-inventory-not-license-clearance",
        "project": "PhysicsQoo/GPMC",
        "target": target,
        "source_commit": source_sha,
        "release_version": provenance.get("release_version"),
        "archive_name": archive_path.name,
        "archive_sha256": digest(archive_path.read_bytes()),
        "executable_name": binary_name,
        "executable_sha256": digest(contents[binary_name]),
        "abi_report_sha256": digest(contents["abi-report.json"]),
        "builder_dependencies_sha256": digest(contents["dependencies.txt"]),
        "builder_dependencies_raw": dependency_text,
        "installed_package_owners": package_owners,
        "installed_homebrew_formula_versions": brew_versions,
        "bundled_libraries": components,
        "included_notice_files_sha256": {n: digest(contents[n]) for n in sorted(NOTICE_PATHS)},
        "included_notices_prove_component_compliance": False,
        "all_corresponding_sources_delivered": False,
        "all_runtime_licenses_reviewed": False,
        "macos_developer_id_and_notarization_verified": False,
        "signed_runtime_library_substitution_verified": False,
        "distribution_admitted": False,
        "outstanding": [
            "Resolve each actual binary file to its installed package/version and exact patched source",
            "Archive durable source bundles, source checksums, license texts and notices",
            "Verify LGPL replacement/relinking with user-modified libraries",
            "Verify macOS Developer ID hardened runtime, library validation and notarization",
            "Review any other bundled Windows runtime licenses separately",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-distribution-admission", action="store_true")
    args = parser.parse_args()
    report = inventory(args.archive, args.target, args.source_sha)
    serialized = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.output.exists() and args.output.read_bytes() != serialized:
        raise ValueError("Stale, conflicting or tampered redistribution inventory")
    if args.require_distribution_admission:
        raise ValueError("Distribution is NOT admitted by a candidate-only inventory")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialized)
    print(f"REDISTRIBUTION_INVENTORY_PASS target={args.target} "
          f"libraries={len(report['bundled_libraries'])} distribution_admitted=false")


if __name__ == "__main__":
    main()
