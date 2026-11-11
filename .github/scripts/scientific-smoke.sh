#!/usr/bin/env bash
# Small independent scientific oracles for the native GPMC executable.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/gpmc" >&2
  exit 2
fi
binary="$1"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cat > "$tmp/unsat.cnf" <<'CNF'
p cnf 1 2
1 0
-1 0
CNF
cat > "$tmp/three_models.cnf" <<'CNF'
p cnf 2 1
1 2 0
CNF
cat > "$tmp/projected.cnf" <<'CNF'
c p show 1 0
p cnf 2 1
1 2 0
CNF
cat > "$tmp/complex_unit.cnf" <<'CNF'
p cnf 1 1
c p weight 1 2 3 0
c p weight -1 7 0 0
1 0
CNF
cat > "$tmp/projected_complex_unit.cnf" <<'CNF'
c p show 1 0
p cnf 1 1
c p weight 1 2 3 0
c p weight -1 7 0 0
1 0
CNF

run() {
  local name="$1" mode="$2"
  "$binary" "-mode=$mode" "-prec=30" "$tmp/$name.cnf" > "$tmp/$name.$mode.out"
}
check_int() {
  local name="$1" mode="$2" expected="$3"
  run "$name" "$mode"
  if ! grep -Eq "^c s exact arb int $expected\r?$" "$tmp/$name.$mode.out"; then
    echo "Scientific oracle failed: $name mode=$mode expected integer=$expected" >&2
    cat "$tmp/$name.$mode.out" >&2
    exit 1
  fi
  echo "SCIENCE_PASS $name mode=$mode integer=$expected"
}
check_complex() {
  local name="$1" mode="$2"
  run "$name" "$mode"
  # Integer-valued complex oracle: exactly 2+3i, allowing trailing decimal zeros.
  local num2='2(\.0+)?([eE]\+?0+)?'
  local num3='3(\.0+)?([eE]\+?0+)?'
  if ! grep -Eq "^c s exact double prec-sci ${num2}\+${num3}i\r?$" "$tmp/$name.$mode.out"; then
    echo "Scientific oracle failed: $name mode=$mode expected complex=2+3i" >&2
    cat "$tmp/$name.$mode.out" >&2
    exit 1
  fi
  echo "SCIENCE_PASS $name mode=$mode complex=2+3i"
}

check_int unsat 0 0
check_int three_models 0 3
check_int projected 2 2
check_complex complex_unit 1
check_complex projected_complex_unit 3
echo "SCIENTIFIC_SMOKE_PASS"
