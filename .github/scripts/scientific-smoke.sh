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


# Cancellation of two satisfying assignments (x is fixed, y is free).
cat > "$tmp/complex_cancel.cnf" <<'CNF'
p cnf 2 1
c p weight 1 1 0 0
c p weight -1 1 0 0
c p weight 2 1 0 0
c p weight -2 -1 0 0
1 0
CNF

# Existential projection must count each projected x assignment only once.
# x=true: 2+3i, x=false: 5-2i, hence projected WMC=7+i.
cat > "$tmp/projected_weighted.cnf" <<'CNF'
c p show 1 0
p cnf 2 1
c p weight 1 2 3 0
c p weight -1 5 -2 0
1 2 0
CNF

# Same existential projection, but the two projected assignments cancel.
cat > "$tmp/projected_cancel.cnf" <<'CNF'
c p show 1 0
p cnf 2 1
c p weight 1 2 3 0
c p weight -1 -2 -3 0
1 2 0
CNF

# Preserve a source weight beyond IEEE-754 f64's decimal precision.
cat > "$tmp/high_precision.cnf" <<'CNF'
p cnf 1 1
c p weight 1 1.000000000000000000000000000001 0 0
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

check_complex_exact() {
  local name="$1" mode="$2" expected="$3"
  run "$name" "$mode"
  if ! grep -Fq "c s exact double prec-sci $expected" "$tmp/$name.$mode.out"; then
    echo "Scientific oracle failed: $name mode=$mode expected complex=$expected" >&2
    cat "$tmp/$name.$mode.out" >&2
    exit 1
  fi
  echo "SCIENCE_PASS $name mode=$mode complex=$expected"
}

check_high_precision() {
  "$binary" -mode=1 -prec=45 "$tmp/high_precision.cnf" > "$tmp/high_precision.out"
  if ! grep -Fq 'c s exact double prec-sci 1.000000000000000000000000000001' "$tmp/high_precision.out"; then
    echo "Scientific precision oracle failed: 1 + 10^-30 must retain its 30th fractional digit" >&2
    cat "$tmp/high_precision.out" >&2
    exit 1
  fi
  echo "SCIENCE_PASS high_precision mode=1 30th_fractional_digit_preserved"
}

check_complex_exact complex_cancel 1 '0+0i'
check_complex_exact projected_weighted 3 '7+1i'
check_complex_exact projected_cancel 3 '0+0i'
check_high_precision

echo "SCIENTIFIC_SMOKE_PASS"
