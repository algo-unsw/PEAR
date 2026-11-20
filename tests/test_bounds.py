"""Bound language tests, one group per section of docs/specs/bounds.md.

Every bound here is arithmetic only, not a research claim.
"""

from __future__ import annotations

import math

import pytest

from pear.bounds import (
    BoundSyntaxError,
    Relation,
    best,
    build_context,
    compare,
    display,
    is_monotone,
    ostar_tex,
    parse_bound,
    parse_expr,
    render_bound,
    substitute_bound,
)
from pear.bounds.compare import ConstraintError

SYMS = {"n", "m", "N", "k", "tw", "t"}
CTX = build_context(
    SYMS, [r"k \le n", r"m \le n^{2}", r"tw \le n - 1"], not_poly_bounded=["t"], constants={"omega": (2.0, 2.25)}
)
BARE = build_context(SYMS)


def P(s: str):
    return parse_bound(s, SYMS)


# --- §1 syntax -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("src", "notation", "shown"),
    [
        (r"O(1.5^{k} + kn)", "O", r"O(1.5^{k} + k n)"),
        (r"O^*(2^{tw})", "O*", r"O^*(2^{\mathit{tw}})"),
        (r"O^{*}(2^{tw})", "O*", r"O^*(2^{\mathit{tw}})"),
        (r"\tilde{O}(2^{n/2})", "Õ", r"\tilde{O}(2^{n/2})"),
        (r"O^*(2^{O(\sqrt{k})})", "O*", r"O^*(2^{O(\sqrt{k})})"),
        (r"n^{O(k)}", None, r"n^{O(k)}"),
        (r"O((2-\varepsilon)^{n})", "O", r"O((2 - \varepsilon)^{n})"),
        (r"O^*(k^{k})", "O*", r"O^*(k^{k})"),
        (r"f(k) \cdot n^{O(1)}", None, r"f(k) n^{O(1)}"),
        (r"O(1) \cdot 2^{n}", None, r"O(1) \cdot 2^{n}"),
        (r"\mathrm{poly}(n) \cdot 2^{\mathit{tw}}", None, r"\mathrm{poly}(n) \cdot 2^{\mathit{tw}}"),
        (r"O(\log^{2} n \cdot 2^{k})", "O", r"O(\log^{2} n \cdot 2^{k})"),
    ],
)
def test_parse_and_render(src, notation, shown):
    b = P(src)
    assert b.notation == notation
    assert render_bound(b) == shown
    assert render_bound(P(render_bound(b))) == shown  # rendering parses back to itself


def test_family_form():
    b = P(r"O(2^{\delta n}) \text{ for every } \delta > 0")
    assert b.family


@pytest.mark.parametrize(
    ("src", "message"),
    [
        (r"O(2^{x})", "unknown variable"),
        (r"n^10", "braces"),
        (r"O(2^{\delta n})", "for every"),
        (r"O(1.5^{k} + kn", "unbalanced"),
        (r"O(2^{n}))", "unexpected"),
        (r"\mathrm{zz}", "unknown variable"),
        (r"\foo{n}", "unsupported command"),
    ],
)
def test_syntax_errors(src, message):
    with pytest.raises(BoundSyntaxError, match=message):
        P(src)


def test_longest_symbol_wins():
    assert render_bound(P(r"O(2^{tw} kn)")) == r"O(2^{\mathit{tw}} k n)"


# --- §2 meaning and §5 comparison ------------------------------------------------------


def rel(a: str, b: str, ctx=CTX) -> str:
    return compare(P(a), P(b), ctx).value


