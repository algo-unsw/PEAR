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
    children,
    Const,
    Asym,
    Bell,
    Bound,
    Div,
    Fact,
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
    variables,
)
from .growth import Unspecified, UnsupportedBound, bound_terms, log_growth

DECIMALS = 4  # bases computed for derived bounds are rounded up to this many places


# --- O* form -------------------------------------------------------------------


def ostar(b: Bound, ctx: Context) -> Bound:
    """The O* form: drop factors polynomial in N, then terms dominated by another term.
    Constants that O(·) or O*(·) hide are dropped too (hide_constants)."""
    expr = hide_constants(b.expr, ctx)
    terms = [t for _, t in expr.terms] if isinstance(expr, Add) else [expr]
    kept = [_drop_poly_factors(t, ctx) for t in terms]
    if len(kept) > 1:
        # a term that was only polynomial factors is O*(1); a running time is at least 1,
        # so it adds nothing next to another term
        kept = [t for t in kept if t != num(1)] or [num(1)]
    kept = _drop_dominated(kept, ctx)
    expr = kept[0] if len(kept) == 1 else Add(tuple((1, t) for t in kept))
    return Bound("O*", expr, b.family)


def ostar_tex(b: Bound, ctx: Context) -> str:
    return render_bound(ostar(b, ctx))


def _drop_poly_factors(term: Node, ctx: Context) -> Node:
    factors = list(term.factors) if isinstance(term, Mul) else [term]
    factors = [_drop_poly_exponent_terms(f, ctx) for f in factors]
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


def _drop_poly_exponent_terms(f: Node, ctx: Context) -> Node:
    """c^{x + a} = c^{x} c^{a}: drop the exponent terms a for which c^{a} is a polynomial
    factor, added or subtracted: 2^{t - 1} and 2^{t + 1} become 2^{t}. Only for a numeric
    base c: in n^{k + 1} or n^{k + o(1)} the exponent is what the result is about."""
    if not (isinstance(f, Pow) and isinstance(f.exp, Add) and isinstance(f.base, Num)):
        return f
    kept = tuple((s, a) for s, a in f.exp.terms if not _is_poly_factor(Pow(f.base, a), ctx))
    if len(kept) == len(f.exp.terms):
        return f
    if not kept:
        return num(1)
    exp = kept[0][1] if len(kept) == 1 and kept[0][0] > 0 else Add(kept)
    return Pow(f.base, exp)


# --- constants hidden by O(·) (20 November 2026) -------------------------------------


def hide_constants(node: Node, ctx: Context) -> Node:
    r"""Inside O(·) and o(·), write the argument in its simplest form up to constant factors:
    2^{O(2n (\log\log(2n))^2/\sqrt{\log(2n)})} becomes 2^{O(n (\log\log n)^2/\sqrt{\log n})}."""
    if isinstance(node, Asym):
        return Asym(node.kind, _theta(node.arg, ctx))
    if isinstance(node, Pow) and isinstance(node.exp, Asym):
        # x^{O(f)} = 2^{O(f log x)}: the base counts only as inside a log, (2n)^{O(1)} = n^{O(1)}
        base = _log_argument(node.base, ctx)
        return Pow(base if base is not None else node.base, hide_constants(node.exp, ctx))
    if isinstance(node, Add):
        return _absorb(_map(node, lambda c: hide_constants(c, ctx)), ctx)
    return _map(node, lambda c: hide_constants(c, ctx))


def _growth_term(node: Node):
    try:
        return bound_terms(Bound("O", node))[0]
    except (UnsupportedBound, Unspecified):
        return None


def _smaller(a: Node, b: Node, ctx: Context, strictly: bool) -> bool:
    """a = O(b) or, strictly, a = o(b): the second only for one and the same variable,
    since with several variables a ≤ b without b ≤ a (n against n k) need not be o(b)."""
    ga, gb = _growth_term(a), _growth_term(b)
    if ga is None or gb is None or not term_le(ga, gb, ctx, "exact"):
        return False
    if not strictly:
        return True
    return len(variables(a) | variables(b)) == 1 and not term_le(gb, ga, ctx, "exact")


