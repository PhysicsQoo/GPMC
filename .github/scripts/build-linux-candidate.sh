#!/usr/bin/env bash
# Executed inside the official PyPA manylinux_2_28 (AlmaLinux 8) image.
# This is a source-pinned qualification candidate, NOT a distribution approval.
set -euo pipefail

test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.28"
dnf -y install cmake ninja-build gmp-devel mpfr-devel zlib-devel
cmake --version | head -n 1
c++ --version | head -n 1
cmake --preset release
cmake --build --preset release --parallel 2
test -x build/gpmc
bash .github/scripts/scientific-smoke.sh build/gpmc
/opt/python/cp312-cp312/bin/python .github/scripts/scientific_oracle.py build/gpmc
ldd build/gpmc > dependencies.txt
if grep -F 'not found' dependencies.txt; then
    echo "Unresolved runtime libraries inside the manylinux builder" >&2
    exit 1
fi
rpm -q gmp gmp-devel mpfr mpfr-devel zlib zlib-devel >> dependencies.txt

# Builder is root inside Docker. Return provenance to the host runner account
# so subsequent SHA checks can append the resolved image digest.
if [[ -n "${HOST_UID:-}" && -n "${HOST_GID:-}" ]]; then
    chown "$HOST_UID:$HOST_GID" dependencies.txt
fi
