# QOO-227 — Safe native C++ GPMC CodSpeed baseline for QuPRS direct CNF

**Status:** source-pinned CLI science, CodSpeed upload opt-in. Production
C++ solver, QuPRS SolverAdapter, GMP/MPFR settings, release, and normal GPMC
CMake targets are entirely unchanged.

## Why native CLI, not an in-process Google Benchmark

An earlier [in-process Google Benchmark experiment, PR #22](https://github.com/PhysicsQoo/GPMC/pull/22),
used `GPMC::Counter<Complex>` repeatedly in the same program.
It **is not qualified**: four nonzero cases produced denormal garbage
(~6.95e-310) on repeated calls. Google Benchmark's `SkipWithError`
also failed to set a nonzero exit code until explicitly corrected.
[Fail-closed diagnostic](https://github.com/PhysicsQoo/GPMC/actions/runs/43473932368).
Do not merge that invalid in-process measurement or infer GPMC is slow
because its in-process wrapper returned incorrect answers.

The actual QuPRS adapter invokes the original GPMC **native CLI in a
fresh process**. This safe baseline instruments that native executable
via official CodSpeed v5 **exec** harness directly; it does not call GPMC
as a subprocess inside the instrumented Google Benchmark. Thus it
measures real C++ solving without assuming stateful `Counter` reentrancy.
The old in-process investigation remains isolated in Draft PR #22.

## Frozen QuPRS source/semantics

- QuPRS original commit: `0b28736651b3740ed3b201edd2efdef3da541e0d`.
- `test/test_wmc_direct_cnf_golden.py` original blob:
  `d5d9b8ab6e513afd332e34c642a8017b7c415caa`.
- `prepare_direct_cnf.py` checks both **original source blob and HEAD**,
  extracts the real original test functions/weights and emits precisely
  the same six GPMC-format CNF bytes/manifest of SHA256 hashes that the
  Rust side in [RaWMoCS PR #52](https://github.com/PhysicsQoo/RaWMoCS/pull/52)
  also consumes.
- Original six cases: unconstrained = 3/4; forced SAT =
  19/16 − 3i/16; contradictory UNSAT = 0; disjunction =
  −5/16 + 9i/16; XOR-like = 1/2 + 5i/16; Boolean SAT with
  complex cancellation = 0.
- Only **test-defined direct CNF**. These are *not* genuine quantum
  PathSum or Rust WmcManager encoder-emitted miter CNFs. QOO-226
  tracks that missing gate.

## Two complementary measurement modes

1. **Required native process smoke:** each case runs GPMC C++ CLI
   `-mode=1 -prec=30` three times as fresh OS processes, checking
   exact CNF SHA256, SAT status separately from complex zero, and
   the expected printed Full WMC to an explicit MPFR30 comparison
   tolerance. The standalone Python probe records per-call subprocess
   WallTime; data are saved to a 30-day Actions artifact. It includes
   process startup, DIMACS parsing, preprocessing, search and output.
   Short-submillisecond shifts are not statistically meaningful.
2. **Optional CodSpeed Simulation:** `codspeed.yml` contains six
   named **native exec** benchmark commands over the same original
   input bytes. Requires [CodSpeed](https://codspeed.io/) connected
   to `PhysicsQoo/GPMC` and GitHub Actions variable
   `GPMC_CODSPEED_ENABLED=true`. Until connected/opted in,
   the CodSpeed job is expected to **skip**; do not say performance
   was measured by CodSpeed based only on green smoke.

## Reproduce and limits

```sh
python3 benchmarks/quprs/prepare_direct_cnf.py \
  --quprs /path/to/original/pinned-QuPRS \
  --output build-quprs-bench/quprs-cnf
cmake -S . -B build-quprs-bench -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-quprs-bench --target gpmc-bin --parallel 2
python3 benchmarks/quprs/native_process_parity.py \
  --binary build-quprs-bench/gpmc \
  --corpus build-quprs-bench/quprs-cnf --trials 3
# Only when GPMC is connected and authenticated to CodSpeed:
codspeed run -m simulation
```

GPMC here uses **MPFR 30-digit** complex weights; RaWMoCS
counts the **exact finite printed decimal rationals**. Same CNF does
not make the arithmetic guarantees identical. CodSpeed `exec`
GPMC full CLI and Rust Divan in-process benchmark have different
timing boundaries; do not divide the two measurements as a speedup.
[RaWMoCS PR #52](https://github.com/PhysicsQoo/RaWMoCS/pull/52)
also builds a **same-runner native C++ CLI versus Rust CLI** comparison
with independently checked results, fresh-process WallTime and RSS,
to make those comparisons methodologically closer. All six are tiny
test-defined cases, insufficient to claim QuPRS performance parity.
