#!/usr/bin/env python3
"""Package and re-check source-pinned native GPMC qualification binaries.

This script deliberately does not assert manylinux, relocatability or clean
runtime compatibility: those properties require separate admission checks.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED = {
    "linux-almalinux8-x86_64": ("elf", 62),
    "linux-almalinux8-aarch64": ("elf", 183),
    "macos15-arm64": ("macho", 0x0100000C),
    "macos15-x86_64": ("macho", 0x01000007),
}
LICENSES = (
    "LICENSE.md",
    "flow-cutter-pace17/LICENSE",
    "preprocessor/lib_sharpsat_td/LICENSE",
    "mpfr/copying.txt",
)


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_architecture(data: bytes, target: str) -> None:
    kind, architecture = SUPPORTED[target]
    if kind == "elf":
        valid = (
            len(data) >= 20
            and data[:6] == b"\x7fELF\x02\x01"
            and struct.unpack_from("<H", data, 18)[0] == architecture
        )
    else:
        valid = (
            len(data) >= 8
            and data[:4] == b"\xcf\xfa\xed\xfe"
            and struct.unpack_from("<I", data, 4)[0] == architecture
        )
    if not valid:
        raise ValueError(f"Incorrect native binary architecture for {target}")


def add_bytes(archive: tarfile.TarFile, path: str, data: bytes, executable: bool = False) -> None:
    info = tarfile.TarInfo(path)
    info.size = len(data)
    info.mode = 0o755 if executable else 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    archive.addfile(info, io.BytesIO(data))


def expected_name(version: str, target: str) -> str:
    if version != "candidate" and not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?", version):
        raise ValueError("Expected candidate or an explicit vMAJOR.MINOR.PATCH[-rc.NUMBER] version")
    return f"gpmc-{version}-{target}.tar.gz"


def package(args: argparse.Namespace) -> None:
    if args.target not in SUPPORTED:
        raise ValueError("Unsupported qualification target")
    if not re.fullmatch("[0-9a-f]{40}", args.source_sha):
        raise ValueError("Source must be pinned to a full Git commit SHA")
    name = expected_name(args.version, args.target)
    binary = Path(args.binary).read_bytes()
    check_architecture(binary, args.target)
    dependencies = Path(args.dependencies).read_bytes()
    runtime_libs = {}
    if args.target.startswith("linux-"):
        if not args.runtime_dir:
            raise ValueError("Linux candidate requires bundled shared GMP/MPFR libraries")
        expected = {"libgmp.so.10", "libgmpxx.so.4", "libmpfr.so.4"}
        folder = Path(args.runtime_dir)
        if {p.name for p in folder.iterdir() if p.is_file()} != expected:
            raise ValueError("Unexpected Linux runtime library set")
        for libname in sorted(expected):
            data = (folder / libname).read_bytes()
            check_architecture(data, args.target)
            runtime_libs[libname] = data
    elif args.runtime_dir:
        raise ValueError("macOS static candidate must not bundle runtime libraries")
    abi_report = Path(args.abi_report).read_bytes()
    abi = json.loads(abi_report)
    if abi.get("target") != args.target or abi.get("binary_sha256") != fingerprint(binary):
        raise ValueError("ABI audit does not correspond to the bundled executable")
    if abi.get("distribution_admitted") is not False:
        raise ValueError("Unreviewed candidate must not claim distribution admission")
    provenance = {
        "schema": 1,
        "project": "PhysicsQoo/GPMC",
        "release_version": args.version,
        "source_commit": args.source_sha,
        "platform": args.target,
        "executable_sha256": fingerprint(binary),
        "abi_report_sha256": fingerprint(abi_report),
        "bundled_library_sha256": {name: fingerprint(data) for name, data in runtime_libs.items()},
        "library_mode": "static-gmp-mpfr" if args.target.startswith("macos") else "bundled-dynamic-gmp-mpfr",
        "admission": "native-build-and-science-smoke-only",
    }
    files = {
        "gpmc": (binary, True),
        "provenance.json": (json.dumps(provenance, indent=2, sort_keys=True).encode() + b"\n", False),
        "dependencies.txt": (dependencies, False),
        "abi-report.json": (abi_report, False),
    }
    for libname, data in runtime_libs.items():
        files[f"libs/{libname}"] = (data, False)
    for path in LICENSES:
        files[f"licenses/{path}"] = ((ROOT / path).read_bytes(), False)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    archive_file = output / name
    with archive_file.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for path in sorted(files):
                    data, executable = files[path]
                    add_bytes(archive, path, data, executable)
    digest = fingerprint(archive_file.read_bytes())
    (output / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="ascii")
    print(f"PACKAGE_PASS {name} source={args.source_sha} binary_sha256={provenance['executable_sha256']}")


def verify(args: argparse.Namespace) -> None:
    if args.target not in SUPPORTED:
        raise ValueError("Unsupported qualification target")
    filename = expected_name(args.version, args.target)
    archive_path = Path(args.output_dir) / filename
    data = archive_path.read_bytes()
    checksum = (Path(args.output_dir) / f"{filename}.sha256").read_text(encoding="ascii").strip()
    if checksum != f"{fingerprint(data)}  {filename}":
        raise ValueError("Archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        allowed = {"gpmc", "provenance.json", "dependencies.txt", "abi-report.json"} | {f"licenses/{p}" for p in LICENSES}
        if args.target.startswith("linux-"):
            allowed |= {"libs/libgmp.so.10", "libs/libgmpxx.so.4", "libs/libmpfr.so.4"}
        if len(members) != len(allowed) or {m.name for m in members} != allowed:
            raise ValueError("Release archive has an unexpected file set")
        if any(not m.isfile() for m in members):
            raise ValueError("Release archive contains non-regular files")
        binary = archive.extractfile("gpmc").read()
        metadata = json.loads(archive.extractfile("provenance.json").read())
        abi_report = archive.extractfile("abi-report.json").read()
        runtime_libs = {
            member.name.split("/", 1)[1]: archive.extractfile(member).read()
            for member in members if member.name.startswith("libs/")
        }
    for libname, libdata in runtime_libs.items():
        check_architecture(libdata, args.target)
    abi = json.loads(abi_report)
    if abi.get("target") != args.target or abi.get("binary_sha256") != fingerprint(binary):
        raise ValueError("Bundled ABI report does not match the executable")
    if abi.get("distribution_admitted") is not False:
        raise ValueError("Bundled ABI report must remain unqualified")
    if metadata != {
        "schema": 1,
        "project": "PhysicsQoo/GPMC",
        "release_version": args.version,
        "source_commit": args.source_sha,
        "platform": args.target,
        "executable_sha256": fingerprint(binary),
        "abi_report_sha256": fingerprint(abi_report),
        "bundled_library_sha256": {name: fingerprint(data) for name, data in runtime_libs.items()},
        "library_mode": "static-gmp-mpfr" if args.target.startswith("macos") else "bundled-dynamic-gmp-mpfr",
        "admission": "native-build-and-science-smoke-only",
    }:
        raise ValueError("Source/platform/executable provenance mismatch")
    check_architecture(binary, args.target)
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        executable = folder / "gpmc"
        executable.write_bytes(binary)
        executable.chmod(0o755)
        if runtime_libs:
            library_dir = folder / "libs"
            library_dir.mkdir()
            for libname, libdata in runtime_libs.items():
                (library_dir / libname).write_bytes(libdata)
        cnf = folder / "one.cnf"
        cnf.write_text("p cnf 1 1\n1 0\n", encoding="ascii")
        # Prove the archive runs without inherited Homebrew/LD search paths.
        clean_env = {k: v for k, v in os.environ.items()
                     if not k.startswith(("DYLD_", "LD_LIBRARY_PATH", "LD_PRELOAD"))}
        clean_env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
        result = subprocess.run(
            [str(executable), "-mode=0", str(cnf)],
            capture_output=True, text=True, timeout=30, check=True, env=clean_env,
        )
        if "c s exact arb int 1" not in result.stdout.splitlines():
            raise ValueError("Extracted release executable failed standalone model counting")
    print(f"ARCHIVE_VERIFY_PASS {filename} source={args.source_sha}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pack", "verify"))
    parser.add_argument("--target", choices=sorted(SUPPORTED), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--binary")
    parser.add_argument("--dependencies")
    parser.add_argument("--abi-report")
    parser.add_argument("--runtime-dir")
    args = parser.parse_args()
    if args.action == "pack":
        if not args.binary or not args.dependencies or not args.abi_report:
            parser.error("pack requires --binary, --dependencies and --abi-report")
        package(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
