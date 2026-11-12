#!/usr/bin/env python3
"""Repackage already scientifically qualified native candidate CLI bytes for a new release."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import tempfile
import tarfile

spec = importlib.util.spec_from_file_location("cli_release", Path(__file__).with_name("cli-release.py"))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

UNCHANGED_TARGETS = (
    "macos15-arm64", "macos15-x86_64",
    "windows-ucrt64-x86_64", "windows-clangarm64-aarch64",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    if args.version != "v1.0.2":
        parser.error("This source-pinned repackaging step is only for v1.0.2")

    for target in UNCHANGED_TARGETS:
        candidate = argparse.Namespace(version="candidate", target=target,
            source_sha=args.source_sha, output_dir=str(args.candidate_dir))
        cli.verify(candidate)
        name = cli.archive_name("candidate", target)
        exe_name = "gpmc.exe" if target.startswith("windows-") else "gpmc"
        with tarfile.open(args.candidate_dir / name, "r:gz") as archive:
            exe = archive.extractfile(exe_name).read()
            dependencies = archive.extractfile("dependencies.txt").read()
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            binary = folder / exe_name
            binary.write_bytes(exe)
            dep = folder / "dependencies.txt"
            dep.write_bytes(dependencies)
            release = argparse.Namespace(version=args.version, target=target,
                source_sha=args.source_sha, binary=str(binary),
                dependencies=str(dep), output_dir=str(args.dest))
            cli.package(release)
            cli.verify(release)
        print(f"UNMODIFIED_NATIVE_EXECUTABLE_REPACKAGED target={target} source={args.source_sha}")


if __name__ == "__main__":
    main()