@pytest.mark.parametrize(
    ("a", "b", "expected", "rule"),
    [
        # one variable: shape first, then coefficient (§5.2)
        (r"O^*(2^{\sqrt{k}})", r"O^*(1.1^{k})", "<", "smaller shape wins"),
        (r"O^*(1.1^{k})", r"O^*(1.5^{k})", "<", "smaller base wins"),
        (r"O^*(1.5^{k})", r"O^*(k^{k})", "<", "k^k is a larger shape"),
        (r"O^*(1.2^{2k})", r"O^*(1.44^{k})", "=", "same value written two ways"),
        # non-explicit constants (§2)
        (r"O((2-\varepsilon)^{n})", r"O(2^{n})", "<", "2 - ε beats 2"),
        (r"O(1.99^{n})", r"O((2-\varepsilon)^{n})", "<", "any explicit base below 2 beats 2 - ε"),
        # asymptotics inside exponents (§2, §5.2)
        (r"O^*(2^{\sqrt{k}})", r"O^*(2^{O(\sqrt{k})})", "<", "more precise beats less precise"),
        (r"O^*(2^{O(\sqrt{k})})", r"O^*(2^{O(\sqrt{k})})", "=", "the same statement"),
        (r"O^*(2^{O(\sqrt{k})})", r"O^*(1.01^{k})", "<", "unknown constant, smaller shape"),
        (r"O^*(2^{\sqrt{n}})", r"2^{o(n)}", "<", "an explicit o(n) exponent is more precise"),
        # families (§2)
        (r"2^{o(n)}", r"O(2^{\delta n}) \text{ for every } \delta > 0", "<", "one algorithm beats a family"),
        # (c + δ)^n for every δ > 0 is the family c^n 2^{δn} (18 November 2026)
        (r"O((1 + \delta)^{n}) \text{ for every } \delta > 0", r"O(2^{\delta n}) \text{ for every } \delta > 0", "=", "(1 + δ)^n is 2^{δn}"),
        (r"1.75^{n}", r"O((1.75 + \delta)^{n}) \text{ for every } \delta > 0", "<", "c^n beats (c + δ)^n"),
        (r"O((1.75 + \delta)^{n}) \text{ for every } \delta > 0", r"1.7501^{n}", "<", "(c + δ)^n beats (c + ε)^n for a fixed ε"),
        (r"2^{n / \log n}", r"O((1 + \delta)^{n}) \text{ for every } \delta > 0", "<", "subexponential beats (1 + δ)^n"),
        (r"O(2^{\delta n}) \text{ for every } \delta > 0", r"O(1.01^{n})", "<", "family beats any c^n"),
        # several variables need constraints (§5.3)
        (r"O^*(1.5^{k})", r"O^*(1.5^{n})", "<", "k ≤ n"),
        (r"O^*(1.5^{k})", r"O^*(1.2^{n})", "?", "different parameters, different bases"),
        (r"O^*(2^{\mathit{tw}})", r"O^*(2^{n})", "<", "tw ≤ n - 1"),
        (r"O^*(2^{m})", r"O^*(2^{n^{2}})", "<", "m ≤ n^2"),
        (r"O^*(2^{k})", r"n^{O(k)}", "<", "mixed monomial, collapsed through k ≤ n"),
        (r"O^*(k^{k})", r"n^{O(k)}", "<", "k^k ≤ n^k is an instance of n^{O(k)}"),
        (r"O^*(1.5^{n-k})", r"O^*(1.5^{n})", "<", "composite parameter"),
        # terms (§5.1)
        (r"O(1.5^{k} + kn)", r"O(1.5^{k} k n)", "<", "sum dominated term by term"),
        # O* first, then exact forms (§5.4, B6)
        (r"O(2^{n} n)", r"O(2^{n} n^{2})", "<", "equal in O*, smaller polynomial"),
        (r"O(1.5^{k} k)", r"O(1.5^{k} + kn)", "~", "equal in O*, exact forms incomparable"),
        (r"O(1.5^{k} + kn)", r"O^*(1.5^{k})", "<", "explicit polynomial beats a hidden one"),
        (r"O(2^{n} n)", r"\tilde{O}(2^{n})", "<", "explicit factor beats hidden polylog"),
        (r"O^*(2^{k})", r"O^*(2^{k} n^{O(1)})", "=", "the same statement"),
        # named constants (§2): symbolic, resolved with data/constants
        (r"O(n^{\omega})", r"O(n^{\omega})", "=", "the same symbol"),
        (r"O(n^{\omega})", r"O(n^{\omega} \log n)", "<", "symbol cancels"),
        (r"O(n^{\omega})", r"O(n^{2.3})", "<", "omega ≤ 2.25"),
        (r"O(n^{\omega})", r"O(n^{2.2})", "~", "omega may be above 2.2"),
        (r"O(n^{2})", r"O(n^{\omega})", "<", "omega ≥ 2"),
        (r"O^*(n^{\omega k/3})", r"O^*(n^{0.76 k})", "<", "omega/3 ≤ 0.75"),
        # polynomially bounded variables (B4)
        (r"O(nt)", r"O(nt^{2})", "<", "t is not polynomially bounded"),
        (r"O(n^{2} t)", r"O(nt^{2})", "<", "O* keeps t but drops n^2"),
        # unspecified f(k) (B3)
        (r"f(k) n^{O(1)}", r"O^*(k^{k})", ">", "every explicit bound in k beats f(k)"),
        (r"f(k) n^{O(1)}", r"O^*(1.1^{n})", "?", "a bound in another parameter does not"),
        (r"f(k) n^{O(1)}", r"f(k) n^{O(1)}", "?", "f(k) beats nothing"),
        # factorials, Bell numbers and π (20 November 2026)
        (r"O^*(k!)", r"O^*(k^{k})", "<", "k! is (k/e)^k up to polynomial factors"),
        (r"O^*(k!)", r"O^*((k/3)^{k})", ">", "k! is above (k/3)^k"),
        (r"O^*(k! 4^{k})", r"O^*(k^{k})", ">", "k! 4^k is about (4k/e)^k"),
        (r"O^*(k! 2^{o(k)})", r"O^*(k! 4^{k})", "<", "a subexponential factor beats 4^k"),
        (r"O^*(B_{k})", r"O^*(k^{k})", "<", "B_k ≤ k^k, and B_k is not k^k"),
        (r"O^*(2^{k})", r"O^*(B_{k})", "<", "B_k ≥ (k/8)^{k/4}"),
        (r"O^*(2^{\pi k})", r"O^*(2^{3.15 k})", "<", "π < 3.15"),
        (r"O^*(2^{\pi k})", r"O^*(2^{3.14 k})", ">", "π > 3.14"),
    ],
)
def test_compare(a, b, expected, rule):
    assert rel(a, b) == expected, rule
    mirror = {"<": ">", ">": "<"}.get(expected, expected)
    assert rel(b, a) == mirror, f"{rule} (mirrored)"


