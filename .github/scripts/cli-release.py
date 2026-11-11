#!/usr/bin/env python3
"""Minimal source-pinned GPMC CLI archive; system-provided shared libraries only."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[2]
LICENSES = (
    "LICENSE.md",
    "flow-cutter-pace17/LICENSE",
    "preprocessor/lib_sharpsat_td/LICENSE",
    "mpfr/copying.txt",
)
MACHINES = (
    "linux-almalinux8-x86_64",
    "linux-almalinux8-aarch64",
    "macos15-arm64",
    "macos15-x86_64",
    "windows-ucrt64-x86_64",
    "windows-clangarm64-aarch64",
)

spec = importlib.util.spec_from_file_location(
    "native_bundle", Path(__file__).with_name("native-release-bundle.py")
)
native_bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_bundle)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_name(version: str, target: str) -> str:
    if not re.fullmatch(r"candidate|v[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Invalid CLI release version")
    if target not in MACHINES:
        raise ValueError("Unsupported CLI target")
    return f"gpmc-cli-{version}-{target}.tar.gz"


def usage(target: str) -> bytes:
    common = (
        "GPMC independent PhysicsQoo CLI distribution\n"
        "Source and checksum: see provenance.json and .sha256 sidecar.\n"
        "The GNU GMP/GMPXX, MPFR, zlib and C/C++ runtimes are NOT bundled.\n"
        "This is NOT a self-contained installer. Install compatible native\n"
        "runtime libraries using your platform's package manager.\n\n"
    )
    if target.startswith("linux-"):
        detail = (
            "Linux: build ABI baseline is AlmaLinux 8 / glibc 2.28.\n"
            "Install compatible gmp, gmp-c++, mpfr and zlib packages.\n"
            "The executable needs libgmp.so.10, libgmpxx.so.4 and\n"
            "libmpfr.so.4; a newer incompatible soname is insufficient.\n"
        )
    elif target.startswith("macos"):
        detail = (
            "macOS: install Homebrew packages: brew install gmp mpfr zlib\n"
            "Inspect dependencies.txt with otool -L for linked library paths.\n"
            "Built on macOS 26 ARM64 or macOS 15 Intel with minimum deployment\n"
            "target 15.0. Compatibility on clean macOS 15 is not certified.\n"
            "This CLI is not Developer-ID notarized; Gatekeeper may warn.\n"
        )
    elif target == "windows-ucrt64-x86_64":
        detail = (
            "Windows x64: install matching MSYS2 UCRT64 runtime packages\n"
            "(mingw-w64-ucrt-x86_64-gmp/mpfr/zlib and toolchain runtime).\n"
            "Launch from the MSYS2 UCRT64 environment, or add its bin\n"
            "directory to PATH. This package contains no runtime DLLs.\n"
        )
    else:
        detail = (
            "Windows ARM64: install matching MSYS2 CLANGARM64 runtime packages\n"
            "(mingw-w64-clang-aarch64-gmp/mpfr/zlib and toolchain runtime).\n"
            "Launch from the MSYS2 CLANGARM64 environment, or add its bin\n"
            "directory to PATH. This package contains no runtime DLLs.\n"
        )
    return (common + detail + "\nUsage: gpmc -mode=0 input.cnf\n").encode("utf-8")


def expected_members(target: str) -> set[str]:
    exe = "gpmc.exe" if target.startswith("windows-") else "gpmc"
    return {exe, "README-CLI.txt", "provenance.json", "dependencies.txt"} | {
        "licenses/" + name for name in LICENSES
    }


def add_file(tar: tarfile.TarFile, name: str, blob: bytes, execute: bool = False) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(blob)
    info.mode = 0o755 if execute else 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    tar.addfile(info, io.BytesIO(blob))


def package(args: argparse.Namespace) -> None:
    name = archive_name(args.version, args.target)
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha):
        raise ValueError("Source SHA must be a full commit ID")
    exe_name = "gpmc.exe" if args.target.startswith("windows-") else "gpmc"
    exe = Path(args.binary).read_bytes()
    native_bundle.check_architecture(exe, args.target)
    deps = Path(args.dependencies).read_bytes()
    provenance = {
        "project": "PhysicsQoo/GPMC",
        "release_version": args.version,
        "source_commit": args.source_sha,
        "platform": args.target,
        "executable_sha256": digest(exe),
        "dependencies_sha256": digest(deps),
        "runtime_mode": "external-system-shared-libraries",
        "bundled_runtime_libraries": [],
    }
    items = {
        exe_name: exe,
        "README-CLI.txt": usage(args.target),
        "provenance.json": (json.dumps(provenance, sort_keys=True, indent=2) + "\n").encode(),
        "dependencies.txt": deps,
    }
    for rel in LICENSES:
        items["licenses/" + rel] = (ROOT / rel).read_bytes()
    assert set(items) == expected_members(args.target)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / name
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(mode="w", fileobj=gz) as tar:
                for key in sorted(items):
                    add_file(tar, key, items[key], key == exe_name)
    (output / (name + ".sha256")).write_text(
        f"{digest(path.read_bytes())}  {name}\n", encoding="ascii"
    )
    verify(args)
    print(f"CLI_PACKAGE_PASS name={name} source={args.source_sha} sha256={digest(path.read_bytes())}")


def verify(args: argparse.Namespace) -> None:
    name = archive_name(args.version, args.target)
    path = Path(args.output_dir) / name
    value = (Path(args.output_dir) / (name + ".sha256")).read_text(encoding="ascii")
    if value != f"{digest(path.read_bytes())}  {name}\n":
        raise ValueError("CLI checksum mismatch")
    with tarfile.open(path, mode="r:gz") as tar:
        members = tar.getmembers()
        names = [member.name for member in members]
        if set(names) != expected_members(args.target) or len(names) != len(set(names)):
            raise ValueError("Missing or unexpected CLI package files")
        if any(not member.isfile() or member.issym() or member.islnk() for member in members):
            raise ValueError("CLI archive must contain only regular files")
        data = {m.name: tar.extractfile(m).read() for m in members}
        provenance = json.loads(data["provenance.json"])
        exe_name = "gpmc.exe" if args.target.startswith("windows-") else "gpmc"
        native_bundle.check_architecture(data[exe_name], args.target)
        if (
            provenance.get("release_version") != args.version
            or provenance.get("source_commit") != args.source_sha
            or provenance.get("platform") != args.target
            or provenance.get("executable_sha256") != digest(data[exe_name])
            or provenance.get("dependencies_sha256") != digest(data["dependencies.txt"])
            or provenance.get("runtime_mode") != "external-system-shared-libraries"
            or provenance.get("bundled_runtime_libraries") != []
        ):
            raise ValueError("CLI provenance mismatch")
        for rel in LICENSES:
            if data["licenses/" + rel] != (ROOT / rel).read_bytes():
                raise ValueError("CLI license file mismatch")
        if data["README-CLI.txt"] != usage(args.target):
            raise ValueError("CLI installation guidance mismatch")
    print(f"CLI_ARCHIVE_VERIFY_PASS name={name} target={args.target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pack", "verify"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--binary")
    parser.add_argument("--dependencies")
    parser.add_argument("--output-dir", default="dist-cli")
    args = parser.parse_args()
    if args.action == "pack":
        if not args.binary or not args.dependencies:
            parser.error("pack requires --binary and --dependencies")
        package(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
