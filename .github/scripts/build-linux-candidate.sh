#!/usr/bin/env bash
# Build inside PyPA manylinux_2_28 (AlmaLinux 8). Candidate only.
# LGPL source and relinking admission remain separate.
set -euo pipefail
test "$(getconf GNU_LIBC_VERSION)" = "glibc 2.28"
# Keep ordinary AlmaLinux packages independent of the occasionally stale
# EPEL mirror metadata. patchelf is the only required EPEL component.
dnf -y --disablerepo=epel install cmake ninja-build gcc gcc-c++ gmp-devel mpfr-devel zlib-devel
if ! command -v patchelf >/dev/null 2>&1; then
    # Use Fedora's direct official EPEL base URL, not stale third-party metalinks.
    # The literal $basearch is expanded by DNF, not by the shell.
    if ! dnf -y --refresh \
        --setopt='epel.metalink=' --setopt='epel.mirrorlist=' \
        --setopt='epel.baseurl=https://dl.fedoraproject.org/pub/epel/8/Everything/$basearch/' \
        install patchelf; then
        echo 'Official Fedora EPEL direct package fetch failed; trying normal mirrors once.' >&2
        dnf clean metadata
        dnf -y install patchelf
    fi
fi
command -v patchelf >/dev/null 2>&1 || { echo 'patchelf unavailable' >&2; exit 1; }
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
: > build/rpm-dso-owners.txt
for soname in libgmp.so.10 libgmpxx.so.4 libmpfr.so.4; do
    resolved="$(ldd build/gpmc | awk -v name="$soname" '$1 == name { print $3 }')"
    test -n "$resolved" && test -f "$resolved"
    printf '%s original_dso_sha256=%s rpm_owner=' "$soname" "$(sha256sum "$resolved" | cut -d' ' -f1)" >> build/rpm-dso-owners.txt
    rpm -qf "$resolved" --qf '%{NAME} %{VERSION}-%{RELEASE} source_rpm=%{SOURCERPM} license_label=%{LICENSE}\n' >> build/rpm-dso-owners.txt
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
printf 'Original DSO source RPM ownership (not source admission):\n' >> dependencies.txt
cat build/rpm-dso-owners.txt >> dependencies.txt
# Docker mounts the checkout but writes as root: allow host to append provenance.
chown "$HOST_UID:$HOST_GID" dependencies.txt
