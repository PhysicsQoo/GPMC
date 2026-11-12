# GPMC v1.0.2 — six-platform unified CLI release

PhysicsQoo/GPMC is independently maintained based on the original GPMC by
Kenji Hashimoto. This is a **complete six-platform** patch release: all
six archives use the same `v1.0.2` version and the **same exact source
commit**, reflected in each `provenance.json`.

## Platforms

- Linux x86_64 and Linux ARM64: the tested Ubuntu 22.04 / glibc 2.35 baseline,
  with system `libmpfr.so.6`. These replace the Linux v1.0.0 builds that
  required the unavailable `libmpfr.so.4`.
- macOS Intel and Apple Silicon: unchanged CLI building and scientific
  qualification methods, with minimum deployment target macOS 15.
- Windows x86_64 UCRT64 and Windows ARM64 CLANGARM64: unchanged native CLI
  qualification methods.

The macOS and Windows executables are sourced from the six-platform native
qualification of this exact release commit. No changes to model counting
algorithms, no Apple Developer ID notarization, and no additional shared
libraries are bundled. The Linux executables are rebuilt with Ubuntu
22.04 MPFR 6 and tested in clean Ubuntu 22.04/24.04 environments.

Each CLI archive includes the executable, dependency information,
project/third-party notices and its exact source/executable hashes.
Use `SHA256SUMS.txt` to verify the download. These are CLI-only packages,
**not** standalone installers: compatible GMP/GMPXX, MPFR, zlib and
platform runtime shared libraries must be available.

For Ubuntu 22.04/24.04:

```sh
sudo apt-get install libmpfr6 libgmp10 libgmpxx4ldbl zlib1g
```

For macOS: `brew install gmp mpfr zlib`. Gatekeeper may require manual
approval for a trusted unsigned/unnotarized CLI. On Windows, install the
corresponding MSYS2 UCRT64 or CLANGARM64 runtime packages and use their
environment or matching DLLs on PATH.

Ubuntu 20.04, AlmaLinux 8, and other environments with glibc below 2.35
are **not** included in the Linux support baseline. Build from source.

GitHub Release `v1.0.1` (Linux-only) and `v1.0.0` are preserved
unchanged for historical reproducibility.
