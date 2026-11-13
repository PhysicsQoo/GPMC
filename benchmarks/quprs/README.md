# GPMC C++ CodSpeed research — QOO-227

This is a **nonproduction**, opt-in harness for GPMC's actual C++ full complex-WMC
`Counter<Complex>`; it does not alter GPMC's counting engine, command-line
interface, release workflow, QuPRS SolverAdapter, or default GPMC selection.

## Source of truth: QuPRS test-defined *direct* CNFs

The Python stdlib-only generator `prepare_direct_cnf.py` reads the actual
source methods and weights in the pinned
[QuPRS test](https://github.com/PhysicsQoo/QuPRS/blob/0b28736651b3740ed3b201edd2efdef3da541e0d/test/test_wmc_direct_cnf_golden.py).
It checks both the QuPRS commit
`0b28736651b3740ed3b201edd2efdef3da541e0d` and original Git blob
`d5d9b8ab6e513afd332e34c642a8017b7c415caa` **before** emitting six
GPMC-format files. It checks source-independent SAT satisfiability, the original
test's mathematical Full Complex WMC oracle, and each benchmark's hard-coded
expected result; the output manifest records exact SHA-256 of each CNF input.

| Case | SAT? | Expected exact Full WMC of printed weights |
| --- | --- | --- |
| unconstrained | yes | 3/4 |
| forced-sat | yes | 19/16 - 3i/16 |
| contradictory-unsat | no | 0 |
| disjunction | yes | -5/16 + 9i/16 |
| xor | yes | 1/2 + 5i/16 |
| complex-cancellation | yes | 0 |

All test-source fractions are binary64-exact; the GPMC GPMC-format decimal
tokens preserve their numeric values. For different phase coefficients in
actual QuPRS circuits, the printed decimals are **not exact quantum phases**.
In particular, SAT-with-zero-WMC is not UNSAT.

**Scope boundary:** None of these six files is emitted by the actual
PathSum/WmcManager circuit encoder. Real circuit-generated CNF collection
continues in [QOO-226](https://linear.app/qoogohome/issue/QOO-226).
Do not use this suite to claim RaWMoCS outperforms GPMC in quantum examples.

## Timed semantics and correctness gate

`BM_QuPRSDirectCnfFullPipeline` constructs a fresh GPMC
`Counter<Complex>` every iteration and includes its in-process
DIMACS load, default preprocessing, variable-score setup (if needed), and
countModels (if preprocessing did not already solve the instance).
The source CNF is read into memory and the fixture's expected result is checked
**before** timing. The checked result has separate Boolean SAT status and
Full WMC values. The benchmark checks each iteration and errors on a mismatch;
using a subprocess for CodSpeed Simulation is deliberately avoided.

This is **not** a counting-kernel-only benchmark: small CNFs can be solved
entirely by preprocessing. GPMC uses **MPFR 30-digit precision** by default
for complex WMC in QuPRS; RaWMoCS uses exact Gaussian rational arithmetic
over printed decimal tokens. Their performance and numeric guarantees are
not interchangeable, and the CodSpeed names must not be compared across
different timed boundaries or isolated repositories without controls.

## CI and opt-in results

The [workflow](../../.github/workflows/quprs-codspeed-cpp.yml):
1. Builds `gpmc_quprs_cnf_bench` and executes all six source-locked cases
   with `CODSPEED_MODE=off`, *even when CodSpeed is not connected*.
2. Archives `manifest.json` and the original generated GPMC CNF bytes.
3. Runs CodSpeed C++ Google Benchmark Simulation on a separate job **only if**
   the GPMC repository is connected in CodSpeed and its GitHub Actions
   repository variable `GPMC_CODSPEED_ENABLED=true`. OIDC uses
   `CodSpeedHQ/action@v5` and `id-token: write`.

The CodSpeed C++ compatibility layer is fetched only when the CMake
`GPMC_BUILD_QU_PRS_BENCHMARKS=ON` option is set, and pinned to upstream
`CodSpeedHQ/codspeed-cpp@76985b6f02c49fe70393c50fcca6e9748f300caa`.
The normal GPMC CMake build is unchanged. Green smoke builds are **not**
CodSpeed performance measurements; green CodSpeed CI alone does not prove
solver superiority or a CPU speedup.

### Reproduce (Linux)

```sh
# Supply a QuPRS checkout at the exact pinned commit.
python3 benchmarks/quprs/prepare_direct_cnf.py \
  --quprs /path/to/pinned/QuPRS --output /tmp/gpmc-quprs-cnf

cmake -S . -B build-quprs-bench -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DGPMC_BUILD_QU_PRS_BENCHMARKS=ON -DCODSPEED_MODE=off
cmake --build build-quprs-bench --target gpmc_quprs_cnf_bench --parallel 2
GPMC_QU_PRS_CNF_DIR=/tmp/gpmc-quprs-cnf \
  ./build-quprs-bench/gpmc_quprs_cnf_bench \
  --benchmark_filter=BM_QuPRSDirectCnfFullPipeline --benchmark_min_time=0.03s
```

## Fair external comparison still required

The corresponding RaWMoCS exact Full WMC oracle is implemented in
[QOO-225 / PR #51](https://github.com/PhysicsQoo/RaWMoCS/pull/51), but
**there is no paired GPMC-versus-RaWMoCS CodSpeed result yet**. GPMC's
C++ Google Benchmark and RaWMoCS's Rust Divan are separate CodSpeed suites.
For a rigorous head-to-head, replay exact same input bytes, same Full WMC
semantics and controlled precision/error acceptance, compare equivalent
timed spans and instrumentation modes, record independent correctness,
and independently measure fresh-process WallTime/VmHWM including process
startup. Include nontrivial authentic QuPRS-encoder CNFs and negative
controls before any claim of performance parity or replacement.

## QOO-227 field discovery: in-process repeated-count instability

**DO NOT USE the C++ Google Benchmark's repeated Counter<Complex>
result as a valid measurement yet.** [Initial CI native run
43472794121](https://github.com/PhysicsQoo/GPMC/actions/runs/43472794121)
returned a nominally green workflow but four of the six Google Bench
instances emitted `ERROR OCCURRED` from the *measured* iterations.
Google Benchmark's `SkipWithError` did not set a nonzero process status,
so the smoke's prior green status was a **false positive**.
[Follow-up run 43473932368](https://github.com/PhysicsQoo/GPMC/actions/runs/43473932368)
fixed that error exit and correctly failed; four nonzero counts were
read as denormal garbage `~6.95e-310` on repeated in-process calls.
The source-defined SAT-but-zero controls had also passed an overly
loose numeric zero tolerance. This problem cannot be dismissed as
FP rounding and must not be called source parity.

The regular CI now **builds** the C++ Google Benchmark adapter but
does **not** execute this known-invalid repeated in-process path,
unless `workflow_dispatch` is explicitly invoked with
`in_process_probe=true`; that diagnostic must fail closed if incorrect.
No production GPMC code was modified to mask this behavior.

The admitted alternative is the **real GPMC C++ native CLI**, with
each source-pinned CNF run in an independent subprocess, like
QuPRS's actual solver adapter. The separate native CLI science smoke
uses `native_process_parity.py` to check one SAT verdict and a precise
complex count for all six cases, digest-checking the original input,
with repeated process-spawn WallTime records. The scoped CodSpeed
config `codspeed.yml` uses the official `exec` harness: it directly
instruments each native GPMC executable as a new program in
Simulation mode. This provides a way to benchmark **C++ GPMC itself**
without introducing a logically invalid in-process counting wrapper.

**Important comparison boundary:** GPMC's CodSpeed `exec` is a native
fresh program and includes a different initialization span from
RaWMoCS's existing in-process Divan. Do not divide these numbers to
make an apparent head-to-head speedup. The next bridge must add a
corresponding RaWMoCS CLI `exec` or same-CLI-span WallTime and RSS
study, and source-backed QuPRS encoder-generated CNFs (QOO-226).
GPMC repo must be connected to CodSpeed before `GPMC_CODSPEED_ENABLED`
can be activated; the optional upload job is expected to SKIP until then.
