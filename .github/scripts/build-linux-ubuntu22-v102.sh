#!/usr/bin/env bash
# Run inside Ubuntu 22.04 for native x86_64 / ARM64.
# Linux-only GPMC v1.0.2: public runtime uses system libmpfr.so.6.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update
apt-get -y -qq install --no-install-recommends \
  cmake ninja-build g++ libgmp-dev libmpfr-dev zlib1g-dev python3 binutils
test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.35"
cmake --preset release
cmake --build --preset release --parallel 2
test -x build/gpmc
readelf -d build/gpmc > linux-v102-dynamic.txt
grep -F 'Shared library: [libmpfr.so.6]' linux-v102-dynamic.txt
if grep -Fq 'Shared library: [libmpfr.so.4]' linux-v102-dynamic.txt; then
  echo "Unexpected obsolete MPFR SONAME" >&2
  exit 1
fi
ldd build/gpmc > linux-v102-dependencies.txt
if grep -Fq 'not found' linux-v102-dependencies.txt; then
  cat linux-v102-dependencies.txt >&2
  exit 1
fi
bash .github/scripts/scientific-smoke.sh build/gpmc
python3 .github/scripts/scientific_oracle.py build/gpmc
mkdir -p linux-v102-build
cp build/gpmc linux-v102-build/gpmc
cp linux-v102-dependencies.txt linux-v102-build/dependencies.txt
printf 'build_os=Ubuntu 22.04\nminimum_glibc=2.35\nrequired_mpfr_soname=libmpfr.so.6\n' >> linux-v102-build/dependencies.txt
# Ensure the host Actions user can package files written by the Docker container.
chown -R "${HOST_UID}:${HOST_GID}" linux-v102-build
echo "UBUNTU22_MPFR6_BUILD_AND_SCIENCE_PASS"