def test_named_constants_need_values():
    assert rel(r"O(n^{\omega})", r"O(n^{2.3})", BARE) == "~"


def test_constraints_are_needed_across_variables():
    assert rel(r"O^*(1.5^{k})", r"O^*(1.5^{n})", BARE) == "?"


def test_best_keeps_the_antichain():
    bounds = [P(r"O^*(1.5^{k})"), P(r"O^*(1.2^{n})"), P(r"O^*(2^{k})"), P(r"f(k) n^{O(1)}")]
    assert best(bounds, CTX) == [0, 1]


def test_unsupported_bounds_are_incomparable_not_errors():
    # the log of a sum is outside the supported class: kept as incomparable (§5 principle)
    odd = P(r"O(2^{n} \log(n + m))")
    assert compare(P(r"O(2^{n})"), odd, CTX) == Relation.INCOMPARABLE
    assert best([P(r"O(2^{n})"), odd], CTX) == [0, 1]


# --- constraints (B5) -------------------------------------------------------------------


def test_constraints_close_transitively():
    ctx = build_context({"a", "b", "c"}, [r"a \le b", r"b \le c^{2}"])
    assert ctx.relation("a", "c") == 2


@pytest.mark.parametrize("bad", [r"k n", r"k \le x"])
def test_bad_constraints(bad):
    with pytest.raises((ConstraintError, BoundSyntaxError)):
        build_context(SYMS, [bad])


# --- §4 display -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("src", "shown"),
    [
        (r"O(1.5^{k} + kn)", r"O^*(1.5^{k})"),
        (r"O(2^{n} n^{2})", r"O^*(2^{n})"),
        (r"O^*(k^{k})", r"O^*(k^{k})"),  # natural form, never 2^{k log k} (B2)
        (r"n^{O(k)}", r"O^*(n^{O(k)})"),
        (r"O(n^{2} t)", r"O^*(t)"),  # t is not polynomially bounded (B4)
        (r"O(\sqrt{n} t \log^{5/2} t)", r"O^*(t)"),  # log t <= N: polylog(t) is polynomial in N
        (r"O(n 2^{\log^{2} t})", r"O^*(2^{\log^{2} t})"),  # quasi-polynomial in t stays
        (r"O(n^{2} n^{\omega k / 3})", r"O^*(n^{\omega k/3})"),
        (r"O(n + m + n^{2} n^{\omega (n - k) / 3})", r"O^*(n^{\omega (n - k)/3})"),  # O*(1) terms vanish
        (r"f(k) \cdot n^{O(1)}", r"O^*(f(k))"),
        (r"O(2^{k} + 1.5^{n})", r"O^*(2^{k} + 1.5^{n})"),  # incomparable terms stay
        (r"O(1.5^{k} + 1.5^{n})", r"O^*(1.5^{n})"),  # k ≤ n decides
        (r"O(\log^{2} n \cdot 2^{k} \cdot \mathrm{poly}(n))", r"O^*(2^{k})"),
        (r"O(n^{3})", r"O^*(1)"),
        (r"O(2^{\delta n} n) \text{ for every } \delta > 0", r"O^*(2^{\delta n}) \text{ for every } \delta > 0"),
        (r"O((2-\varepsilon)^{n} n)", r"O^*((2 - \varepsilon)^{n})"),
    ],
)
def test_ostar_display(src, shown):
    assert ostar_tex(P(src), CTX) == shown


