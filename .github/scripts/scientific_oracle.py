#!/usr/bin/env python3
"""Independent exhaustive arithmetic oracle for small native GPMC CNFs.

No third-party packages. This intentionally does not import GPMC or reuse its
model-counting code; projections are existential and weights are rational pairs.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import product
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ONE = (Fraction(1), Fraction(0))
ZERO = (Fraction(0), Fraction(0))
TOLERANCE = Fraction(1, 10**34)
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
COMPLEX = re.compile(rf"^({NUMBER})([+-](?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)i$")


def value(re_part: str, im_part: str = "0") -> tuple[Fraction, Fraction]:
    return Fraction(re_part), Fraction(im_part)


def multiply(a: tuple[Fraction, Fraction], b: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction]:
    return a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]


# name, mode, variables, clauses, projected variables, literal weights
CASES = [
    ("unsat", 0, 1, [(1,), (-1,)], (), {}),
    ("mc_or", 0, 2, [(1, 2)], (), {}),
    ("pmc_or", 2, 2, [(1, 2)], (1,), {}),
    ("pmc_existential", 2, 3, [(1, 2), (2, 3)], (1, 3), {}),
    ("complex_unit", 1, 1, [(1,)], (), {1: value("2", "3"), -1: value("7")}),
    ("complex_fraction", 1, 1, [(1,)], (), {1: value("0.125", "-0.2")}),
    ("cancel", 1, 2, [(1,)], (), {2: value("1"), -2: value("-1")}),
    ("projected_complex", 3, 2, [(1, 2)], (1,), {1: value("2", "3"), -1: value("5", "-2")}),
    ("projected_cancel", 3, 2, [(1, 2)], (1,), {1: value("2", "3"), -1: value("-2", "-3")}),
    ("precision_30_digits", 1, 1, [(1,)], (), {1: value("1.000000000000000000000000000001")}),
    ("near_cancel_30_digits", 1, 2, [(1,)], (), {2: value("1"), -2: value("-0.999999999999999999999999999999")}),
]


def satisfying(assignment: tuple[bool, ...], clauses: list[tuple[int, ...]]) -> bool:
    return all(any(assignment[abs(lit) - 1] == (lit > 0) for lit in clause) for clause in clauses)


def oracle(case: tuple) -> tuple[bool, int | tuple[Fraction, Fraction]]:
    _name, mode, size, clauses, projection, weights = case
    sat = [a for a in product((False, True), repeat=size) if satisfying(a, clauses)]
    if mode == 0:
        return bool(sat), len(sat)
    if mode == 2:
        return bool(sat), len({tuple(a[i - 1] for i in projection) for a in sat})

    if mode == 3:
        # Distinct projected assignments, not all satisfying completions.
        distinct = {tuple(a[i - 1] for i in projection) for a in sat}
        assignments = [dict(zip(projection, a)) for a in distinct]
        variables = projection
    else:
        assignments = [dict(enumerate(a, start=1)) for a in sat]
        variables = range(1, size + 1)

    real = Fraction(0)
    imag = Fraction(0)
    for assignment in assignments:
        term = ONE
        for variable in variables:
            lit = variable if assignment[variable] else -variable
            term = multiply(term, weights.get(lit, ONE))
        real += term[0]
        imag += term[1]
    return bool(sat), (real, imag)


def fixture(case: tuple) -> str:
    _name, mode, size, clauses, projection, weights = case
    lines = []
    if mode in (2, 3):
        lines.append("c p show " + " ".join(map(str, projection)) + " 0")
    lines.append(f"p cnf {size} {len(clauses)}")
    for lit, (re_part, im_part) in sorted(weights.items()):
        lines.append(f"c p weight {lit} {float_text(re_part)} {float_text(im_part)} 0")
    lines.extend(" ".join(map(str, clause)) + " 0" for clause in clauses)
    return "\n".join(lines) + "\n"


def float_text(fraction: Fraction) -> str:
    # Every supplied fixture has a terminating base-10 representation. Compute
    # the exact textual decimal, not a binary float approximation.
    denominator = fraction.denominator
    p2 = p5 = 0
    while denominator % 2 == 0:
        denominator //= 2
        p2 += 1
    while denominator % 5 == 0:
        denominator //= 5
        p5 += 1
    if denominator != 1:
        raise ValueError(f"non-terminating decimal fixture: {fraction}")
    scale = max(p2, p5)
    scaled = fraction.numerator * (2 ** (scale - p2)) * (5 ** (scale - p5))
    if scale == 0:
        return str(scaled)
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).zfill(scale + 1)
    return sign + digits[:-scale] + "." + digits[-scale:]


def measured(stdout: str, mode: int) -> int | tuple[Fraction, Fraction]:
    if mode in (0, 2):
        match = re.search(r"^c s exact arb int ([0-9]+)\s*$", stdout, re.MULTILINE)
        if not match:
            raise AssertionError("missing exact integer result:\n" + stdout)
        return int(match.group(1))
    match = re.search(r"^c s exact double prec-sci (.+?)\s*$", stdout, re.MULTILINE)
    if not match:
        raise AssertionError("missing complex result:\n" + stdout)
    parts = COMPLEX.fullmatch(match.group(1).strip())
    if not parts:
        raise AssertionError("malformed complex result: " + match.group(1))
    return Fraction(parts.group(1)), Fraction(parts.group(2))


def main(binary: Path) -> None:
    binary = binary.resolve(strict=True)
    with tempfile.TemporaryDirectory() as dirname:
        for case in CASES:
            name, mode, *_ = case
            path = Path(dirname) / f"{name}.cnf"
            path.write_text(fixture(case), encoding="utf-8")
            run = subprocess.run(
                [str(binary), f"-mode={mode}", "-prec=45", str(path)],
                capture_output=True, text=True, timeout=30, check=True,
            )
            expected_sat, expected = oracle(case)
            status = re.search(r"^s (SATISFIABLE|UNSATISFIABLE)\s*$", run.stdout, re.MULTILINE)
            if status is None or (status.group(1) == "SATISFIABLE") != expected_sat:
                raise AssertionError(f"{name}: SAT status mismatch:\n{run.stdout}")
            observed = measured(run.stdout, mode)
            if isinstance(expected, tuple):
                if not isinstance(observed, tuple) or any(abs(a - b) > TOLERANCE for a, b in zip(observed, expected)):
                    raise AssertionError(f"{name}: expected={expected}, observed={observed}\n{run.stdout}")
            elif observed != expected:
                raise AssertionError(f"{name}: expected={expected}, observed={observed}\n{run.stdout}")
            print(f"ORACLE_PASS {name} mode={mode}")
    print(f"INDEPENDENT_ORACLE_PASS cases={len(CASES)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 scientific_oracle.py /path/to/gpmc")
    main(Path(sys.argv[1]))
