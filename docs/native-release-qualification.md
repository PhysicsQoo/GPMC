# Native binary Release qualification

GPMC native build jobs produce **candidate artifacts**, not a redistribution
approval. A public GitHub Release remains a separate manual decision after
source, runtime, license, signing, and downstream acceptance gates.

## Five-platform candidate policy

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

The main native release workflow qualifies all five targets from one exact
source SHA and checks the archive and executable/library hashes. It creates
**only unpublished draft Releases** for explicit version tags. Actions
qualification artifacts are not formal releases.

A separate Windows 11 ARM64 / CLANGARM64 candidate experiment may produce an
optional sixth artifact; it must not block the first qualified five-platform
release candidate.

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
