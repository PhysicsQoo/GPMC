# Native binary Release qualification

GPMC native build jobs produce **candidate artifacts**, not a redistribution
approval. A public GitHub Release remains a separate manual decision after
source, runtime, license, signing, and downstream acceptance gates.

## Six-platform candidate policy

- Linux x86_64 / aarch64: build with a glibc 2.28 baseline; bundle individually
  replaceable GMP/GMPXX/MPFR shared objects with relative `$ORIGIN` paths.
  Record exact executable/shared-object SHA-256, ELF ABI and source identity.
- macOS 15+ Intel / Apple Silicon: **preferred candidate bundles three
  replaceable GMP/GMPXX/MPFR dylibs** in `libs/`; Mach-O imports are rewritten
  to `@loader_path`-relative paths with no Homebrew runtime search path.
  Modified native code is ad-hoc signed for scientific and relocation tests.
  The previously validated static-link build mode is kept as a technical
  fallback only; LGPL obligations apply regardless of linkage choice.
- Windows x86_64: build native MSYS2 UCRT64 PE, recursively inspect imports
  and bundle all non-system DLLs next to `gpmc.exe`. Unknown dependencies
  fail closed. Verify extraction and execution through native Windows Python.
- Windows 11 ARM64: build native MSYS2 CLANGARM64 PE32+ (Machine 0xAA64) on
  GitHub's Windows ARM runner, using ARM64 Clang/GMP/MPFR packages. Bundle
  the recursive ARM64 DLL closure next to the executable; validate the
  precise source SHA, executable and DLL architectures/hashes, 11-case
  independent oracle, and extracted native execution without MSYS2 PATH.
  This is a separately admitted sixth target: Windows x64 and ARM64
  candidates cannot be interchanged or treated as evidence for a QuPRS wheel.

The main native release workflow qualifies all six targets from one exact
source SHA and checks the archive and executable/library hashes. It creates
**only unpublished draft Releases** for explicit version tags. Actions
qualification artifacts are not formal releases.

Native Windows ARM64 has passed a separate technical proof of concept, and is
now included in the unified six-platform candidate qualification. If its
signing, source, license, minimum-OS or clean-target gates fail, the release
owner may **explicitly revert the optional ARM64 candidate** and restore the
five-platform draft plan; never silently omit an asset from a six-platform
tag or mislabel x64 as ARM64.

## Remaining hard gates

1. Review actual package/library source correspondence, notices, LGPL/GPL and
   LLVM/MinGW runtime redistribution obligations, and user substitution or
   relinking rights on every target.
2. For macOS, verify the intended Developer ID/Hardened Runtime/Library
   Validation and Gatekeeper/notarization approach permits the required
   replacement or relinking path. The current ad-hoc signatures prove none of
   those requirements.
3. Independently test downloaded archives on clean supported target systems,
   including OS floors, runtime closure, complex/projected/precision/oracle
   semantics and SHA/source provenance.
4. Admit QuPRS Python/Rust solver behavior, wheel and source distributions,
   full supported-platform pytest, and offline execution before replacing
   the existing source-pinned Submodule integration.

No public Release or QuPRS consumer switch is authorized until the above
evidence is complete. Candidate metadata explicitly reports
`distribution_admitted=false` and macOS `notarized=false`.
