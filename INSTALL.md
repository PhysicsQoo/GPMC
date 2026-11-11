# GPMC installation

## Requirements

- CMake >= 3.20 and a C++11 compiler
- Ninja (for the provided presets)
- GMP and GMPXX, MPFR, and zlib development packages

Install native development libraries using your platform package manager. The
repository does not download or build these dependencies.

## Reproducible configuration

```sh
cmake --preset release
cmake --build --preset release --parallel 2
./build/gpmc -mode=0 example/dekel_test.cnf
bash .github/scripts/scientific-smoke.sh ./build/gpmc
```

For debug builds use the `debug` preset and `build-debug/gpmc`. On Windows
with MSYS2 UCRT64, use `build/gpmc.exe` and install the corresponding UCRT64
CMake, Ninja, GCC, GMP, MPFR and zlib packages.

`build.sh r` remains available as a legacy wrapper, copying the output to
`bin/gpmc`.

## Provenance and limitations

The CI matrix builds and tests Linux x64, macOS arm64 and Windows UCRT64 x64,
and uploads the tested executable, a SHA-256 checksum, source Git revision,
and a smoke transcript. This makes each artifact traceable to a source
revision, but does **not** certify bit-identical rebuilds: GMP/MPFR/zlib,
compilers, and package-manager versions are not fully pinned.

The scientific smoke tests cover only small exact MC/PMC and integer-valued
complex WMC/WPMC witnesses. Broader precision, cancellation, and projected
weighted-model fixtures require independent regression acceptance.
