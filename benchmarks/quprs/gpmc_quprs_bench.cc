// QOO-227: GPMC's existing in-process Counter<Complex> on the original,
// source-pinned QuPRS *test-defined* direct weighted CNFs. Not miter emission.
#include <benchmark/benchmark.h>

#include <mpfr/mpreal.h>
#include "c-mpfr/ComplexMPFR.h"
#include "core/Config.h"
#include "core/Counter.h"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

struct Observed {
    double real;
    double imag;
    bool sat;
};

// The timed path includes parsing, default preprocessing, and full WMC.
// It excludes process startup and fixture-generation; unlike a subprocess
// wrapper it is visible to CodSpeed's C++ CPU Simulation instrumentation.
Observed count_full_pipeline(const std::string& cnf) {
    GPMC::Configuration cfg;
    cfg.cntr.mode = GPMC::WMC;
    cfg.cm.weighted = true;
    cfg.cntr.watchCand = true;
    cfg.cntr.precision = 30;  // Same effective precision as QuPRS GPMC.
    GPMC::Counter<Complex> solver(cfg);
    std::istringstream input(cnf);
    solver.load(input);
    const bool simplified = solver.preprocess();
    if (!simplified) {
        solver.setExtraVarScore();
        if (!solver.countModels()) {
            throw std::runtime_error("GPMC returned incomplete/UNKNOWN");
        }
    }
    const Complex& value = solver.getMC();
    return {value.real.toDouble(), value.imag.toDouble(), solver.sat};
}

std::string read_source_cnf(const char* case_id) {
    const char* root = std::getenv("GPMC_QU_PRS_CNF_DIR");
    if (root == nullptr || *root == '\0') {
        throw std::runtime_error("GPMC_QU_PRS_CNF_DIR is required");
    }
    const std::string filename = std::string(root) + "/" + case_id + ".cnf";
    std::ifstream in(filename, std::ios::binary);
    if (!in) {
        throw std::runtime_error("missing pinned QuPRS fixture: " + filename);
    }
    std::ostringstream contents;
    contents << in.rdbuf();
    const std::string raw = contents.str();
    if (raw.find("p cnf 2 ") != 0 || raw.find("c t wmc") == std::string::npos) {
        throw std::runtime_error("invalid direct-CNF source: " + filename);
    }
    return raw;
}

bool matches(const Observed& value, bool sat, double real, double imag) {
    return value.sat == sat && std::isfinite(value.real) &&
           std::isfinite(value.imag) &&
           std::abs(value.real - real) <= 1e-10 &&
           std::abs(value.imag - imag) <= 1e-10;
}

bool any_benchmark_error = false;

void reject(benchmark::State& state, const char* label,
            const Observed& got, bool sat, double real, double imag) {
    any_benchmark_error = true;
    std::ostringstream detail;
    detail << label << " got SAT=" << got.sat
           << " complex=(" << got.real << ", " << got.imag << ")"
           << " expected SAT=" << sat
           << " complex=(" << real << ", " << imag << ")";
    state.SkipWithError(detail.str().c_str());
}

void BM_QuPRSDirectCnfFullPipeline(benchmark::State& state,
                                  const char* case_id, bool sat,
                                  double real, double imag) {
    const std::string cnf = read_source_cnf(case_id);
    // Verify once before measurement, and then at EVERY iteration. A green
    // exit is disallowed if native Google Benchmark reports any skipped error.
    const auto before = count_full_pipeline(cnf);
    if (!matches(before, sat, real, imag)) {
        reject(state, case_id, before, sat, real, imag);
        return;
    }
    for (auto _ : state) {
        auto result = count_full_pipeline(cnf);
        benchmark::DoNotOptimize(result.real);
        benchmark::DoNotOptimize(result.imag);
        if (!matches(result, sat, real, imag)) {
            reject(state, case_id, result, sat, real, imag);
            break;
        }
    }
}

}  // namespace

BENCHMARK_CAPTURE(BM_QuPRSDirectCnfFullPipeline, unconstrained,
                  "unconstrained", true, 0.75, 0.0);
BENCHMARK_CAPTURE(BM_QuPRSDirectCnfFullPipeline, forced_sat,
                  "forced-sat", true, 1.1875, -0.1875);
BENCHMARK_CAPTURE(BM_QuPRSDirectCnfFullPipeline, contradictory_unsat,
                  "contradictory-unsat", false, 0.0, 0.0);
BENCHMARK_CAPTURE(BM_QuPRSDirectCnfFullPipeline, disjunction,
                  "disjunction", true, -0.3125, 0.5625);
BENCHMARK_CAPTURE(BM_QuPRSDirectCnfFullPipeline, xor,
                  "xor", true, 0.5, 0.3125);
BENCHMARK_CAPTURE(BM_QuPRSDirectCnfFullPipeline, complex_cancellation,
                  "complex-cancellation", true, 0.0, 0.0);

int main(int argc, char** argv) {
    mpfr::mpreal::set_default_prec(mpfr::digits2bits(30));
    benchmark::Initialize(&argc, argv);
    if (benchmark::ReportUnrecognizedArguments(argc, argv)) {
        return 2;
    }
    benchmark::RunSpecifiedBenchmarks();
    return any_benchmark_error ? 1 : 0;
}