def _absorb(node: Node, ctx: Context) -> Node:
    """f + h + O(g) = f + O(g) when h = O(g), and f + h + o(g) = f + o(g) when h = o(g),
    for added or subtracted h (21 November 2026): (2e)^{k 2^k - k + o(k 2^k - k)} is shown
    as (2e)^{k 2^k + o(k 2^k)}."""
    if not isinstance(node, Add):
        return node
    asym = [t for _, t in node.terms if isinstance(t, Asym)]
    if not asym:
        return node
    kept = tuple((s, t) for s, t in node.terms
                 if isinstance(t, Asym) or not _has_var(t)
                 or not any(_smaller(_theta(t, ctx), a.arg, ctx, a.kind == "o") for a in asym))
    if len(kept) == len(node.terms):
        return node
    if len(kept) == 1 and kept[0][0] > 0:
        return kept[0][1]
    return Add(kept)


def hide_constants_exact(b: Bound, ctx: Context) -> Bound:
    """A derived exact form under an outer O, O* or Õ: hide constants as inside O(·), term
    by term, and merge repeated terms; every term stays, such as a reduction's time (R7)."""
    expr = hide_constants(b.expr, ctx)
    if b.notation is None:
        return Bound(b.notation, expr, b.family)
    terms = expr.terms if isinstance(expr, Add) else ((1, expr),)
    if any(s < 0 for s, _ in terms):
        return Bound(b.notation, expr, b.family)
    out: list[Node] = []
    for _, t in terms:
        g = _theta(t, ctx)
        if g not in out and not (g == ONE and len(terms) > 1):
            out.append(g)
    expr = out[0] if len(out) == 1 else Add(tuple((1, g) for g in out))
    return Bound(b.notation, expr, b.family)


def _map(node: Node, fn) -> Node:
    if isinstance(node, Add):
        return Add(tuple((s, fn(t)) for s, t in node.terms))
    if isinstance(node, Mul):
        return Mul(tuple(fn(f) for f in node.factors))
    if isinstance(node, Div):
        return Div(fn(node.num), fn(node.den))
    if isinstance(node, Pow):
        return Pow(fn(node.base), fn(node.exp))
    if isinstance(node, Log):
        return Log(fn(node.arg), node.power, node.base)
    if isinstance(node, (Sqrt, Fact, Bell, Poly)):
        return type(node)(fn(node.arg))
    if isinstance(node, Asym):
        return Asym(node.kind, fn(node.arg))
    if isinstance(node, Func):
        return Func(node.name, fn(node.arg))
    return node


def _has_var(node: Node) -> bool:
    return isinstance(node, Var) or any(_has_var(c) for c in children(node))


ONE = num(1)


def _theta(node: Node, ctx: Context) -> Node:
    """A simplest expression g with node = Θ(g) as the variables grow: constant factors,
    constant terms, log bases, constant powers inside logs and dominated summands go."""
    if isinstance(node, Num):
        return ONE
    if isinstance(node, Mul):
        return _product([_theta(f, ctx) for f in node.factors])
    if isinstance(node, Div):
        n, d = _theta(node.num, ctx), _theta(node.den, ctx)
        return n if d == ONE else Div(n, d)
    if isinstance(node, Pow) and not _has_var(node.exp):
        base = _theta(node.base, ctx)
        if base == ONE:
            return ONE
        if isinstance(base, Mul) and isinstance(node.exp, Num):
            # (x y)^2 = x^2 y^2, so that equal terms written differently are merged
            e = node.exp.value
            return _product([Pow(f.base, num(f.exp.value * e)) if isinstance(f, Pow) and isinstance(f.exp, Num)
                             else Pow(f, node.exp) for f in base.factors])
        return _product([Pow(base, node.exp)])
    if isinstance(node, Sqrt):
        a = _theta(node.arg, ctx)
        return ONE if a == ONE else Sqrt(a)
    if isinstance(node, Log):
        a = _log_argument(node.arg, ctx)
        return Log(a, node.power, None) if a is not None else node
    if isinstance(node, Add):
        return _theta_sum(node, ctx)
    if isinstance(node, Asym):
        return Asym(node.kind, _theta(node.arg, ctx))
    return hide_constants(node, ctx)


def _log_argument(arg: Node, ctx: Context) -> Node | None:
    """log x up to a constant factor: log(c x^p y^q) = Θ(log(x y)). None if x is constant."""
    a = _theta(arg, ctx)
    if a == ONE:
        return None
    if isinstance(a, Add) and all(s > 0 for s, _ in a.terms):
        # log(k + p^2) = Θ(log(k + p))
        terms: list[Node] = []
        for _, s in a.terms:
            g = _strip_powers(s)
            if g not in terms:
                terms.append(g)
        terms = _drop_dominated_exact(terms, ctx)
        return terms[0] if len(terms) == 1 else Add(tuple((1, g) for g in terms))
    return _strip_powers(a)


