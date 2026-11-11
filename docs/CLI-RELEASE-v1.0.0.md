# GPMC v1.0.0 — PhysicsQoo CLI

First stable native CLI distribution of the independently maintained
[PhysicsQoo/GPMC](https://github.com/PhysicsQoo/GPMC), based on the original
GPMC by Kenji Hashimoto, with complex weighted model counting support.

## Assets

Six platform/architecture-specific `gpmc-cli-v1.0.0-*.tar.gz` archives:
Linux x86_64 and ARM64 (AlmaLinux 8 / glibc 2.28 baseline);
macOS x86_64 and ARM64 (macOS 15 deployment target);
Windows UCRT64 x86_64 and CLANGARM64 ARM64.

Verify an asset against `SHA256SUMS.txt`, then extract it and run
`gpmc -mode=0 input.cnf` (Windows: `gpmc.exe`).

## Runtime dependencies

These are **CLI-only, not standalone installers**. Each archive contains the
tested executable, source-provenance manifest, original dependency report,
installation notes and project/third-party license texts. It does **not**
include GMP, GMPXX, MPFR, zlib or Windows compiler/runtime shared libraries.
Install the corresponding compatible **native shared libraries** before running.

- **Linux:** use compatible GMP, GMPXX, MPFR and zlib packages. In particular
  the Linux build uses `libgmp.so.10`, `libgmpxx.so.4`,
  `libmpfr.so.4` and a glibc 2.28 baseline; other Linux distributions may
  have different sonames and require a local source build.
- **macOS:** `brew install gmp mpfr zlib`; inspect the included
  `dependencies.txt` for the linked Homebrew paths. These binaries are
  not Developer ID notarized and may require user approval in Gatekeeper;
  clean macOS 15 host compatibility is not independently certified.
- **Windows:** install MSYS2 UCRT64 packages on x86_64, or MSYS2 CLANGARM64
  packages on ARM64, including matching GMP/MPFR/zlib and toolchain DLLs.
  Run from that MSYS2 environment (or arrange the matching `bin` on PATH).

The distributed build artifacts passed model-counting smoke tests and
11-case independent exact scientific oracles, but this does not certify
compatibility with every runtime environment.

## Source and licenses

The source archive attached automatically to the GitHub Release corresponds
to the exact `v1.0.0` tag. Each executable archive contains `provenance.json`
with the source Git SHA and executable SHA-256, and original license notices.
This is an independent PhysicsQoo release, **not** an upstream GPMC release.
