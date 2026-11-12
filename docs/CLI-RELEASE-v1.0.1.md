# GPMC v1.0.1 — Linux MPFR runtime fix

This Linux-only patch release corrects the unusable Linux executables in
PhysicsQoo/GPMC v1.0.0. Both old Linux assets required `libmpfr.so.4`,
which is not supplied by the normal Ubuntu 22.04/24.04 packages even after
installing `libmpfr-dev`.

The new **x86_64** and **ARM64** CLI binaries are built natively on Ubuntu
22.04 (glibc 2.35), link to **`libmpfr.so.6`** and are tested by executing
the **actual extracted release archives** on Ubuntu 22.04 and Ubuntu 24.04.
The archive contains the CLI executable, source and dependency provenance,
checksums and license notices. It deliberately does not bundle runtime
shared libraries.

For Ubuntu 22.04 or 24.04:

```sh
sudo apt-get install libmpfr6 libgmp10 libgmpxx4ldbl zlib1g
```

Download the `gpmc-cli-v1.0.1-linux-ubuntu22-*.tar.gz` archive for your
architecture and verify it using `SHA256SUMS.txt`.

The glibc floor has changed from the v1.0.0 AlmaLinux 8 build to
**glibc 2.35**. RHEL 8/9, Ubuntu 20.04 and other older systems are not
covered by these Linux v1.0.1 binaries. Build from source on such systems.

**macOS and Windows:** these binaries have not changed. Continue to use
[their v1.0.0 assets](https://github.com/PhysicsQoo/GPMC/releases/tag/v1.0.0).
This is not a new macOS notarization or Windows distribution.

This is a PhysicsQoo-maintained independent release, based on the original
GPMC by Kenji Hashimoto; it is not an upstream release. No solver algorithms
have been changed.
