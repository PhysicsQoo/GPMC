#!/usr/bin/env python3
"""Source-locked QuPRS direct-CNF fixtures for GPMC/RaWMoCS research only.

These are QuPRS *test-defined* cases, NOT emitted PathSum-miter CNFs.
Uses only pinned original source definitions; does not import QuPRS or pytest.
"""
from __future__ import annotations

import argparse
import ast
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess

SOURCE_COMMIT = "0b28736651b3740ed3b201edd2efdef3da541e0d"
SOURCE_BLOB = "d5d9b8ab6e513afd332e34c642a8017b7c415caa"
SOURCE_PATH = "test/test_wmc_direct_cnf_golden.py"

CASES = (
    ("unconstrained", (), "WEIGHTS", Fraction(3, 4), Fraction(0), True),
    ("forced-sat", ((1,), (-2,)), "WEIGHTS", Fraction(19, 16), Fraction(-3, 16), True),
    ("contradictory-unsat", ((1,), (-1,)), "WEIGHTS", Fraction(0), Fraction(0), False),
    ("disjunction", ((1, 2),), "WEIGHTS", Fraction(-5, 16), Fraction(9, 16), True),
    ("xor", ((1, 2), (-1, -2)), "WEIGHTS", Fraction(1, 2), Fraction(5, 16), True),
    ("complex-cancellation", (), "CANCEL_WEIGHTS", Fraction(0), Fraction(0), True),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quprs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.quprs.resolve()
    head = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != SOURCE_COMMIT:
        raise SystemExit(f"QuPRS HEAD drift: {head} != {SOURCE_COMMIT}")
    actual_blob = subprocess.check_output(
        ["git", "-C", str(repo), "hash-object", SOURCE_PATH], text=True
    ).strip()
    if actual_blob != SOURCE_BLOB:
        raise SystemExit(f"QuPRS test blob drift: {actual_blob} != {SOURCE_BLOB}")

    origin = repo / SOURCE_PATH
    parsed = ast.parse(origin.read_text(encoding="utf-8"), filename=str(origin))
    allowed_functions = {"_multiply", "_exact_count", "_solver_cnf"}
    allowed_variables = {"Weight", "WEIGHTS", "CANCEL_WEIGHTS"}
    body = []
    for node in parsed.body:
        if isinstance(node, ast.ImportFrom) and node.module in ("__future__", "fractions", "itertools"):
            body.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in allowed_variables for t in targets):
                body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in allowed_functions:
            body.append(node)
    env = {"__name__": "_pinned_quprs_direct_cnf"}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(origin), "exec"), env)
    if not allowed_functions.issubset(env) or not {"WEIGHTS", "CANCEL_WEIGHTS"}.issubset(env):
        raise SystemExit("original source definitions missing")

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "QuPRS test-defined direct CNF (NOT PathSum encoder-emitted)",
        "quprs_commit": head,
        "quprs_test_blob": actual_blob,
        "dialect": "gpmc",
        "cases": [],
    }
    for case, clauses, weight_name, real, imag, satisfiable in CASES:
        weights = env[weight_name]
        observed = env["_exact_count"](clauses, weights)
        if observed != complex(float(real), float(imag)):
            raise SystemExit(f"source mathematical oracle drift for {case}: {observed}")
        count = sum(
            all(any(bits[abs(literal) - 1] == (literal > 0) for literal in clause) for clause in clauses)
            for bits in product((False, True), repeat=2)
        )
        if (count != 0) != satisfiable:
            raise SystemExit(f"independent SAT status mismatch: {case}")
        raw = env["_solver_cnf"]("gpmc", clauses, weights)
        if not raw.startswith(f"p cnf 2 {len(clauses)}\nc t wmc\n"):
            raise SystemExit(f"unexpected GPMC grammar: {case}")
        data = raw.encode("utf-8")
        output = args.output / f"{case}.cnf"
        output.write_bytes(data)
        manifest["cases"].append({
            "case": case,
            "file": output.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "variables": 2,
            "clauses": len(clauses),
            "satisfiable": satisfiable,
            "expected_real": str(real),
            "expected_imag": str(imag),
        })
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"SOURCE_LOCK_PASS commit={head} blob={actual_blob} files={len(CASES)}")


if __name__ == "__main__":
    main()