def _strip_powers(a: Node) -> Node:
    """x^p y^q becomes x y: equal up to a constant factor inside a log."""
    factors = a.factors if isinstance(a, Mul) else (a,)
    return _product([f.base if isinstance(f, Pow) and not _has_var(f.exp) else f for f in factors])


def _theta_sum(node: Add, ctx: Context) -> Node:
    """A sum of nonnegative terms is Θ of the sum of their simplest forms, without constants
    and dominated terms. A sum that subtracts a term with variables keeps its form, apart
    from subtracted constants (n - 1 = Θ(n))."""
    if any(s < 0 and _has_var(t) for s, t in node.terms):
        # a - b = Θ(a) when b = o(a), in one variable: k 2^k - k = Θ(k 2^k) (21 November 2026)
        pos = [_theta(t, ctx) for s, t in node.terms if s > 0]
        if not all(any(_smaller(_theta(t, ctx), p, ctx, True) for p in pos)
                   for s, t in node.terms if s < 0 and _has_var(t)):
            return hide_constants(node, ctx)
    terms: list[Node] = []
    for s, t in node.terms:
        if s < 0:
            continue
        g = _theta(t, ctx)
        if g != ONE and g not in terms:
            terms.append(g)
    if not terms:
        return ONE
    terms = _drop_dominated_exact(terms, ctx)
    return terms[0] if len(terms) == 1 else Add(tuple((1, g) for g in terms))


def _drop_dominated_exact(terms: list[Node], ctx: Context) -> list[Node]:
    """Drop a summand at most a constant times another one (O(n^2 + n) = O(n^2))."""
    if len(terms) == 1:
        return terms
    analysed = []
    for t in terms:
        try:
            analysed.append(bound_terms(Bound("O", t))[0])
        except (UnsupportedBound, Unspecified):
            analysed.append(None)
    out = []
    for i, t in enumerate(terms):
        dominated = False
        for j in range(len(terms)):
            if i == j or analysed[i] is None or analysed[j] is None:
                continue
            if not term_le(analysed[i], analysed[j], ctx, "exact"):
                continue
            if term_le(analysed[j], analysed[i], ctx, "exact") and i < j:
                continue
            dominated = True
            break
        if not dominated:
            out.append(t)
    return out


def _product(factors: list[Node]) -> Node:
    """Multiply, collecting powers of equal bases (n · n = n^2) and dropping 1s."""
    powers: dict[Node, Fraction] = {}
    first: dict[Node, Node] = {}  # a base used once keeps its exponent as written
    count: dict[Node, int] = {}
    order: list[Node] = []
    for f in factors:
        for g in (f.factors if isinstance(f, Mul) else (f,)):
            if g == ONE:
                continue
            base, e = g, Fraction(1)
            if isinstance(g, Pow) and isinstance(g.exp, Num):
                base, e = g.base, g.exp.value
            elif isinstance(g, Pow):
                base, e = g, None  # a symbolic exponent: kept as it is
            if base not in count:
                order.append(base)
                first[base] = g
                count[base] = 0
            count[base] += 1
            if e is not None:
                powers[base] = powers.get(base, Fraction(0)) + e
    out: list[Node] = []
    for b in order:
        if count[b] == 1 or b not in powers:
            out.append(first[b])
        else:
            e = powers[b]
            out.append(b if e == 1 else Pow(b, num(e)))
    if not out:
        return ONE
    return out[0] if len(out) == 1 else Mul(tuple(out))


def _drop_dominated(terms: list[Node], ctx: Context) -> list[Node]:
    if len(terms) == 1:
        return terms
    analysed = []
    for t in terms:
        try:
            analysed.append(bound_terms(Bound("O*", t))[0])
        except UnsupportedBound:
            analysed.append(None)  # kept as it is, and used to drop nothing
    out = []
    for i, t in enumerate(terms):
        dominated = False
        for j in range(len(terms)):
            if i == j or analysed[i] is None or analysed[j] is None:
                continue
            if not term_le(analysed[i], analysed[j], ctx, "ostar"):
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
    if isinstance(node, Const) and node.deps:
        # ε_k depends on the parameters it is written with: k ↦ 2k keeps ε_k, k ↦ 3 makes it
        # a plain ε (20 November 2026)
        deps: list[str] = []
        for d in node.deps:
            for v in sorted(variables(mapping[d])) if d in mapping else [d]:
                if v not in deps:
                    deps.append(v)
        return Const(node.name, tuple(deps))
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
    if isinstance(node, Fact):
        return Fact(substitute(node.arg, mapping))
    if isinstance(node, Bell):
        return Bell(substitute(node.arg, mapping))
    return node


