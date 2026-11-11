# Native binary Release qualification

GPMC's native qualification jobs produce **candidate artifacts**, not a
redistribution approval. A public GitHub Release remains a separate manual
decision after source, runtime, license, and downstream acceptance checks.

## Dependency policy

- Linux x86_64/aarch64: build with a glibc 2.28 baseline, provide independently
  replaceable GMP/GMPXX/MPFR shared objects next to the solver, and use
  relative ELF runtime search paths. Do not require target machines to install
  a particular MPFR SONAME. Record exact binary/library hashes and ELF ABI.
- macOS 15+ Intel/Apple Silicon: static GMP/MPFR linkage, only system dynamic
  libraries, exact Mach-O architecture and deployment minimum.
- Windows x64: native MSYS2 UCRT64 PE executable with non-system GMP/MPFR,
  C++ compiler and other transitive runtime DLLs bundled alongside `gpmc.exe`.
  Recursively inspect PE imports; unknown DLLs fail qualification. Confirm
  extracted execution via native Windows Python, without UCRT64 on PATH.

All platforms must pass native counting, projected/complex science checks,
exact independent small-CNF oracles, binary/package checksum validation, and
extracted archive execution.

## Release blockers

Passing CI does **not** grant permission to publish. Before a public release:

1. Verify exact corresponding source, copyright notices, LGPL/GPL version
   obligations and replace/relink requirements for all redistributed third-party
   libraries and compiled LGPL code, including macOS static linking.
2. Prove clean target-machine operation and dependency closure for each
   declared OS/architecture and supported minimum release.
3. Admit QuPRS Python/Rust solver output compatibility, wheel/sdist packaging
   and offline use against the exact asset hashes.
4. Preserve immutable tagged source and checksum manifest. Never silently
   change the QuPRS default solver or fetch arbitrary latest assets.

The archive metadata deliberately retains `distribution_admitted=false`
until these independent conditions are reviewed and satisfied.