@pytest.mark.parametrize(
    ("bound", "mapping", "exact", "shown", "hover"),
    [
        (r"O^*(1.2^{k})", {"k": "2k"}, r"O^*(1.2^{2 k})", r"O^*(1.44^{k})", None),  # the plan's example
        (r"O^*(3^{k})", {"k": "2k"}, r"O^*(3^{2 k})", r"O^*(9^{k})", None),
        (r"O^*(2.25^{k})", {"k": "n/2"}, r"O^*(2.25^{n/2})", r"O^*(1.5^{n})", None),  # exact square root
        # folding would need rounding: keep the exact form, offer the fold on hover
        (r"O(1.2738^{k} + kn)", {"k": "2k"}, r"O(1.2738^{2 k} + 2 k n)", r"O^*(1.2738^{2 k})", r"O^*(1.6226^{k})"),
        (r"O^*(1.5^{k})", {"k": "n/2"}, r"O^*(1.5^{n/2})", r"O^*(1.5^{n/2})", r"O^*(1.2248^{n})"),
        (r"O^*(2^{k})", {"k": "n/2"}, r"O^*(2^{n/2})", r"O^*(2^{n/2})", r"O^*(1.4143^{n})"),
        (r"O^*(1.5^{k})", {"k": "n - k"}, r"O^*(1.5^{n - k})", r"O^*(1.5^{n - k})", None),
        (r"O^*(k^{k})", {"k": "2k"}, r"O^*((2 k)^{2 k})", r"O^*((2 k)^{2 k})", None),
    ],
)
def test_substitution_and_folding(bound, mapping, exact, shown, hover):
    b = substitute_bound(P(bound), {v: parse_expr(e, SYMS) for v, e in mapping.items()})
    assert render_bound(b) == exact
    d = display(b, CTX, derived=True)
    assert (d.tex, d.hover) == (shown, hover)


def test_stated_bounds_are_never_folded():
    d = display(P(r"O^*(1.2^{2k})"), CTX)
    assert d.tex == r"O^*(1.2^{2 k})" and d.hover == r"O^*(1.44^{k})"


def test_shown_bound_is_exact_and_hover_is_an_upper_bound():
    b = substitute_bound(P(r"O^*(1.2738^{k})"), {"k": parse_expr("2k", SYMS)})
    d = display(b, CTX, derived=True)
    assert compare(b, parse_bound(d.tex, SYMS), CTX) == Relation.EQUAL
    assert compare(b, parse_bound(d.hover, SYMS), CTX) == Relation.BETTER


# --- rulebook A2: monotonicity ------------------------------------------------------------


@pytest.mark.parametrize(
    ("src", "monotone"),
    [
        (r"O(1.5^{k} + kn)", True),
        (r"O^*(1.5^{n-k})", False),
        (r"O(2^{n/\log n})", True),
        (r"O(2^{n}/k)", False),
        (r"f(k) n^{O(1)}", True),
        (r"O(k! 2^{o(k)} (n + m))", True),
        (r"O(B_{tw + 1}^{3} n)", True),
    ],
)
def test_monotone(src, monotone):
    assert is_monotone(P(src)) is monotone


@pytest.mark.parametrize(
    ("src", "shown"),
    [
        (r"O(k! 2^{o(k)} (n + m))", r"O(k! \cdot 2^{o(k)} (n + m))"),
        (r"O^*((k!)^{2})", r"O^*((k!)^{2})"),
        (r"O^*((tw + 1)!)", r"O^*((\mathit{tw} + 1)!)"),
        (r"O(B_{tw + 1}^{3} n)", r"O(B_{\mathit{tw} + 1}^{3} n)"),
        (r"2^{\frac{2\pi}{\sqrt{3} \ln 2} \sqrt{k}} n^{O(1)}", r"2^{2 \pi/(\sqrt{3} \ln 2) \sqrt{k}} n^{O(1)}"),
    ],
)
def test_factorial_bell_and_pi_parse_and_render(src, shown):
    assert render_bound(P(src)) == shown


def test_ln_needs_no_constant_file(tmp_path):
    # \ln is the logarithm to base e, a number, not a named constant from data/constants
    from pear.bounds.expr import constants

    assert constants(P(r"2^{\frac{2\pi}{\sqrt{3} \ln 2} \sqrt{k}}").expr) == {"e"}


def test_factorial_bell_and_pi_values():
    from pear.bounds.numeric import log_value, value

    assert value(P("5!").expr, {}) == 120
    assert round(value(P("B_{5}").expr, {})) == 52
    assert abs(value(P(r"2^{\pi}").expr, {}) - 2 ** math.pi) < 1e-9
    assert abs(log_value(P("k!").expr, {"k": 1000.0}) - math.lgamma(1001)) < 1e-6
    # de Bruijn's expansion beyond the exact table is close to the exact value
    assert abs(log_value(P("B_k").expr, {"k": 400.0}) - math.log(_bell(400))) / math.log(_bell(400)) < 0.01


