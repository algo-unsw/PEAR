"""The comparison procedure of bounds §5 (21 November 2026): exact linear programming with
certificates, Z3 for polynomial growths, witnesses for failures, and "undecided"."""

from fractions import Fraction

import pytest

from pear.bounds.compare import Relation, _reduce, analyse, build_context, compare, refuted
from pear.bounds.decide import bounded_below, verify, _slots
from pear.bounds.expr import parse_bound
from pear.bounds.lp import solve

SYMS = {"n", "m", "k", "tw", "N", "n_G", "n_H"}


def P(s: str):  # noqa: N802
    return parse_bound(s, SYMS)


# --- the linear-programming solver -----------------------------------------------------------


def test_lp_solves_exactly():
    r = solve([1, 1], [[1, 2], [3, 1]], [4, 6])
    assert r.status == "optimal" and r.x == (Fraction(8, 5), Fraction(6, 5)) and r.value == Fraction(14, 5)
    assert solve([1, 0], [[-1, 1]], [0]).status == "unbounded"
    assert solve([0], [[1]], [-1]).status == "infeasible"
    assert solve([1, 1], a_eq=[[1, 1]], b_eq=[3]).value == 3
    assert solve([-1, -1], [[-1, -1]], [-2]).value == -2  # x + y >= 2, minimise x + y


# --- proofs and certificates -----------------------------------------------------------------


def _growth(a: str, b: str, ctx, mode: str = "ostar"):
    ta, tb = analyse(P(a)).terms[0], analyse(P(b)).terms[0]
    return _reduce(tb.lo, ctx, mode) - _reduce(ta.hi, ctx, mode)


def test_certificate_is_checked_independently():
    ctx = build_context(SYMS, [r"k \le n"])
    g = _growth(r"O^*(1.5^{k} 1.1^{n})", r"O^*(1.7^{n})", ctx)  # 1.5^k 1.1^n <= 1.65^n <= 1.7^n
    dec = bounded_below(g, ctx)
    assert dec.proved
    (cert,) = dec.certificates
    # k is paid for by n: along the edge k <= n, or with a multiple of n - k >= 0
    assert cert.method == "lp" and (cert.weak or cert.lam)
    slots = _slots(g, {})
    assert verify(cert, slots, ctx)
    # a tampered certificate is rejected: paying ten times as much as there is
    used = cert.weak or cert.lam
    for key in used:
        used[key] *= 10
    assert not verify(cert, slots, ctx)


def test_nonnegative_expressions_are_used_with_a_multiplier():
    ctx = build_context(SYMS, [r"m \le n(n - 1)/2"])
    assert compare(P(r"O^*(1.1996^{n(n - 1)/2 - m})"), P(r"O^*(2^{n(n - 1)/2 - m})"), ctx) == Relation.BETTER


def test_named_constants_are_checked_at_both_ends():
    ctx = build_context(SYMS, [], constants={"omega": (2.0, 2.371339)})
    assert compare(P(r"O^*(2^{2 n})"), P(r"O^*(2^{\omega n})"), ctx) in (Relation.BETTER, Relation.EQUAL)
    assert compare(P(r"O^*(2^{\omega n})"), P(r"O^*(2^{2.4 n})"), ctx) == Relation.BETTER
    # ω is not known to be at most 2.3: not comparable either way at both ends
    assert compare(P(r"O^*(2^{\omega n})"), P(r"O^*(2^{2.3 n})"), ctx) != Relation.BETTER


def test_logarithms_of_a_variable_below_a_strict_power_gap():
    # 21 November 2026: k log n_G = o(n_G n_H) for k <= n_H, so (n_G n_H)^{ω k/3} beats
    # 1.1996^{n_G n_H} (Maximum Common Subgraph), which the per-variable rules could not show
    ctx = build_context(SYMS, [r"k \le n_G", r"k \le n_H"], constants={"omega": (2.0, 2.371339)})
    assert compare(P(r"O^*((n_G n_H)^{\omega k/3})"), P(r"O^*(1.1996^{n_G n_H})"), ctx) == Relation.BETTER


def test_z3_proves_what_the_linear_program_cannot():
    # n^2 - k n - tw n = n (n - k - tw) >= 0 needs the product of n with the constraint
    ctx = build_context(SYMS, [r"k + tw \le n"])
    assert compare(P(r"O^*(2^{k n + \mathit{tw} n})"), P(r"O^*(2^{n^{2}})"), ctx) == Relation.BETTER
    g = _growth(r"O^*(2^{k n + \mathit{tw} n})", r"O^*(2^{n^{2}})", ctx)
    assert bounded_below(g, ctx).certificates[0].method == "z3"


def test_strict_edges_need_a_positive_leftover():
    # 20 November 2026 case, now a certificate question: with tw <= k, n^k is used up by n^tw
    ctx = build_context(SYMS, [r"k \le n", r"\mathit{tw} \le k"])
    assert compare(P(r"2^{O(k)} n^{\mathit{tw} + 1} \log n"), P(r"O(n^{k} k^{2} + n^{2})"), ctx) == Relation.INCOMPARABLE


# --- witnesses and "undecided" -----------------------------------------------------------------


def test_incomparable_needs_a_witness_each_way():
    ctx = build_context(SYMS, [r"k \le n"])
    a, b = analyse(P(r"O^*(1.5^{k})")), analyse(P(r"O^*(1.1^{n})"))
    assert compare(a, b, ctx) == Relation.INCOMPARABLE
    assert refuted(a, b, ctx, "ostar").startswith("witness: ")  # k = t, n = t
    assert refuted(b, a, ctx, "ostar").startswith("witness: ")  # k constant


def test_witness_cancels_exactly_along_a_slice():
    # m = n(n-1)/2 makes 2^{n(n-1)/2 - m} constant: exactly 0, not "about 0"
    ctx = build_context(SYMS, [r"m \le n(n - 1)/2"])
    a, b = analyse(P(r"O^*(2^{n})")), analyse(P(r"O^*(2^{n(n - 1)/2 - m})"))
    why = refuted(a, b, ctx, "ostar")
    assert why is not None and "m = t(t-1)/2" in why


def test_no_proof_and_no_witness_is_undecided():
    ctx = build_context(SYMS, [])
    assert compare(P(r"O(2^{n})"), P(r"O(2^{n} \log(n + m))"), ctx) == Relation.UNDECIDED  # outside the class
    # a constant base with ω and no known range for ω
    assert compare(P(r"O^*(3^{\mathit{tw}})"), P(r"O^*((1 + 2^{\omega - 1} \cdot 3)^{\mathit{tw}})"), ctx) == Relation.UNDECIDED


def test_rules_refute_without_slices():
    ctx = build_context(SYMS, [])
    a, b = analyse(parse_bound(r"O^*(f(k))", SYMS)), analyse(P(r"O^*(2^{k})"))
    assert "B3" in refuted(a, b, ctx, "ostar")


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (r"O^*(1.5^{n})", r"O^*(1.4^{n} n^{3})", Relation.WORSE),
        (r"O^*(2^{\sqrt{n}})", r"O^*(1.01^{n})", Relation.BETTER),
        (r"O^*(2^{o(n)})", r"O^*(1.01^{n})", Relation.BETTER),
        (r"O^*(2^{O(\sqrt{n})})", r"O^*(2^{\sqrt{n} \log n})", Relation.BETTER),
    ],
)
def test_tiers(a, b, expected):
    # exponential rate first, then sub-exponential, then polynomial: strict edges between tiers
    assert compare(P(a), P(b), build_context(SYMS, [])) == expected
