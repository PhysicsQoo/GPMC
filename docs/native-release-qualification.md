# Native binary Release qualification

GPMC native build jobs produce **candidate artifacts**, not a redistribution
approval. A public GitHub Release remains a separate manual decision after
source, runtime, license, signing, and downstream acceptance gates.

## Six-platform candidate policy

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
- Windows 11 ARM64: build native MSYS2 CLANGARM64 PE32+ (Machine 0xAA64) on
  GitHub's Windows ARM runner, using ARM64 Clang/GMP/MPFR packages. Bundle
  the recursive ARM64 DLL closure next to the executable; validate the
  precise source SHA, executable and DLL architectures/hashes, 11-case
  independent oracle, and extracted native execution without MSYS2 PATH.
  This is a separately admitted sixth target: Windows x64 and ARM64
  candidates cannot be interchanged or treated as evidence for a QuPRS wheel.

The main native release workflow qualifies all six targets from one exact
source SHA and checks the archive and executable/library hashes. It creates
**only unpublished draft Releases** for explicit version tags. Actions
qualification artifacts are not formal releases.

Native Windows ARM64 has passed a separate technical proof of concept, and is
now included in the unified six-platform candidate qualification. If its
signing, source, license, minimum-OS or clean-target gates fail, the release
owner may **explicitly revert the optional ARM64 candidate** and restore the
five-platform draft plan; never silently omit an asset from a six-platform
tag or mislabel x64 as ARM64.


## Redistribution evidence: source and license admission

The separately generated per-archive `*.tar.gz.redistribution.json` file is an
**inventory of actual packaged executable and library bytes** (SHA-256, source
commit, target, included notice files and builder dependency metadata). It is
attached only to an **unpublished Draft** and is not a license clearance.
The candidate workflow verifies that each sidecar matches its precise archive
and includes it in the draft checksums. Run the offline negative-contract tests
before depending on this evidence.

No `distribution_admitted=true` value may be inferred from CI success, a
package name, a formula, an upstream license webpage, or bundled
`mpfr/copying.txt`. Some vendored licenses reference additional components;
check what was actually compiled and shipped. All source correspondence fields
remain explicitly unresolved until reviewed against the specific **packaged
binary bytes**. The sidecar's upstream license descriptions are *research
hints*, not licenses determined for a particular patched package.

Build candidates additionally record local runtime package-manager versions and
ownership: Linux original library DSO SHA and RPM Source RPM label; Windows
each bundled DLL's pacman owner/version; and macOS the installed Homebrew GMP
and MPFR formula versions. These are evidence *hints* linked to the candidate
bytes, not source archive/patch hashes or legal redistribution permission.

### Actual-package source correspondence (must be recorded separately)

For **every** bundled `.so`, `.dylib`, `.dll` and any statically linked
runtime, the release reviewer must produce and retain:

1. Exact filename and SHA-256 bound to the candidate archive and target.
2. Installed binary package owner, full version/revision and build/repository
   identity. Linux: RPM ownership and Source RPM/patch list; macOS: actual
   Homebrew installed bottle/formula revision and its source/patch references;
   Windows: `pacman -Qo` on the **original** installed DLL (not its copied
   archive path), `pacman -Qi`, package build recipe and source hashes.
3. Corresponding, reproducibly retrievable source archive + patches or
   equivalent complete source **for the precise shipped library version**,
   checksum, durable URL/asset and applicable copyright/NOTICE/license texts.
4. An independent reviewer sign-off on relevant LGPL/GPL or other license
   obligations. GMP/GMPXX, MPFR, GCC/MinGW/LLVM runtimes and zlib must be
   assessed by the actual closure, not by a hardcoded three-library assumption.
5. A real replacement/relinking test using a separately built, ABI-compatible
   modified LGPL shared library (not a byte-for-byte copy) plus instructions
   that a recipient can actually follow.

Do not treat ephemeral Actions Artifacts as adequate long-term corresponding
source delivery. Source and notices must remain obtainable with the publicly
distributed asset; record the checked source hashes in the release evidence.
Source-archive provenance and legal rights cannot be established from the
existing per-file SHA evidence alone.

Authoritative starting points:
- GNU GMP copying conditions: https://gmplib.org/manual/Copying
- GNU MPFR license: https://www.mpfr.org/
- MSYS2 package ownership and build metadata:
  https://www.msys2.org/docs/package-management/
- MSYS2 UCRT64/CLANGARM64 package prefixes:
  https://www.msys2.org/docs/package-naming/

### macOS signed-runtime and notarization admission

The current relocatable `@loader_path`/ad-hoc signed tests **do not certify**
a Developer ID signature, Hardened Runtime, replacement under Library
Validation, Gatekeeper acceptance, secure timestamp, or notarization.

Before public release, use controlled Developer ID Application credentials to
sign *all* executable code with Hardened Runtime and timestamp. Evaluate
Library Validation on the **signed** executable. Apple's default restriction
may prevent loading user-replaced GMP/MPFR dylibs signed by another developer.
If necessary, assess `com.apple.security.cs.disable-library-validation` only
after an explicit security review: Apple warns that Gatekeeper adds scrutiny
when that entitlement is used. Alternatively document and **actually test** a
compliant relink/redistribution path without weakening security. Neither
approach is assumed to be approved merely because an entitlement is listed.

Test a distinct modified ABI-compatible LGPL dylib under the intended
Developer ID/Hardened Runtime configuration, not only the original bytes.
Then notarize the final supported distribution container through
`xcrun notarytool`, retain accepted submission evidence, and validate
Gatekeeper on a clean macOS 15 target. Observe that the existing `.tar.gz`
qualification archive is **not** itself a claimed notarized container; its
signing/notarization packaging decision remains open.

Apple references:
- https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation
- https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- https://developer.apple.com/documentation/security/customizing-the-notarization-workflow

**Admission decision:** until every required source/notice/signature and
replacement test is evidenced, keep `distribution_admitted=false`, leave
the PR in Draft, do not make a public Release and do not switch the QuPRS
consumer. Recording an incomplete inventory is useful progress, not approval.


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
