#!/usr/bin/env python3
"""Produce/verify a source-pinned macOS GPMC native Release candidate archive.

Never certify LGPL redistribution, hardened signing, notarization or QuPRS
compatibility from a passing scoped native smoke. Existing static builds stay
unchanged until formal release admission.
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
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")
OTOOl_DEP = re.compile(r"^\s*(\S+)\s+\(compatibility version", re.M)
MINOS = re.compile(r"^\s*minos\s+([0-9.]+)", re.M)
EXPECTED_LIBRARIES = ("gmp", "gmpxx", "mpfr")
LICENSES = ("LICENSE.md", "flow-cutter-pace17/LICENSE", "preprocessor/lib_sharpsat_td/LICENSE", "mpfr/copying.txt")
ARCHES = {"arm64", "x86_64"}


def cmd(*args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        [str(a) for a in args], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=60, env=env,
    )
    return proc.stdout


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_arch(path: Path, arch: str) -> None:
    found = cmd("lipo", "-archs", str(path)).strip().split()
    if found != [arch]:
        raise ValueError(f"{path.name}: expected thin {arch} Mach-O, got {found}")


def dependencies(path: Path, dylib: bool = False) -> list[str]:
    found = OTOOl_DEP.findall(cmd("otool", "-L", str(path)))
    if dylib:
        # First Mach-O dylib -L entry is its LC_ID_DYLIB install name.
        if not found:
            raise ValueError(f"Missing dylib install name: {path}")
        found = found[1:]
    if not found:
        raise ValueError(f"Missing dynamic dependency list: {path}")
    return found


def rpaths(path: Path) -> list[str]:
    lines = cmd("otool", "-l", str(path)).splitlines()
    result = []
    for i, line in enumerate(lines):
        if line.strip() == "cmd LC_RPATH":
            for candidate in lines[i + 1:i + 8]:
                match = re.match(r"^\s*path\s+(\S+)\s+\(offset", candidate)
                if match:
                    result.append(match.group(1))
                    break
    return result


def expand(location: str, referer: Path, binary: Path) -> Path:
    if location.startswith("@loader_path/"):
        return referer.parent / location[len("@loader_path/"):]
    if location.startswith("@executable_path/"):
        return binary.parent / location[len("@executable_path/"):]
    return Path(location)


def resolve(dep: str, referer: Path, binary: Path, prefixes: list[Path]) -> Path:
    if dep.startswith("@rpath/"):
        suffix = dep[len("@rpath/"):]
        dirs = [expand(p, referer, binary) for p in rpaths(referer) + rpaths(binary)]
        dirs.extend(p / "lib" for p in prefixes)
        options = [p / suffix for p in dirs]
    else:
        options = [expand(dep, referer, binary)]
    for candidate in options:
        if candidate.is_file():
            path = candidate.resolve()
            if not any(path.is_relative_to(p) for p in prefixes):
                raise ValueError(f"Non-system dylib outside declared build prefixes: {path}")
            return path
    raise ValueError(f"Unresolved macOS dynamic dependency {dep!r} in {referer.name}")


def discover(binary: Path, prefixes: list[Path]) -> tuple[dict[str, Path], dict[Path, list[tuple[str, str]]]]:
    found: dict[str, Path] = {}
    refs: dict[Path, list[tuple[str, str]]] = {}
    queue = [(binary.resolve(), False)]
    visited: set[Path] = set()
    while queue:
        current, is_dylib = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        refs[current] = []
        for dep in dependencies(current, is_dylib):
            if dep.startswith(SYSTEM_PREFIXES):
                continue
            child = resolve(dep, current, binary.resolve(), prefixes)
            name = child.name
            if not (name.startswith(("libgmp", "libmpfr")) and name.endswith(".dylib")):
                raise ValueError(f"Unexpected third-party dylib dependency: {child}")
            if name in found and found[name] != child:
                raise ValueError(f"Two distinct dylibs with the same basename: {name}")
            found[name] = child
            refs[current].append((dep, name))
            queue.append((child, True))
    for kind in EXPECTED_LIBRARIES:
        if not any(
            (name.startswith("libgmpxx") if kind == "gmpxx" else
             name.startswith("libmpfr") if kind == "mpfr" else
             name.startswith("libgmp") and not name.startswith("libgmpxx"))
            for name in found
        ):
            raise ValueError(f"Missing dylib {kind} in dependency closure")
    if len(found) != 3:
        raise ValueError(f"Expected exactly three GMP/GMPXX/MPFR dylibs, got {sorted(found)}")
    return found, refs


def make_relocatable(binary: Path, dest: Path, libs: dict[str, Path],
                     refs: dict[Path, list[tuple[str, str]]], arch: str) -> None:
    libdir = dest / "libs"
    libdir.mkdir(parents=True)
    shutil.copy2(binary, dest / "gpmc")
    for name, source in libs.items():
        shutil.copy2(source, libdir / name)
    copied = {binary.resolve(): dest / "gpmc"}
    copied.update({source: libdir / name for name, source in libs.items()})
    for source, changes in refs.items():
        target = copied[source]
        for old, name in changes:
            relative = ("@loader_path/libs/" if source == binary.resolve()
                        else "@loader_path/") + name
            cmd("install_name_tool", "-change", old, relative, str(target))
        if source != binary.resolve():
            cmd("install_name_tool", "-id", "@rpath/" + target.name, str(target))
        for path in rpaths(target):
            cmd("install_name_tool", "-delete_rpath", path, str(target))
        valid_arch(target, arch)
        cmd("codesign", "--force", "--sign", "-", "--timestamp=none", str(target))
        cmd("codesign", "--verify", "--strict", str(target))
    for item in [dest / "gpmc", *sorted(libdir.iterdir())]:
        verify_linkage(item, item.name != "gpmc")


def verify_linkage(path: Path, is_dylib: bool) -> None:
    if rpaths(path):
        raise ValueError(f"Unexpected inherited LC_RPATH in {path}")
    for dep in dependencies(path, is_dylib):
        if dep.startswith(SYSTEM_PREFIXES):
            continue
        prefix = "@loader_path/" if is_dylib else "@loader_path/libs/"
        if not dep.startswith(prefix):
            raise ValueError(f"Non-relocatable {path.name} dependency: {dep}")
        target = path.parent / dep[len("@loader_path/"):]
        if not target.is_file():
            raise ValueError(f"Unresolved relative bundle dependency: {target}")


def add(archive: tarfile.TarFile, path: str, data: bytes, executable: bool = False) -> None:
    item = tarfile.TarInfo(path)
    item.size = len(data)
    item.mode = 0o755 if executable else 0o644
    item.mtime = item.uid = item.gid = 0
    item.uname = item.gname = ""
    archive.addfile(item, io.BytesIO(data))


def archive_name(arch: str, version: str) -> str:
    if arch not in ARCHES:
        raise ValueError("Invalid macOS architecture")
    if version != "candidate" and not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-rc\.[0-9]+)?", version):
        raise ValueError("Invalid release candidate version")
    return f"gpmc-{version}-macos15-{arch}.tar.gz"


def bundle(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha):
        raise ValueError("Expected exact 40-digit source commit SHA")
    binary = Path(args.binary).resolve()
    valid_arch(binary, args.arch)
    prefixes = [Path(args.gmp_prefix).resolve(), Path(args.mpfr_prefix).resolve()]
    if not all(p.is_dir() for p in prefixes):
        raise ValueError("Expected existing Homebrew build-time prefixes")
    dylibs, refs = discover(binary, prefixes)
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        make_relocatable(binary, stage, dylibs, refs, args.arch)
        executable = stage / "gpmc"
        minos = MINOS.findall(cmd("otool", "-l", str(executable)))
        if not minos or any(tuple(int(v) for v in x.split(".")) > (15, 0) for x in minos):
            raise ValueError(f"Invalid macOS deployment target {minos}")
        bins = {"gpmc": executable.read_bytes()}
        bins.update({f"libs/{p.name}": p.read_bytes() for p in sorted((stage / "libs").iterdir())})
        license_data = {f"licenses/{name}": (ROOT / name).read_bytes() for name in LICENSES}
        audit_path = stage / "abi-report.json"
        cmd(sys.executable, str(ROOT / ".github/scripts/native-abi-audit.py"),
            "--binary", str(executable), "--target", f"macos15-{args.arch}",
            "--output", str(audit_path))
        audit_bytes = audit_path.read_bytes()
        audit = json.loads(audit_bytes)
        if (audit.get("binary_sha256") != sha(bins["gpmc"]) or
                audit.get("distribution_admitted") is not False):
            raise ValueError("ABI audit is not bound to signed staged executable")
        dependency_bytes = (cmd("otool", "-L", str(executable)) + "\n").encode()
        formula_versions = {}
        for raw in cmd("brew", "list", "--versions", "gmp", "mpfr").splitlines():
            parts = raw.strip().split()
            if len(parts) != 2 or parts[0] in formula_versions:
                raise ValueError(f"Ambiguous installed Homebrew formula: {raw!r}")
            formula_versions[parts[0]] = parts[1]
        if set(formula_versions) != {"gmp", "mpfr"}:
            raise ValueError(f"Missing installed Homebrew formula identity: {formula_versions}")
        report = {
            "schema": 1,
            "project": "PhysicsQoo/GPMC",
            "source_commit": args.source_sha,
            "release_version": args.version,
            "platform": f"macos15-{args.arch}",
            "target": f"macos15-{args.arch}",
            "library_mode": "bundled-relocatable-gmp-mpfr-dylibs",
            "installed_homebrew_formula_versions": formula_versions,
            "binary_sha256": sha(bins["gpmc"]),
            "executable_sha256": sha(bins["gpmc"]),
            "abi_report_sha256": sha(audit_bytes),
            "bundled_library_sha256": {name.split("/", 1)[1]: sha(data) for name, data in bins.items() if name != "gpmc"},
            "libraries_sha256": {name: sha(data) for name, data in bins.items() if name != "gpmc"},
            "admission": "native-build-and-science-smoke-only",
            "declared_macos_minos": minos,
            "signing": "ad-hoc-only",
            "notarized": False,
            "distribution_admitted": False,
            "reason": "Experimental only: LGPL source/relinking, notarization and downstream compatibility pending",
        }
        files = {**bins, **license_data,
                 "abi-report.json": audit_bytes,
                 "dependencies.txt": dependency_bytes,
                 "provenance.json": (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()}
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        name = archive_name(args.arch, args.version)
        with (output / name).open("wb") as handle:
            with gzip.GzipFile(fileobj=handle, mode="wb", filename="", mtime=0) as stream:
                with tarfile.open(fileobj=stream, mode="w|", format=tarfile.PAX_FORMAT) as tar:
                    for path, data in sorted(files.items()):
                        add(tar, path, data, executable=path == "gpmc")
        (output / f"{name}.sha256").write_text(
            f"{sha((output / name).read_bytes())}  {name}\n", encoding="ascii"
        )
        print(f"MACOS_DYLIB_BUNDLE_PASS arch={args.arch} source={args.source_sha} "
              f"libs={sorted(dylibs)} minos={minos} distribution_admitted=false")


def run_science(executable: Path) -> None:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("DYLD_", "LD_LIBRARY_PATH", "LD_PRELOAD"))}
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    cmd("/bin/bash", str(ROOT / ".github/scripts/scientific-smoke.sh"), str(executable), env=env)
    cmd(sys.executable, str(ROOT / ".github/scripts/scientific_oracle.py"), str(executable), env=env)


def verify(args: argparse.Namespace) -> None:
    output = Path(args.output_dir)
    name = archive_name(args.arch, args.version)
    tar_bytes = (output / name).read_bytes()
    sidecar = (output / f"{name}.sha256").read_text(encoding="ascii").strip()
    if sidecar != f"{sha(tar_bytes)}  {name}":
        raise ValueError("Archive SHA-256 mismatch")
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        members = tar.getmembers()
        names = {m.name for m in members}
        lib_names = {name for name in names if name.startswith("libs/")}
        expected = {"gpmc", "provenance.json", "dependencies.txt", "abi-report.json", *(f"licenses/{n}" for n in LICENSES)} | lib_names
        if names != expected or len(members) != len(expected) or not all(m.isfile() for m in members):
            raise ValueError("Unexpected files or non-regular members in macOS candidate")
        if len(lib_names) != 3 or any("/" in n[5:] or not n.endswith(".dylib") for n in lib_names):
            raise ValueError("Unexpected dylib closure")
        files = {m.name: tar.extractfile(m).read() for m in members}
    report = json.loads(files["provenance.json"])
    audit = json.loads(files["abi-report.json"])
    if audit.get("binary_sha256") != sha(files["gpmc"]) or audit.get("distribution_admitted") is not False:
        raise ValueError("ABI provenance mismatch")
    if (report.get("target") != f"macos15-{args.arch}"
            or report.get("source_commit") != args.source_sha
            or report.get("release_version") != args.version
            or report.get("platform") != f"macos15-{args.arch}"
            or report.get("abi_report_sha256") != sha(files["abi-report.json"])
            or report.get("admission") != "native-build-and-science-smoke-only"
            or report.get("bundled_library_sha256") != {name.split("/", 1)[1]: sha(files[name]) for name in lib_names}
            or report.get("distribution_admitted") is not False
            or report.get("notarized") is not False
            or report.get("library_mode") != "bundled-relocatable-gmp-mpfr-dylibs"
            or set(report.get("installed_homebrew_formula_versions", {})) != {"gmp", "mpfr"}
            or report.get("binary_sha256") != sha(files["gpmc"])
            or report.get("libraries_sha256") != {k: sha(files[k]) for k in lib_names}):
        raise ValueError("Source/target/binary/dylib provenance mismatch")
    with tempfile.TemporaryDirectory(prefix="gpmc-relocated-") as temp:
        stage = Path(temp)
        for path, data in files.items():
            dest = stage / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            dest.chmod(0o755 if path == "gpmc" else 0o644)
        executable = stage / "gpmc"
        for path in [executable, *sorted((stage / "libs").iterdir())]:
            valid_arch(path, args.arch)
            verify_linkage(path, path != executable)
            cmd("codesign", "--verify", "--strict", str(path))
        run_science(executable)
        # Replacing a standalone LGPL dylib file must not require relinking gpmc.
        # This only tests an ABI-identical replacement, not arbitrary new versions.
        replacement = sorted((stage / "libs").iterdir())[0]
        data = replacement.read_bytes()
        replacement.unlink()
        replacement.write_bytes(data)
        cmd("codesign", "--verify", "--strict", str(replacement))
        run_science(executable)
    print(f"MACOS_DYLIB_ARCHIVE_VERIFY_PASS arch={args.arch} "
          "science=pass replace_identical_dylib=pass distribution_admitted=false")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["bundle", "verify"])
    parser.add_argument("--arch", choices=sorted(ARCHES), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", default="candidate")
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--binary")
    parser.add_argument("--gmp-prefix")
    parser.add_argument("--mpfr-prefix")
    args = parser.parse_args()
    if args.action == "bundle":
        if not all([args.binary, args.gmp_prefix, args.mpfr_prefix]):
            parser.error("bundle requires --binary, --gmp-prefix and --mpfr-prefix")
        bundle(args)
    else:
        verify(args)


if __name__ == "__main__":
    main()