def _bell(n: int) -> int:
    row = [1]
    for _ in range(n):
        nxt = [row[-1]]
        for v in row:
            nxt.append(nxt[-1] + v)
        row = nxt
    return row[0]


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        # 20 November 2026 (Serge): k! 2^{o(k)} with k ≤ n gives n! 2^{o(n)}: a bound that is
        # nondecreasing in every variable may have its variables raised along the constraints
        (r"O^*(k! 2^{o(k)})", r"O^*(n! 2^{o(n)})", "<"),
        (r"O^*(n^{k})", r"O^*(n^{n})", "<"),
        (r"O(n^{k} k^{2} + n^{2})", r"O^*(n^{n})", "<"),
        (r"O^*(B_{tw + 1})", r"O^*(B_{n + 1})", "<"),
        (r"O^*(B_{tw + 1})", r"O^*(B_{tw + 1})", "="),  # identical statements, though B's estimates differ
        (r"O^*(1.5^{n - k})", r"O^*(1.5^{n})", "<"),
        (r"O^*(k!)", r"O^*(2^{n})", "?"),  # k may be n
        (r"O^*(2^{k})", r"O^*(1.9^{n})", "?"),
    ],
)
def test_raising_variables_of_monotone_bounds(a, b, expected):
    ctx = build_context(SYMS, [r"k \le n", r"tw \le k"])
    assert compare(P(a), P(b), ctx).value == expected


def test_omega_cancels_across_monomials_and_variables():
    # 20 November 2026: ω x ≤ ω y for x ≤ y, and n_G log n_H ≤ n_G n_H log n_H pointwise
    syms = {"n", "k", "n_G", "n_H", "N", "m"}
    ctx = build_context(syms, [r"k \le n_G", r"k \le n_H", r"n_G \le n", r"n_H \le n"],
                        constants={"omega": (2.0, 2.371339)})
    Q = lambda s: parse_bound(s, syms)  # noqa: E731
    assert compare(Q(r"O^*(n^{\omega k})"), Q(r"O^*(n^{\omega n})"), ctx) == Relation.BETTER
    assert compare(Q(r"O^*((n_G n_H)^{\omega k/3})"), Q(r"O^*((n_G n_H)^{\omega n_G n_H/3})"), ctx) == Relation.BETTER
    assert compare(Q(r"O^*(2^{n_G})"), Q(r"O^*(2^{n_G n_H})"), ctx) == Relation.BETTER
    assert compare(Q(r"O^*(n^{\omega k})"), Q(r"O^*(n^{2 k})"), ctx) == Relation.WORSE


def test_strict_domination_needs_a_coefficient_left():
    # 20 November 2026: with tw ≤ k, n^k beats n^tw, but its coefficient is then used up, so
    # it cannot also absorb 2^{O(k)}: Alon–Yuster–Zwick's 2^{O(k)} n^{tw+1} log n does not
    # beat O(n^k k^2 + n^2) (take tw = k)
    ctx = build_context(SYMS, [r"k \le n", r"tw \le k"])
    a, b = P(r"2^{O(k)} n^{tw + 1} \log n"), P(r"O(n^{k} k^{2} + n^{2})")
    assert compare(a, b, ctx) == Relation.INCOMPARABLE
    assert compare(P(r"n^{tw}"), P(r"n^{k}"), ctx) == Relation.BETTER
    assert compare(P(r"2^{k} n^{tw}"), P(r"n^{k} \log n"), ctx) == Relation.INCOMPARABLE


def test_subtraction_in_a_factor_is_bounded_above():
    # (n - k) <= n is polynomial, so it disappears under O*
    assert ostar_tex(P(r"O(n + m + 1.2738^{n - k} + (n - k) n)"), CTX) == r"O^*(1.2738^{n - k})"


def test_term_without_lower_estimate_does_not_block_the_bound():
    # (n - k) n has no safe lower estimate, but the 1.2738^{n-k} term still compares
    a = P(r"O^*(1.25281^{n - k})")
    b = P(r"O(n + m + 1.2738^{n - k} + (n - k) n)")
    assert compare(a, b, CTX) == Relation.BETTER


@pytest.mark.parametrize(
    ("text", "tex"),
    [
        (r"2^{tw_p}", r"2^{\mathit{tw}_{p}}"),
        (r"2^{tw_{i}} n", r"2^{\mathit{tw}_{i}} n"),
        (r"ntw_d", r"n \mathit{tw}_{d}"),
    ],
)
def test_subscripted_symbols(text, tex):
    assert render_bound(parse_bound(text, {"n", "tw", "tw_p", "tw_d", "tw_i"})) == tex


def test_power_of_a_logarithm_keeps_its_parentheses():
    from pear.bounds import parse_bound
    from pear.bounds.expr import render_bound

    tex = render_bound(parse_bound(r"2^{O(k (\log\log k)^{1/9} / (\log k)^{1/54})}", ("k",)))
    assert r"(\log \log k)^{1/9}" in tex and r"(\log k)^{1/54}" in tex


