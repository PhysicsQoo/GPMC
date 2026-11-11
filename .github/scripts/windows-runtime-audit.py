#!/usr/bin/env python3
"""Collect/audit UCRT64 x64 or CLANGARM64 Windows native DLL closure.

The source compiler's architecture and every bundled PE DLL are verified.
This is candidate qualification, not LGPL redistribution admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

IMPORT = re.compile(r"^\s*DLL Name:\s*([^\s]+)", re.I | re.M)
WIN32_SYSTEM = frozenset({
    "kernel32.dll", "kernelbase.dll", "user32.dll", "ucrtbase.dll",
    "msvcrt.dll", "ntdll.dll", "advapi32.dll", "bcrypt.dll",
    "crypt32.dll", "gdi32.dll", "ole32.dll", "oleaut32.dll",
    "shell32.dll", "shlwapi.dll", "ws2_32.dll", "rpcrt4.dll",
    "secur32.dll", "version.dll", "winmm.dll", "setupapi.dll",
    "imm32.dll", "comdlg32.dll", "comctl32.dll", "normaliz.dll",
    "psapi.dll", "iphlpapi.dll", "netapi32.dll", "dbghelp.dll",
    "winspool.drv",
})


PE_MACHINES = {"x86_64": 0x8664, "aarch64": 0xAA64}


def pe_arch_matches(data: bytes, arch: str) -> bool:
    if len(data) < 0x40 or data[:2] != b"MZ":
        return False
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    return (0 < pe_offset <= len(data) - 6
            and data[pe_offset:pe_offset + 4] == b"PE\x00\x00"
            and struct.unpack_from("<H", data, pe_offset + 4)[0] == PE_MACHINES[arch])


def imports(path: Path) -> set[str]:
    output = subprocess.run(
        ["objdump", "-p", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout
    names = {m.group(1).lower() for m in IMPORT.finditer(output)}
    if not names:
        raise ValueError(f"No PE imports detected: {path}")
    return names


def is_windows_dll(name: str) -> bool:
    return (name in WIN32_SYSTEM or name.startswith("api-ms-win-")
            or name.startswith("ext-ms-"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=sorted(PE_MACHINES), default="x86_64")
    parser.add_argument("--binary", required=True)
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dependencies", required=True)
    args = parser.parse_args()

    binary = Path(args.binary).resolve()
    if not pe_arch_matches(binary.read_bytes(), args.arch):
        raise ValueError(f"Expected PE native {args.arch} executable")
    compiler = shutil.which("clang++" if args.arch == "aarch64" else "gcc")
    if not compiler:
        raise ValueError("Required native Windows compiler not found")
    toolchain_bin = Path(compiler).resolve().parent
    if toolchain_bin.name.lower() != "bin":
        raise ValueError("Unexpected compiler location")
    target = Path(args.runtime_dir)
    target.mkdir(parents=True, exist_ok=True)
    if list(target.iterdir()):
        raise ValueError("Runtime destination must start empty")

    queue = [binary]
    seen_imports: set[str] = set()
    bundled: dict[str, bytes] = {}
    system: set[str] = set()
    while queue:
        current = queue.pop(0)
        for name in sorted(imports(current)):
            if name in seen_imports:
                continue
            seen_imports.add(name)
            if name == "msys-2.0.dll":
                raise ValueError("Native UCRT64 solver must not depend on MSYS POSIX runtime")
            dll = toolchain_bin / name
            if dll.is_file():
                data = dll.read_bytes()
                if not pe_arch_matches(data, args.arch):
                    raise ValueError(f"Incorrect PE DLL architecture for {args.arch}: {name}")
                bundled[name] = data
                queue.append(dll)
            elif is_windows_dll(name):
                system.add(name)
            else:
                raise ValueError(f"Unresolved or unexpected Windows dependency: {name}")

    names = set(bundled)
    if not (any("gmp" in n and "gmpxx" not in n for n in names)
            and any("gmpxx" in n for n in names)
            and any("mpfr" in n for n in names)):
        raise ValueError(f"Missing GMP/GMPXX/MPFR dynamic DLLs: {sorted(names)}")
    if not names or len(names) > 30:
        raise ValueError("Suspicious bundled DLL count")
    for name, data in bundled.items():
        (target / name).write_bytes(data)

    hashes = {k: hashlib.sha256(v).hexdigest() for k, v in sorted(bundled.items())}
    report = {
        "schema": 1,
        "target": "windows-clangarm64-aarch64" if args.arch == "aarch64" else "windows-ucrt64-x86_64",
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "assessment": {
            "format": "PE32+",
            "machine": args.arch,
            "runtime": "CLANGARM64" if args.arch == "aarch64" else "UCRT64",
            "bundled_dll_sha256": hashes,
            "system_dlls": sorted(system),
            "windows_clean_install_certified": False,
            "reason": "Release redistribution license and clean-user installation remain separate gates.",
        },
        "distribution_admitted": False,
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(args.dependencies).write_text(
        f"Bundled {args.arch} runtime DLLs:\n" +
        "".join(f"{name} sha256={digest}\n" for name, digest in hashes.items()) +
        "System DLLs:\n" + "".join(f"{name}\n" for name in sorted(system)),
        encoding="utf-8",
    )
    print(f"WINDOWS_RUNTIME_AUDIT_PASS dlls={len(bundled)} "
          f"system={len(system)} distribution_admitted=false")


if __name__ == "__main__":
    main()
