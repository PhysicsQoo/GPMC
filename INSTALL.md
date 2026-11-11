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

`build.sh r` and `build.sh d` remain available as compatibility wrappers around
these same Ninja presets, copying the output to `bin/gpmc`. `build.sh rs`
requests a static binary only when the platform supports static linkage.

## Provenance and limitations

The CI matrix builds and tests Linux x64, macOS arm64 and Windows UCRT64 x64,
and uploads the tested executable, a SHA-256 checksum, source Git revision,
the exact solver smoke output, the multi-case scientific test transcript,
and a `build-provenance.txt` manifest recording compiler/CMake and installed
GMP, MPFR, zlib package versions plus resolved include/library paths. SHA-256
is rechecked before upload. These attest the tested binary and its source,
but do **not** certify bit-identical rebuilds: packages, toolchains, and
runner images are not all locked to immutable content digests.

The native scientific tests cover integer MC/PMC, complex WMC/WPMC,
model cancellation, projected complex weights, and a decimal precision
witness beyond f64. These are focused golden tests, **not** a proof of full
solver correctness. Large projected-CNF, high-cancellation and interval-bound
cases still require their own scientific acceptance.