# --- ε depending on parameters: bounds for every fixed k (decided 17 November 2026) -----------


def _fixed_ctx():
    from pear.bounds.compare import build_context

    return build_context(("n", "k"), ("k \\le n",))


def test_epsilon_with_subscript_parses_and_renders():
    from pear.bounds import parse_bound
    from pear.bounds.expr import fixed_parameters, render_bound, variables

    b = parse_bound(r"O((2 - \varepsilon_{k})^{n})", ("n", "k"))
    assert render_bound(b) == r"O((2 - \varepsilon_{k})^{n})"
    assert variables(b.expr) == {"n", "k"} and fixed_parameters(b.expr) == {"k"}
    assert render_bound(parse_bound(r"(2 - \varepsilon_k)^{n}", ("n", "k"))) == r"(2 - \varepsilon_{k})^{n}"


def test_epsilon_subscript_must_name_parameters():
    from pear.bounds import BoundSyntaxError, parse_bound

    with pytest.raises(BoundSyntaxError):
        parse_bound(r"(2 - \varepsilon_{3})^{n}", ("n", "k"))


def test_fixed_k_bound_is_incomparable_with_uniform_bounds():
    from pear.bounds import parse_bound
    from pear.bounds.compare import Relation, compare_ostar

    fixed = parse_bound(r"O((2 - \varepsilon_{k})^{n})", ("n", "k"))
    for other in (r"O^*(2^{n})", r"O^*(1.5^{n})", r"O^*(3^{n})"):
        assert compare_ostar(fixed, parse_bound(other, ("n", "k")), _fixed_ctx()) is Relation.INCOMPARABLE


def test_fixed_k_bounds_compare_among_themselves():
    from pear.bounds import parse_bound
    from pear.bounds.compare import Relation, compare_ostar

    a = parse_bound(r"O((2 - \varepsilon_{k})^{n})", ("n", "k"))
    b = parse_bound(r"O^*((2 - \varepsilon_{k})^{n})", ("n", "k"))
    assert compare_ostar(a, b, _fixed_ctx()) is Relation.EQUAL


def test_plain_epsilon_still_beats_two_to_the_n():
    from pear.bounds import parse_bound
    from pear.bounds.compare import Relation, compare_ostar

    a = parse_bound(r"O^*((2 - \varepsilon)^{n})", ("n",))
    assert compare_ostar(a, parse_bound(r"O^*(2^{n})", ("n",)), _fixed_ctx()) is Relation.BETTER


# --- common sense (18 November 2026) ----------------------------------------------------------


def _cmp(a, b, syms, constraints=(), constants=None, nonneg=()):
    from pear.bounds.compare import build_context

    ctx = build_context(syms, constraints, constants=constants or {}, nonneg=nonneg)
    return compare(parse_bound(a, syms), parse_bound(b, syms), ctx)


def test_same_exponent_with_a_nonnegative_difference():
    # 1.1996^{X} beats 2^{X} only because X = n(n-1)/2 - m >= 0, from the exact edge bound
    syms = ("n", "m")
    a, b = r"O^*(1.1996^{n (n - 1)/2 - m})", r"O^*(2^{n (n - 1)/2 - m})"
    assert _cmp(a, b, syms, [r"m \le n^{2}"]) == Relation.INCOMPARABLE
    assert _cmp(a, b, syms, [r"m \le n(n - 1)/2"]) == Relation.BETTER
    # or from a reduction's parameter map, which bounds a parameter of the produced instance
    assert _cmp(a, b, syms, [r"m \le n^{2}"], nonneg=[r"n (n - 1)/2 - m"]) == Relation.BETTER


def test_exact_edge_bound_still_gives_m_at_most_n_squared():
    from pear.bounds.compare import build_context

    assert build_context(("n", "m"), [r"m \le n(n - 1)/2"]).relation("m", "n") == 2


def test_constant_bases_are_evaluated():
    syms = ("k", "tw")
    golden = r"O^*((2 + (1 + \sqrt{5})/2)^{k})"
    assert _cmp(r"O^*(2.69998^{k})", golden, syms) == Relation.BETTER
    assert _cmp(r"O^*(3.7^{k})", golden, syms) == Relation.WORSE
    # with named constants, from their known range: 1 + 3 \cdot 2^{\omega - 1} >= 7 > 3
    rank = r"O^*((1 + 2^{\omega - 1} \cdot 3)^{tw})"
    assert _cmp(r"O^*(3^{tw})", rank, syms, constants={"omega": (2.0, 2.371339)}) == Relation.BETTER
    assert _cmp(r"O^*(3^{tw})", rank, syms) == Relation.INCOMPARABLE  # no range: no proof