def substitute_bound(b: Bound, mapping: dict[str, Node]) -> Bound:
    return Bound(b.notation, simplify(substitute(b.expr, mapping)), b.family)


def simplify(node: Node) -> Node:
    """Light clean-up that keeps the natural form: flatten products, multiply numbers."""
    if isinstance(node, Mul):
        flat: list[Node] = []
        for f in (simplify(f) for f in node.factors):
            flat.extend(f.factors if isinstance(f, Mul) else [f])
        # numbers written as symbols, such as \pi, stay as they are: 2\pi, not 6.2832...
        nums = [f for f in flat if isinstance(f, Num) and not f.text.startswith("\\")]
        rest = [f for f in flat if not (isinstance(f, Num) and not f.text.startswith("\\"))]
        if len(nums) > 1:
            value = math.prod((n.value for n in nums), start=Fraction(1))
            nums = [num(value)]
        if nums and nums[0].value == 0:
            return nums[0]  # a zero factor: the product is 0
        if nums and nums[0].value == 1 and rest:
            nums = []
        out = nums + rest
        return out[0] if len(out) == 1 else Mul(tuple(out))
    if isinstance(node, Add):
        out = _collect(Add(tuple((s, simplify(t)) for s, t in node.terms)))
        if isinstance(out, Add):
            # a summand that simplified to 0, e.g. n(n - 1)/2 - n(n - 1)/2, is dropped
            terms = tuple((s, t) for s, t in out.terms if not _is_zero(t))
            if not terms:
                return num(0)
            if len(terms) == 1 and terms[0][0] > 0:
                return terms[0][1]
            out = Add(terms) if len(terms) != len(out.terms) else out
        return out
    if isinstance(node, Pow):
        return Pow(simplify(node.base), simplify(node.exp))
    if isinstance(node, Div):
        return Div(simplify(node.num), simplify(node.den))
    return node


def _is_zero(node: Node) -> bool:
    return isinstance(node, Num) and node.value == 0


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


SIZES = frozenset({"n", "m", "N"})


def exact_shape(b: Bound, ctx: Context) -> bool:
    """XP and pseudo-polynomial bounds are shown in their exact form, since O* hides what they
    are about (Serge, 20 November 2026): a power of an input size whose exponent has a
    parameter (n^{k + o(1)} and n^{k + 1} are the same in O*, as are 2^{O(k)} n^{tw + 1} and
    2^{O(k)} n^{tw}), or a bound polynomial in values that are not polynomially bounded
    (Subset Sum's O*(t) for three different results)."""
    expr = ostar(b, ctx).expr
    for node in _walk(expr):
        if isinstance(node, Pow):
            base, exp = variables(node.base), variables(node.exp)
            if base and base <= SIZES and exp - SIZES:
                return True
    names = variables(expr)
    if names and names <= set(ctx.not_poly_bounded):
        try:
            terms = bound_terms(Bound("O*", expr))
        except (UnsupportedBound, Unspecified):
            return False
        return all(a == 0 for t in terms for key in t.hi.terms for _, (a, _, _) in key)
    return False


def _walk(node: Node):
    yield node
    for c in children(node):
        yield from _walk(c)


def display(b: Bound, ctx: Context, derived: bool = False, notation: str | None = None) -> Display:
    """Stated bounds keep the paper's form; derived bounds get exact folds. If folding
    with rounded-up bases reads differently, it is offered as the hover (bounds §4). XP and
    pseudo-polynomial bounds are shown exactly (exact_shape): a stated one as stated, in its
    notation; a derived one with the constants that O(·) hides hidden and dominated terms
    (such as a reduction's time) dropped."""
    if exact_shape(b, ctx):
        if b.notation is None and notation is not None:
            b = Bound(notation, b.expr, b.family)  # the record's notation field, as stated
        if derived:
            exact = hide_constants_exact(b, ctx)
            terms = [t for _, t in exact.expr.terms] if isinstance(exact.expr, Add) else [exact.expr]
            if isinstance(exact.expr, Add) and all(s > 0 for s, _ in exact.expr.terms):
                terms = _drop_dominated_exact(terms, ctx)
                exact = Bound(exact.notation, terms[0] if len(terms) == 1 else Add(tuple((1, t) for t in terms)), exact.family)
        else:
            exact = b
        return Display(render_bound(exact), None)
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
