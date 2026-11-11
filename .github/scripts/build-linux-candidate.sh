#!/usr/bin/env bash
# Build inside PyPA manylinux_2_28 (AlmaLinux 8). Candidate only.
# LGPL source and relinking admission remain separate.
set -euo pipefail
test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.28"
dnf -y install cmake ninja-build gcc gcc-c++ patchelf gmp-devel mpfr-devel zlib-devel
# Use AlmaLinux 8 system compiler to avoid GCC toolset 14 libstdc++ demands.
test -x /usr/bin/gcc
test -x /usr/bin/g++
export CC=/usr/bin/gcc CXX=/usr/bin/g++
"$CXX" --version | head -n 1
cmake --preset release
cmake --build --preset release --parallel 2
test -x build/gpmc
bash .github/scripts/scientific-smoke.sh build/gpmc
/opt/python/cp312-cp312/bin/python .github/scripts/scientific_oracle.py build/gpmc
mkdir -p build/libs
for soname in libgmp.so.10 libgmpxx.so.4 libmpfr.so.4; do
    resolved="$(ldd build/gpmc | awk -v name="$soname" '$1 == name { print $3 }')"
    test -n "$resolved" && test -f "$resolved"
    install -m 0644 "$resolved" "build/libs/$soname"
done
# Binary and its bundled LGPL libraries remain independently replaceable.
patchelf --set-rpath '$ORIGIN/libs' build/gpmc
for library in build/libs/*.so.*; do
    patchelf --set-rpath '$ORIGIN' "$library"
done
ldd build/gpmc > dependencies.txt
if grep -F 'not found' dependencies.txt; then
    echo "Unresolved bundled runtime libraries" >&2
    exit 1
fi
for soname in libgmp.so.10 libgmpxx.so.4 libmpfr.so.4; do
    grep -F "build/libs/$soname" dependencies.txt
done
rpm -q gmp gmp-devel mpfr mpfr-devel zlib zlib-devel gcc gcc-c++ >> dependencies.txt
# Docker mounts the checkout but writes as root: allow host to append provenance.
chown "$HOST_UID:$HOST_GID" dependencies.txt