def test_numeric_cross_check_finds_what_the_comparator_misses():
    from pear.bounds.expr import parse_expr
    from pear.bounds.numeric import dominates, samples

    syms = ["n", "m", "k"]
    pts = samples(syms, [r"k \le n", r"m \le n(n - 1)/2"], {}, count=100)
    assert pts and all(p["k"] <= p["n"] and p["m"] <= p["n"] * (p["n"] - 1) / 2 for p in pts)
    e = lambda s: parse_expr(s, syms)  # noqa: E731
    assert dominates(e(r"1.1996^{n}"), e(r"2^{n}"), pts)
    # k close to n is sampled, so 1.25^k is not taken to be below n^{n - k}
    assert not dominates(e(r"1.25^{k}"), e(r"n^{n - k}"), pts)
    assert not dominates(e(r"2^{n}"), e(r"1.1996^{n}"), pts)


def test_simplify_drops_zero_terms():
    # 20 November 2026: n(n - 1)/2 - n(n - 1)/2 is 0, and a 0 summand is not shown
    from pear.bounds.display import simplify, substitute
    from pear.bounds.expr import parse_expr, render

    e = parse_expr(r"n + (n (n - 1)/2 - m) + 2^{n}", {"n", "m"})
    out = simplify(substitute(e, {"m": parse_expr(r"n (n - 1)/2", {"n"})}))
    assert render(out) == r"n + 2^{n}"
    assert render(simplify(parse_expr(r"0 \cdot n + k", {"n", "k"}))) == "k"


@pytest.mark.parametrize("stated, shown", [
    # 20 November 2026: O(·) hides constant factors, constant terms, log bases, constant powers
    # inside logs and dominated summands
    (r"O^*(2^{O(2 n (\log \log(2 n))^{2}/\sqrt{\log(2 n)})})", r"O^*(2^{O(n (\log \log n)^{2}/\sqrt{\log n})})"),
    (r"O^*(2^{O((2 k + 1) \log(2 k + 1))})", r"O^*(2^{O(k \log k)})"),
    (r"O^*(2^{O(n (n - 1)/2 \log n^{3})})", r"O^*(2^{O(n^{2} \log n)})"),
    (r"O^*(2^{O((n^{2} + n) \log_{3}(k + n^{2}))})", r"O^*(2^{O(n^{2} \log(k + n))})"),
    (r"O^*(2^{O((n (n - 1)/2 - m) \log n)})", r"O^*(2^{O((n (n - 1)/2 - m) \log n)})"),
    (r"O^*(2^{t - 1})", r"O^*(2^{t})"),
    (r"O^*(n^{k + o(1)})", r"O^*(n^{k + o(1)})"),
    (r"O^*(2^{o(3 n)})", r"O^*(2^{o(n)})"),
    (r"O(2^{k} (2 n)^{O(1)})", r"O^*(2^{k})"),
])
def test_ostar_hides_constants(stated, shown):
    from pear.bounds.compare import Context
    from pear.bounds.display import ostar_tex

    b = parse_bound(stated, {"n", "m", "k", "t"})
    assert ostar_tex(b, Context()) == shown


def test_hide_constants_in_a_polynomial_base():
    from pear.bounds.compare import Context
    from pear.bounds.display import hide_constants
    from pear.bounds.expr import render

    b = parse_bound(r"O(2^{k} (2 n^{2})^{O(1)} (n_{G} n_{H})^{O(k)})", {"n", "k", "n_G", "n_H"})
    assert render(hide_constants(b.expr, Context())) == r"2^{k} n^{O(1)} (n_{G} n_{H})^{O(k)}"



def test_comparison_ignores_constants_inside_o():
    # 20 November 2026: 2^{O(2n (log log(2n))^2/sqrt(log(2n)))} was kept next to the strictly
    # better 2^{O(n log log n/sqrt(log n))}, because log(2n) was outside the normal form
    from pear.bounds.compare import Context

    better = parse_bound(r"O^*(2^{O(n \log \log n/\sqrt{\log n})})", {"n"})
    worse = parse_bound(r"O^*(2^{O(2 n (\log \log(2 n))^{2}/\sqrt{\log(2 n)})})", {"n"})
    assert compare(better, worse, Context()) == Relation.BETTER


def test_tilde_o_hides_polylog_of_the_bound():
    # bounds §2: Õ hides a factor polylogarithmic in the bound itself; Õ(n + t) hides
    # polylog(n + t), not a polynomial (20 November 2026: Bringmann's Õ(n + t) for Subset Sum
    # was dropped as if Koiliaris–Xu's sqrt(n) t log^{5/2} t were at least as good)
    from pear.bounds.compare import Context

    s = {"n", "t"}
    rel = compare(parse_bound(r"\tilde{O}(n + t)", s), parse_bound(r"\sqrt{n} t \log^{5/2} t", s), Context())
    assert rel in (Relation.TIE, Relation.INCOMPARABLE)
    # for an exponential bound the polylog is a polynomial, as before
    assert compare(parse_bound(r"O(2^{n} n^{5})", s), parse_bound(r"\tilde{O}(2^{n})", s), Context()) == Relation.BETTER


