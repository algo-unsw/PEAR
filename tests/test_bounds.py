"""Bound language tests, one group per section of docs/specs/bounds.md.

Every bound here is arithmetic only, not a research claim.
"""

from __future__ import annotations

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
    ],
)
def test_monotone(src, monotone):
    assert is_monotone(P(src)) is monotone


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
