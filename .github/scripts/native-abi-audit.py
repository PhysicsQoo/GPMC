#!/usr/bin/env python3
"""Report, but do not falsely certify, native release ABI portability.

This check is read-only and has no dependencies beyond Python and the platform
binutils. A successful report is NOT a manylinux or clean-machine certificate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


VERSIONED = {
    "GLIBC": re.compile(r"\bGLIBC_(\d+)\.(\d+)\b"),
    "GLIBCXX": re.compile(r"\bGLIBCXX_(\d+)\.(\d+)\.(\d+)\b"),
    "CXXABI": re.compile(r"\bCXXABI_(\d+)\.(\d+)(?:\.(\d+))?\b"),
}
NEEDED = re.compile(r"\(NEEDED\)\s+Shared library: \[([^]]+)\]")
MACOS_DYLIB = re.compile(r"^\s*(/\S+|@\S+)\s+\(compatibility version", re.M)


def max_symbol_versions(data: str) -> dict[str, str | None]:
    result = {}
    for label, matcher in VERSIONED.items():
        versions = [tuple(map(int, m.groups(default="0"))) for m in matcher.finditer(data)]
        result[label] = ".".join(map(str, max(versions))) if versions else None
    return result


def linux_abi(binary: Path) -> dict:
    versions = subprocess.run(
        ["readelf", "-W", "--version-info", str(binary)],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout
    dynamic = subprocess.run(
        ["readelf", "-W", "-d", str(binary)],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout
    library_names = sorted(set(NEEDED.findall(dynamic)))
    max_versions = max_symbol_versions(versions)
    glibc = max_versions["GLIBC"]
    # Read-only risk classification. This is NOT proof of wheel compatibility.
    glibc_too_new = (
        glibc is None or tuple(map(int, glibc.split("."))) > (2, 28)
    )
    dynamic_solver_libraries = [
        lib for lib in library_names
        if re.match(r"lib(?:gmp(?:xx)?|mpfr)(?:\.|$)", lib)
    ]
    return {
        "format": "ELF",
        "required_symbol_versions": max_versions,
        "dt_needed": library_names,
        "glibc_2_28_symbol_floor_pass": not glibc_too_new,
        "external_gmp_mpfr_runtime_dependencies": dynamic_solver_libraries,
        "manylinux_2_28_certified": False,
        "reason": (
            "Requires clean glibc-2.28 runtime, library and license admission; "
            "this is only an ELF symbol/dependency observation."
        ),
    }


def macos_abi(binary: Path) -> dict:
    deps = subprocess.run(
        ["otool", "-L", str(binary)],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout
    load_commands = subprocess.run(
        ["otool", "-l", str(binary)],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout
    names = sorted(set(MACOS_DYLIB.findall(deps)))
    minos = re.findall(r"^\s*minos\s+([0-9.]+)", load_commands, re.M)
    dynamic_solver_libraries = [
        lib for lib in names
        if re.search(r"/lib(?:gmp(?:xx)?|mpfr)(?:\.|$)", lib)
    ]
    unexpected = [lib for lib in names if not (
        lib.startswith("/usr/lib/") or lib.startswith("/System/Library/")
    )]
    if unexpected:
        raise ValueError(f"macOS requires non-system dylibs: {unexpected}")
    if not minos or any(tuple(map(int, x.split("."))) > (15, 0) for x in minos):
        raise ValueError(f"macOS deployment target exceeds 15.0: {minos}")
    return {
        "format": "Mach-O",
        "dynamic_libraries": names,
        "declared_macos_minos": sorted(set(minos)),
        "external_gmp_mpfr_runtime_dependencies": dynamic_solver_libraries,
        "macos_clean_install_certified": False,
        "reason": "Requires clean macOS target and redistribution license admission.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    binary = Path(args.binary)
    if not binary.is_file():
        parser.error("Binary does not exist")
    if args.target.startswith("linux-"):
        assessment = linux_abi(binary)
    elif args.target.startswith("macos"):
        assessment = macos_abi(binary)
    else:
        parser.error("Unsupported native target")
    report = {
        "schema": 1,
        "target": args.target,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "assessment": assessment,
        "distribution_admitted": False,
    }
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"ABI_REPORT_PASS target={args.target} "
        f"binary_sha256={report['binary_sha256']} "
        "distribution_admitted=false"
    )
    print(json.dumps(assessment, sort_keys=True))


if __name__ == "__main__":
    main()
