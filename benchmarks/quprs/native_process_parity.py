#!/usr/bin/env python3
"""Native process-per-case QuPRS direct-CNF GPMC correctness and walltime witness.

Unlike in-process Google Benchmark, every repetition starts the real GPMC CLI
in a new process, precisely the QuPRS integration boundary. Not CodSpeed.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import statistics
import subprocess
import time

NUMBER = r"[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?"
COMPLEX = re.compile(rf"^({NUMBER})([+-](?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?)i$")
LIMIT = Fraction(1, 10**23)


def parse_count(stdout: str, sat: bool) -> tuple[Fraction, Fraction]:
    if not sat:
        return Fraction(0), Fraction(0)
    line = re.search(r"^c s exact double prec-sci (.+?)\\s*$", stdout, re.MULTILINE)
    if line is None:
        raise ValueError("missing GPMC complex count")
    complex_number = COMPLEX.fullmatch(line.group(1).strip())
    if complex_number is None:
        raise ValueError("invalid GPMC complex count: " + line.group(1))
    return Fraction(complex_number.group(1)), Fraction(complex_number.group(2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if not (1 <= args.trials <= 5):
        raise SystemExit("trials must be 1..5")
    manifest = json.loads((args.corpus / "manifest.json").read_text())
    if manifest.get("source") != "QuPRS test-defined direct CNF (NOT PathSum encoder-emitted)":
        raise SystemExit("unexpected test-defined QuPRS source manifest")
    from hashlib import sha256
    records = []
    for entry in manifest["cases"]:
        path = args.corpus / entry["file"]
        if sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"{entry['case']}: CNF digest drift")
        expected_sat = entry["satisfiable"]
        expect = (Fraction(entry["expected_real"]), Fraction(entry["expected_imag"]))
        elapsed = []
        observed = None
        for _ in range(args.trials):
            start = time.perf_counter_ns()
            result = subprocess.run(
                [str(args.binary.resolve()), "-mode=1", "-prec=30", str(path.resolve())],
                capture_output=True, text=True, timeout=10, check=True,
            )
            elapsed.append(time.perf_counter_ns() - start)
            statuses = re.findall(r"^s (SATISFIABLE|UNSATISFIABLE)\\s*$", result.stdout, re.MULTILINE)
            if len(statuses) != 1:
                raise SystemExit(f"{entry['case']}: expected one SAT status; got {statuses}")
            sat = statuses[0] == "SATISFIABLE"
            if sat != expected_sat:
                raise SystemExit(f"{entry['case']}: Boolean SAT status mismatch")
            observed = parse_count(result.stdout, sat)
            if any(abs(a - b) > LIMIT for a, b in zip(observed, expect)):
                raise SystemExit(
                    f"{entry['case']}: expected {expect}, got {observed} "
                    "(not a compatible Full Complex WMC solution)"
                )
        row = {
            "case": entry["case"],
            "sha256": entry["sha256"],
            "satisfiable": expected_sat,
            "observed_real": str(observed[0]),
            "observed_imag": str(observed[1]),
            "wall_ns_samples": elapsed,
            "wall_ns_median": statistics.median(elapsed),
            "timing_boundary": "Python subprocess launch + GPMC CLI parse/preprocess/count + stdout capture",
            "exact_numerical_method": "GPMC MPFR 30 decimal precision, not exact rational",
        }
        records.append(row)
        print(f"NATIVE_CLI_PASS {entry['case']} wall_ns_median={row['wall_ns_median']}")
    evidence = {"source": manifest, "records": records, "trials": args.trials}
    if args.output:
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"GPMC_NATIVE_PROCESS_PARITY_PASS cases={len(records)} trials={args.trials}")


if __name__ == "__main__":
    main()
