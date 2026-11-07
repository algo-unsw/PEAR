"""Display and substitution (docs/specs/bounds.md §4, rulebook §2).

Bounds are always shown in their natural form: the factors as written, never the
internal growth exponent. The O* form only removes polynomial factors and dominated
terms; derived bounds additionally get their constants folded, with bases rounded up.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from .compare import Context, _hidden, term_le
from .expr import (
    Add,
    Asym,
    Bound,
    Div,
    Func,
    Log,
    Mul,
    Node,
    Num,
    Poly,
    Pow,
    Sqrt,
    Var,
    format_number,
    num,
    render_bound,
)
from .growth import Unspecified, UnsupportedBound, bound_terms, log_growth

DECIMALS = 4  # bases computed for derived bounds are rounded up to this many places


# --- O* form -------------------------------------------------------------------


def ostar(b: Bound, ctx: Context) -> Bound:
    """The O* form: drop factors polynomial in N, then terms dominated by another term."""
    terms = [t for _, t in b.expr.terms] if isinstance(b.expr, Add) else [b.expr]
    kept = [_drop_poly_factors(t, ctx) for t in terms]
    kept = _drop_dominated(kept, ctx)
    expr = kept[0] if len(kept) == 1 else Add(tuple((1, t) for t in kept))
    return Bound("O*", expr, b.family)


def ostar_tex(b: Bound, ctx: Context) -> str:
    return render_bound(ostar(b, ctx))


def _drop_poly_factors(term: Node, ctx: Context) -> Node:
    factors = list(term.factors) if isinstance(term, Mul) else [term]
    keep = [f for f in factors if not _is_poly_factor(f, ctx)]
    if not keep:
        return num(1)
    return keep[0] if len(keep) == 1 else Mul(tuple(keep))


def _is_poly_factor(f: Node, ctx: Context) -> bool:
    try:
        g = log_growth(f, True)
    except (Unspecified, UnsupportedBound):
        return False
    return all(_hidden(key, ctx, "ostar") for key in g.terms)


def _drop_dominated(terms: list[Node], ctx: Context) -> list[Node]:
    if len(terms) == 1:
        return terms
    try:
        analysed = [bound_terms(Bound("O*", t))[0] for t in terms]
    except UnsupportedBound:
        return terms
    out = []
    for i, t in enumerate(terms):
        dominated = False
        for j in range(len(terms)):
            if i == j or not term_le(analysed[i], analysed[j], ctx, "ostar"):
                continue
            # i ≤ j: drop i, unless they are equal and i comes first
            if term_le(analysed[j], analysed[i], ctx, "ostar") and i < j:
                continue
            dominated = True
            break
        if not dominated:
            out.append(t)
    return out


# --- substitution and folding (derived bounds) -------------------------------------


def substitute(node: Node, mapping: dict[str, Node]) -> Node:
    """Replace variables by expressions, e.g. k ↦ 2k (rulebook §2)."""
    if isinstance(node, Var):
        return mapping.get(node.name, node)
    if isinstance(node, Add):
        return Add(tuple((s, substitute(t, mapping)) for s, t in node.terms))
    if isinstance(node, Mul):
        return Mul(tuple(substitute(f, mapping) for f in node.factors))
    if isinstance(node, Div):
        return Div(substitute(node.num, mapping), substitute(node.den, mapping))
    if isinstance(node, Pow):
        return Pow(substitute(node.base, mapping), substitute(node.exp, mapping))
    if isinstance(node, Sqrt):
        return Sqrt(substitute(node.arg, mapping))
    if isinstance(node, Log):
        return Log(substitute(node.arg, mapping), node.power, node.base)
    if isinstance(node, Asym):
        return Asym(node.kind, substitute(node.arg, mapping))
    if isinstance(node, Func):
        return Func(node.name, substitute(node.arg, mapping))
    if isinstance(node, Poly):
        return Poly(substitute(node.arg, mapping))
    return node


def substitute_bound(b: Bound, mapping: dict[str, Node]) -> Bound:
    return Bound(b.notation, simplify(substitute(b.expr, mapping)), b.family)


def simplify(node: Node) -> Node:
    """Light clean-up that keeps the natural form: flatten products, multiply numbers."""
    if isinstance(node, Mul):
        flat: list[Node] = []
        for f in (simplify(f) for f in node.factors):
            flat.extend(f.factors if isinstance(f, Mul) else [f])
        nums = [f for f in flat if isinstance(f, Num)]
        rest = [f for f in flat if not isinstance(f, Num)]
        if len(nums) > 1:
            value = math.prod((n.value for n in nums), start=Fraction(1))
            nums = [num(value)]
        if nums and nums[0].value == 1 and rest:
            nums = []
        out = nums + rest
        return out[0] if len(out) == 1 else Mul(tuple(out))
    if isinstance(node, Add):
        return _collect(Add(tuple((s, simplify(t)) for s, t in node.terms)))
    if isinstance(node, Pow):
        return Pow(simplify(node.base), simplify(node.exp))
    if isinstance(node, Div):
        return Div(simplify(node.num), simplify(node.den))
    return node


def _collect(node: Add) -> Node:
    """Collect like terms: n + n becomes 2 n, 3k - k becomes 2 k (order of first use kept)."""
    coefs: dict[Node, Fraction] = {}
    for sign, term in node.terms:
        if isinstance(term, Mul) and isinstance(term.factors[0], Num):
            c, rest_f = term.factors[0].value, term.factors[1:]
            rest: Node = rest_f[0] if len(rest_f) == 1 else Mul(rest_f)
        elif isinstance(term, Num):
            c, rest = term.value, num(1)
        else:
            c, rest = Fraction(1), term
        coefs[rest] = coefs.get(rest, Fraction(0)) + sign * c
    if len(coefs) == len(node.terms):
        return node  # nothing to collect: keep the form as written
    out: list[tuple[int, Node]] = []
    for rest, c in coefs.items():
        if c == 0:
            continue
        sign = 1 if c > 0 else -1
        mag = abs(c)
        if isinstance(rest, Num) and rest.value == 1:
            term = num(mag)
        elif mag == 1:
            term = rest
        else:
            term = Mul((num(mag),) + (rest.factors if isinstance(rest, Mul) else (rest,)))
        out.append((sign, term))
    if not out:
        return num(0)
    if len(out) == 1 and out[0][0] > 0:
        return out[0][1]
    return Add(tuple(out))


def fold(node: Node, rounded: bool = False) -> Node:
    """Fold constants into bases (bounds §4).

    Exact folding (the default) folds c^{a·x} only when c^a is exactly a number with at
    most DECIMALS decimal places: 1.2^{2k} becomes 1.44^{k}, 2.25^{n/2} becomes 1.5^{n}.
    Anything else keeps its exact form, since a rounded base is a weaker bound.

    With rounded=True every c^{a·x} is folded and the base rounded up (for the hover).
    """
    if isinstance(node, Pow):
        base, exp = fold(node.base, rounded), fold(node.exp, rounded)
        if isinstance(base, Num) and base.value > 0:
            a, rest = _numeric_coefficient(exp)
            if a is not None and rest is not None and a > 0 and a != 1:
                folded = _exact_power(base.value, a)
                if folded is not None:
                    return Pow(folded, rest)
                if rounded:
                    return Pow(_rounded_up_power(base.value, a), rest)
        return Pow(base, exp)
    if isinstance(node, Mul):
        return simplify(Mul(tuple(fold(f, rounded) for f in node.factors)))
    if isinstance(node, Add):
        return Add(tuple((s, fold(t, rounded)) for s, t in node.terms))
    if isinstance(node, Div):
        return Div(fold(node.num, rounded), fold(node.den, rounded))
    return node


def _numeric_coefficient(exp: Node) -> tuple[Fraction | None, Node | None]:
    if isinstance(exp, Mul) and isinstance(exp.factors[0], Num):
        rest = exp.factors[1:]
        return exp.factors[0].value, rest[0] if len(rest) == 1 else Mul(tuple(rest))
    if isinstance(exp, Div) and isinstance(exp.den, Num) and exp.den.value != 0:
        a, rest = _numeric_coefficient(exp.num)
        if a is None:
            return Fraction(1) / exp.den.value, exp.num
        return a / exp.den.value, rest
    return None, None


def _exact_power(c: Fraction, a: Fraction) -> Num | None:
    """c^a if it is exactly a number with at most DECIMALS decimal places, else None."""
    scale = 10**DECIMALS
    if a.denominator == 1:
        value = c ** int(a)
    else:
        guess = Fraction(round(float(c) ** float(a) * scale), scale)
        if guess <= 0 or guess ** a.denominator != c ** a.numerator:
            return None
        value = guess
    if (value * scale).denominator != 1:
        return None
    return num(value)


def _rounded_up_power(c: Fraction, a: Fraction) -> Num:
    scale = 10**DECIMALS
    if a.denominator == 1:
        up = math.ceil(c ** int(a) * scale)
    else:
        up = math.ceil(float(c) ** float(a) * scale * (1 + 1e-12))
    v = Fraction(up, scale)
    return Num(v, _fixed(v))


def _fixed(v: Fraction) -> str:
    text = f"{float(v):.{DECIMALS}f}".rstrip("0").rstrip(".")
    return text if Fraction(text) == v else format_number(v)


@dataclass(frozen=True)
class Display:
    """How a bound is shown: the O* form, and an optional hover with folded bases."""

    tex: str
    hover: str | None = None


def display(b: Bound, ctx: Context, derived: bool = False) -> Display:
    """Stated bounds keep the paper's form; derived bounds get exact folds. If folding
    with rounded-up bases reads differently, it is offered as the hover (bounds §4)."""
    shown = Bound(b.notation, fold(b.expr) if derived else b.expr, b.family)
    tex = ostar_tex(shown, ctx)
    hover = ostar_tex(Bound(b.notation, fold(b.expr, rounded=True), b.family), ctx)
    return Display(tex, hover if hover != tex else None)


__all__ = [
    "ostar",
    "ostar_tex",
    "substitute",
    "substitute_bound",
    "simplify",
    "fold",
    "Display",
    "display",
]
