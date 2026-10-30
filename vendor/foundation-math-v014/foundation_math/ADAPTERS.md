# Exact arithmetic and restricted Lean adapter

These are deterministic standard-library Python tools for an agentic mathematician.
They do not call a model, use credentials, execute task prose, install software, or
access the network. A successful computation is not automatically a theorem.

The separately callable polynomial adapter is documented in
[POLYNOMIAL-DOMAIN.md](../docs/POLYNOMIAL-DOMAIN.md). v0.3 connects it to the
[typed work queue](../docs/DOMAIN-RUNTIME.md). It does not change the scalar
contract, extend the restricted Lean grammar below, or integrate Lean receipts
into goal acceptance.

## Calculator contract

```python
from foundation_math.calculator import calculate
receipt = calculate({
    "domain": "Q",
    "operation": "add",
    "operands": [{"numerator": 1, "denominator": 2},
                 {"numerator": 1, "denominator": 3}],
})
assert receipt["result"] == {"domain": "Q", "numerator": 5, "denominator": 6}
```

`CalculationRequest(domain, operation, operands)` is an equivalent typed API.
Inputs are JSON integers or exact numerator/denominator objects, never floating
point, booleans, expressions, or executable strings. Rationals are normalized
with a positive denominator. `Z` means integers; `Q` means rationals.

Operations are binary `add`, `subtract`, `multiply`, `divide`, `power`, and unary
`negate`. Integer division must have an integer result; there is no truncation or
automatic domain change. Exponents must be integers. Negative exponents are
supported only in `Q`, with nonzero base. Zero raised to zero or a negative power
is undefined by this tool's contract. Division by zero and unsupported inputs
produce structured errors.

Inputs have a 4096-bit limit, results a 12000-bit limit, and absolute exponents a
10000 limit. Power checks use a conservative bit upper bound before computation;
some large results that would fit may therefore be rejected. The result bound
also stays below CPython's default decimal-serialization limit; a stricter host
limit becomes a structured `representation_limit` error, not a global setting
change.

Successful receipts preserve original input, normalized request, exact result,
Python/backend/adapter versions, scope, and SHA-256 hashes of input, request,
result, and adapter source. Invalid requests that cannot be represented as valid
bounded input have null input/request. Hashes bind bytes or canonical JSON under
this schema; they are not signatures and cannot authenticate an untrusted receipt.
A verifier must replay the exact request and bind it to the intended claim.

## Restricted Lean contract

```python
from foundation_math.lean_adapter import LeanAdapter, LeanRequest
adapter = LeanAdapter(".")
print(adapter.status())  # Inspection only; no executable is run here.
receipt = adapter.verify(LeanRequest("examples/ExactSmoke.lean", "exact_addition"))
```

An explicit `executable` may select an already-installed trusted native Lean 4
binary. Elan proxies are not invoked because they can download toolchains.
`test_mode=True` permits controlled test executables but can only yield
`simulated`, never `passed` or formal-proof acceptance. Do not make executable
selection or test mode controllable by an untrusted problem proposal.

The `closed-arithmetic-v1` profile accepts exactly one theorem:

```lean
theorem exact_addition : (1 : Int) + 1 = 2 := by decide
```

The statement must be a closed arithmetic equality or order relation with one
explicit `Nat` or `Int` domain. Numerals, parentheses, unary minus, addition,
subtraction, and multiplication are the only expressions. Proofs may use only
`by rfl` or `by decide`. `Nat` subtraction has Lean's natural-number semantics,
not integer subtraction. The profile supports no variables, quantifiers,
rationals, real numbers, division, powers, imports, custom tactics, commands,
macros, strings, or quoted/Unicode identifiers. It handles line comments and
nested block comments; `sorry`, `admit`, and `sorryAx` outside comments are
rejected. This is an intentionally tiny grammar, not a full Lean lexer or a
security proof about general Lean source.

Source paths must resolve to regular `.lean` files inside the configured
workspace. The adapter snapshots the input, adds its own `#print axioms`, then
passes precisely those bytes to the native executable with argument arrays,
`--stdin`, and no shell. A private temporary working directory remains inside
the workspace. The child's environment does not inherit credentials, Lean
search-path overrides, or dynamic-loader overrides. Source size, numeral size,
syntax depth, token count, and each subprocess's wall-clock time are bounded.
This is not an OS-level memory/output/network sandbox. Trusted native Lean and
its installed core library remain a prerequisite.

A `passed` receipt requires a successful Lean 4 version check, exit code zero,
no extra diagnostics, and exactly one recognized axiom report using only
`propext`, `Classical.choice`, or `Quot.sound` (or no axioms). Unknown formats fail
closed. Receipts retain checked source, original and checked-source hashes,
executable hash, version, command, output, output hashes, statement, and axioms.
Missing Lean returns `unavailable`; unsupported source `rejected`; errors
`failed`; timeout `timeout`. These states are never promoted to proof.

Acceptance concerns only the recorded Lean statement under the stated trust
assumptions. This adapter does not establish that it matches an informal claim,
lock/hash all core library files, run independent kernel replay, or implement a
proof-marketplace adversarial verifier. The current project has no observed
real-Lean pass: the optional smoke is skipped when no trusted backend exists.

## Tests and checked references

Run `python -m unittest discover -s tests -p 'test_calculator_adapters.py' -v`.
Process-integration tests use a controlled Python stub, explicitly marked as not
Lean. The separately named optional real-Lean smoke runs only when available.

Official sources consulted on 2026-10-24:

- [Lean validation guidance](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)
  explains axiom reports, the limitations of ordinary checking, independent
  replay, and why arbitrary Lean metaprograms must not be treated as safe data.
- [Lean command-line source](https://github.com/leanprover/lean4/blob/master/src/util/shell.cpp)
  defines `--version` and `--stdin`; the adapter does not use `--run`.
- [Elan toolchain management](https://lean-lang.org/doc/reference/latest/Build-Tools-and-Distribution/Managing-Toolchains-with-Elan/)
  describes its toolchain-selecting and installing proxies, motivating direct
  installed-binary use here.

The sources describe current behavior, not a pinned backend installed by this
project. Actual reported version and executable hash belong in each receipt.