def test_constraint_keeps_its_coefficient():
    from fractions import Fraction

    from pear.bounds.compare import build_context

    ctx = build_context({"n", "m", "k"}, [r"m \le n (n - 1)/2", r"k \le m"])
    assert ctx.relation("m", "n") == 2 and ctx.scale("m", "n") == Fraction(1, 2)
    assert ctx.relation("k", "n") == 2 and ctx.scale("k", "n") == Fraction(1, 2)  # closed
    assert ctx.scale("k", "m") == 1


def test_substitution_rewrites_epsilon_subscripts():
    from pear.bounds.display import substitute
    from pear.bounds.expr import Const, parse_expr

    e = parse_expr(r"(2 - \varepsilon_{k})^{n}", {"n", "k"})
    assert substitute(e, {"k": parse_expr("3", set())}).base.terms[1][1] == Const("varepsilon", ())
    assert substitute(e, {"k": parse_expr("2 p", {"p"})}).base.terms[1][1] == Const("varepsilon", ("p",))


# --- parameters a bound is listed under (rulebook §7, 20 November 2026) --------------------------

from pear.bounds.params import listed_parameters  # noqa: E402

LISTED_SYMS = {"k", "n", "m", "tw", "d", "p"}
LISTED_ORDER = ["k", "d", "p", "n", "m", "N", "tw"]


@pytest.mark.parametrize(
    ("bound", "listed"),
    [
        (r"O^*(1.977^{m - k})", ["m - k"]),
        (r"O^*(2^{O((m - k)/\sqrt{\log(m - k)})})", ["m - k"]),
        (r"O^*(1.2273^{m + n})", ["n + m"]),  # one key for n + m and m + n
        (r"O^*(1.2279^{n + m})", ["n + m"]),
        (r"O^*(2^{(m - k)/4})", ["m - k"]),  # constant factor stripped
        # products, other coefficients, higher degrees: the variables, in reading order (20 November 2026)
        (r"O^*(1.4423^{d k})", ["k", "d"]),
        (r"O^*(2^{m - 3 n/5})", ["n", "m"]),
        (r"O^*(2^{(n (n - 1)/2 - m)/4})", ["n", "m"]),
        (r"O^*(2^{9 m/50 + o(m)})", ["m"]),
        (r"O^*(1.2738^{k})", ["k"]),
        (r"O^*(n^{\omega (n - k)/3})", ["k", "n"]),  # n and n - k: listed under the variables
        (r"O^*((2 - \varepsilon_{k})^{n})", ["k", "n"]),
        (r"O^*(1.5^{k} + 1.3^{n})", ["k", "n"]),
        (r"O^*(n^{\omega k/3})", ["k", "n"]),
    ],
)
def test_listed_parameters(bound, listed):
    expr = parse_bound(bound, LISTED_SYMS).expr
    assert [p.key for p in listed_parameters(expr, LISTED_ORDER)] == listed


def test_exact_shape():
    from pear.bounds.compare import Context
    from pear.bounds.display import exact_shape

    s = {"n", "m", "k", "t", "tw"}
    assert exact_shape(parse_bound(r"O(n^{k + o(1)})", s), Context())
    assert exact_shape(parse_bound(r"O(2^{O(k)} n^{\mathit{tw} + 1})", s), Context())
    assert not exact_shape(parse_bound(r"O(k^{n})", s), Context())
    assert not exact_shape(parse_bound(r"O(2^{n} n)", s), Context())
    pseudo = Context(frozenset({"t"}))
    assert exact_shape(parse_bound(r"O(\sqrt{n} t \log^{5/2} t)", s), pseudo)
    assert not exact_shape(parse_bound(r"O(2^{n/2} t)", s), pseudo)


def test_euler_number():
    # 21 November 2026: \mathrm{e} is Euler's number (Tournament Fixing by in-degree,
    # (2e)^{k 2^k - k} n^{O(1)}); a plain e stays free as a variable name
    import math

    from pear.bounds.compare import Context
    from pear.bounds.display import ostar_tex
    from pear.bounds.numeric import value

    b = parse_bound(r"(2 \mathrm{e})^{k 2^{k} - k} n^{O(1)}", {"k", "n"})
    assert ostar_tex(b, Context()) == r"O^*((2 \mathrm{e})^{k \cdot 2^{k} - k})"
    assert abs(value(parse_bound(r"\mathrm{e}^{k}", {"k"}).expr, {"k": 1.0}) - math.e) < 1e-12
