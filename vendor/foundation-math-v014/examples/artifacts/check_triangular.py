#!/usr/bin/env python3
"""Finite exact-arithmetic regression test, not a proof of a universal claim."""


def main() -> int:
    checked = 0
    for n in range(1001):
        left = 2 * sum(range(1, n + 1))
        right = n * (n + 1)
        if left != right:
            print(f"FAIL: n={n}, left={left}, right={right}")
            return 1
        checked += 1
    if sum(range(1, 11)) != 55:
        print("FAIL: the first-ten deduction disagrees with direct summation.")
        return 1
    print(f"PASS: {checked} finite cases (0..1000), plus the first-ten deduction.")
    print("Exact integer arithmetic only; this finite test is not a universal proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
