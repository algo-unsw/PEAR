"""Comparison of bounds (docs/specs/bounds.md §5).

`le(A, B)` holds when A's statement implies B's: for every choice of A's unknowns
(constants hidden by O(·) and O*, o(·) functions, ε) there is a choice of B's
unknowns with A = O(B) on all inputs. So a more precise bound beats a less precise
one: k^k beats n^{O(k)} under k ≤ n, and O(1.5^k + kn) beats O*(1.5^k).

Sound but incomplete: anything the comparator cannot prove is treated as
incomparable, so mistakes can only keep too many bounds, never drop a correct best one.
"""

from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Iterable, Sequence

from .expr import Bound, Div, Mul, Node, Num, Pow, Var, fixed_parameters, parse_expr, variables
from .numeric import interval
from .growth import (
    CONST_EXPRS,
    EPS,
    Coef,
    Growth,
    Key,
    Shape,
    Term,
    UnsupportedBound,
    bound_terms,
    is_monotone,
    value_growth,
)

ALWAYS_POLY = frozenset({"n", "m", "N"})


@dataclass(frozen=True)
class Context:
    """What a problem tells the comparator: its variables and their relations."""

    not_poly_bounded: frozenset[str] = frozenset()  # bounds B4: exceptions only
    # x ≤ y^p, from the problem's constraints (bounds B5), transitively closed
    le: dict[tuple[str, str], Fraction] = field(default_factory=dict)
    # x ≤ c y^p with c ≤ 1, for the pairs in `le` where c < 1: m ≤ n(n-1)/2 gives m ≤ n^2/2
    # (20 November 2026)
    coef: dict[tuple[str, str], Fraction] = field(default_factory=dict)
    # named constants: (best lower bound, best upper bound), from data/constants
    constants: dict[str, tuple[float, float]] = field(default_factory=dict)
    # expressions known to be nonnegative on every instance, as growths: large - small for
    # every constraint small <= large, and every parameter-map expression of a reduction
    # from this problem (it bounds a parameter of the produced instance, which is >= 0);
    # e.g. n(n-1)/2 - m for Clique (18 November 2026)
    nonneg: tuple[Growth, ...] = ()
    # every constraint as (small, large) growths, for checking that a witness lies in the
    # domain (disprove.py); `exact_domain` is False if some constraint could not be read
    domain: tuple[tuple[Growth, Growth], ...] = ()
    exact_domain: bool = True
    symbols: tuple[str, ...] = ()

    def poly_bounded(self, var: str) -> bool:
        return var in ALWAYS_POLY or var not in self.not_poly_bounded

    def relation(self, x: str, y: str) -> Fraction | None:
        """The smallest p with x ≤ y^p (p = 1 for x = y), or None."""
        return Fraction(1) if x == y else self.le.get((x, y))

    def scale(self, x: str, y: str) -> Fraction:
        """The c ≤ 1 with x ≤ c y^p for p = relation(x, y)."""
        return self.coef.get((x, y), Fraction(1))


class ConstraintError(ValueError):
    pass


def build_context(
    symbols: Iterable[str],
    constraints: Iterable[str] = (),
    not_poly_bounded: Iterable[str] = (),
    constants: dict[str, tuple[float, float]] | None = None,
    nonneg: Iterable[str] = (),
) -> Context:
    """Parse constraints such as 'k \\le n', 'm \\le n^{2}', 'n \\ge k', 'tw \\le n - 1'.
    `nonneg`: further expressions known to be nonnegative (parameter-map expressions)."""
    syms = set(symbols)
    edges: dict[tuple[str, str], tuple[Fraction, Fraction]] = {}  # (x, y) -> (p, c): x ≤ c y^p
    known: list[Growth] = []
    domain: list[tuple[Growth, Growth]] = []
    exact_domain = True
    for text in constraints:
        for x, y, p, c in _parse_constraint(text, syms):
            if (x, y) not in edges or (p, c) < edges[(x, y)]:
                edges[(x, y)] = (p, c)
        known += _constraint_gaps(text, syms)
        sides = _constraint_sides(text, syms)
        if sides is None:
            exact_domain = False
        else:
            domain += sides
    for text in nonneg:
        try:
            known.append(value_growth(parse_expr(text, syms)))
        except (UnsupportedBound, ValueError):
            pass
    # transitive closure: x ≤ c y^p and y ≤ d z^q give x ≤ c d^p z^{pq}
    changed = True
    while changed:
        changed = False
        for (x, y), (p, c) in list(edges.items()):
            for (y2, z), (q, d) in list(edges.items()):
                if y2 == y and x != z:
                    # d^p is kept only for an integer p (otherwise 1, which is weaker but sound)
                    e = c * d ** int(p) if p.denominator == 1 else c
                    r = (p * q, e)
                    if (x, z) not in edges or r < edges[(x, z)]:
                        edges[(x, z)] = r
                        changed = True
    useful = [g for g in known if any(c.sign < 0 for k, cs in g.terms.items() if k for c in cs)]
    le = {k: p for k, (p, _) in edges.items()}
    coef = {k: c for k, (_, c) in edges.items() if c < 1}
    return Context(frozenset(not_poly_bounded), le, coef=coef, constants=dict(constants or {}), nonneg=tuple(useful),
                   domain=tuple(domain), exact_domain=exact_domain, symbols=tuple(sorted(syms)))


def _constraint_sides(text: str, syms: set[str]) -> list[tuple[Growth, Growth]] | None:
    """(small, large) growths of a constraint ('=' gives both directions); None if unread."""
    for op, flip in (("\\le", False), ("\\ge", True), ("=", None)):
        if op in text:
            left, right = (s.strip() for s in text.split(op, 1))
            break
    else:
        return None
    try:
        lhs, rhs = value_growth(parse_expr(left, syms)), value_growth(parse_expr(right, syms))
    except (UnsupportedBound, ValueError):
        return None
    if flip is None:
        return [(lhs, rhs), (rhs, lhs)]
    return [(rhs, lhs)] if flip else [(lhs, rhs)]


def _constraint_gaps(text: str, syms: set[str]) -> list[Growth]:
    """large - small >= 0 for a constraint small <= large (both sides for '=')."""
    for op, flip in (("\\le", False), ("\\ge", True), ("=", None)):
        if op in text:
            left, right = (s.strip() for s in text.split(op, 1))
            break
    else:
        return []
    try:
        lhs, rhs = value_growth(parse_expr(left, syms)), value_growth(parse_expr(right, syms))
    except (UnsupportedBound, ValueError):
        return []
    if flip is None:
        return [rhs - lhs, lhs - rhs]
    return [lhs - rhs] if flip else [rhs - lhs]


def _parse_constraint(text: str, syms: set[str]) -> list[tuple[str, str, Fraction]]:
    for op, flip in (("\\le", False), ("\\ge", True), ("=", None)):
        if op in text:
            left, right = (s.strip() for s in text.split(op, 1))
            break
    else:
        raise ConstraintError(f"constraint needs \\le, \\ge or =: {text!r}")
    lhs, rhs = parse_expr(left, syms), parse_expr(right, syms)
    if flip:
        lhs, rhs = rhs, lhs
    pairs = [(lhs, rhs)] if flip is not None else [(lhs, rhs), (rhs, lhs)]
    out = []
    for small, large in pairs:
        if not isinstance(small, Var):
            continue  # only a single variable on the small side is used
        p = _upper_power(large)
        if p is not None:
            out.append((small.name, p[0], p[1], p[2]))
    return out


def _upper_power(node) -> tuple[str, Fraction, Fraction] | None:
    """If node ≤ c y^p for a single variable y (e.g. y, y^{2}, y - 1, y/2, y(y-1)/2), return
    (y, p, c): the highest power of y with coefficient c at most 1, and every other term
    negative."""
    try:
        g = value_growth(node)
    except UnsupportedBound:
        return None
    lead = [(k, cs) for k, cs in g.terms.items() if k]
    if not lead or any(len(k) != 1 or len(cs) != 1 or cs[0].kind != "exact" for k, cs in lead):
        return None
    ys = {k[0][0] for k, _ in lead}
    if len(ys) != 1 or any(k[0][1][1] or k[0][1][2] or k[0][1][0] <= 0 for k, _ in lead):
        return None  # one variable, pure powers (no logs)
    key, cs = max(lead, key=lambda kc: kc[0][0][1][0])
    (y, (a, _, _)), c = key[0], cs[0]
    if c.value > 1 + EPS:
        return None
    if any(k != key and cs2[0].sign > 0 for k, cs2 in lead):
        return None  # y^2 + y is not ≤ y^2
    rest = g.terms.get((), [])
    if any(r.sign > 0 for r in rest):
        return None  # y + 1 is not ≤ y
    return y, a, _exact_fraction(c.value)


class Relation(Enum):
    BETTER = "<"  # strictly better in O*, or equal in O* and better in exact form
    WORSE = ">"
    EQUAL = "="
    TIE = "~"  # equal in O*, exact forms incomparable (bounds B6)
    INCOMPARABLE = "?"  # neither is at most the other: a witness for each direction (bounds §5)
    UNDECIDED = "??"  # no proof and no witness for at least one direction (bounds §5)


# --- term level -----------------------------------------------------------------


def _hidden(key: Key, ctx: Context, mode: str) -> bool:
    """Monomials O* drops: O(log N) in polynomially bounded variables (bounds §4)."""
    if not key:
        return True
    if mode != "ostar" or len(key) != 1:
        return False
    var, (a, b, d) = key[0]
    if a != 0:
        return False
    if not ctx.poly_bounded(var):
        # A number given in binary has log x <= N, so polylog(x) is polynomial in N even
        # when x itself is not (e.g. log t for Subset Sum's target t).
        return b == 0 and d <= 1
    return b < 1 or (b == 1 and d <= 0)


def _reduce(g: Growth, ctx: Context, mode: str) -> Growth:
    return Growth({k: list(cs) for k, cs in g.terms.items() if not _hidden(k, ctx, mode)})


def visible_vars(term: Term, ctx: Context, mode: str = "ostar") -> set[str]:
    return _reduce(term.hi, ctx, mode).variables()


def term_le(a: Term, b: Term, ctx: Context, mode: str) -> bool:
    """Does term a's statement imply term b's? mode 'ostar' drops polynomial factors;
    'exact' keeps them, including the factors O* and Õ hide (as unknowns)."""
    if a.unspecified is not None:
        return False  # bounds B3: f(k) beats nothing
    if b.unspecified is not None:  # every explicit bound in the same parameter beats f(k)
        return visible_vars(a, ctx) <= set(b.unspecified)
    if b.lo is None:
        return False  # no safe lower estimate of b's term
    a_hi, b_lo = (a.hi, b.lo) if mode == "ostar" else (a.hi + a.hidden, b.lo + b.hidden)
    diff = _reduce(b_lo, ctx, mode) - _reduce(a_hi, ctx, mode)
    return _bounded_below(diff, ctx)


N_LOG: Key = (("N", (Fraction(0), Fraction(1), Fraction(0))),)


def _resolve(cs: list[Coef], ctx: Context) -> list[Coef] | None:
    """Replace named constants by their safe value: the lower bound where the term helps
    (positive), the upper bound where it hurts (negative). None if a value is unknown."""
    out = [c for c in cs if not c.kind.startswith("sym:")]
    extra = 0.0
    for c in cs:
        if c.kind.startswith("sym:"):
            name = c.kind[4:]
            if name.startswith("expr#"):
                # log2 of a constant base with named constants (growth.CONST_EXPRS)
                r = interval(CONST_EXPRS[name], ctx.constants) if name in CONST_EXPRS else None
                if r is None or r[0] <= 0:
                    return None
                lo, hi = math.log2(r[0]), math.log2(r[1])
            elif name in ctx.constants:
                lo, hi = ctx.constants[name]
            else:
                return None
            extra += c.value * (lo if c.value > 0 else hi)
    if abs(extra) > EPS:
        for i, c in enumerate(out):
            if c.kind == "exact":
                out[i] = Coef("exact", c.value + extra, c.shift)
                break
        else:
            out.append(Coef("exact", extra))
    return out


def _bounded_below(g: Growth, ctx: Context) -> bool:
    """Is g bounded below on the problem's domain? Decided by certificates (decide.py)."""
    from .decide import bounded_below

    return bounded_below(g, ctx).proved


def _dominates(pkey: Key, nkey: Key, ctx: Context) -> str | None:
    """'weak' if nkey ≤ pkey pointwise with equal shapes, 'strict' if nkey/pkey → 0."""
    pvars = dict(pkey)
    nvars = list(nkey)
    if len(nvars) > len(pvars):
        return None
    for targets in itertools.permutations(pvars, len(nvars)):
        weak = True
        # pointwise ≤ for variables ≥ 1 with the same logarithmic factors and no larger power:
        # n_G log n_H ≤ n_G n_H log n_H (20 November 2026)
        pointwise = True
        strict_ok = len(nvars) == 1 and len(pvars) == 1
        lex_less = False
        for (x, shape), y in zip(nvars, targets):
            p = ctx.relation(x, y)
            if p is None:
                weak = strict_ok = pointwise = False
                break
            moved = _transport(shape, p)
            if moved is None:  # only exact transport keeps coefficients
                weak = pointwise = False
                moved = (shape[0] * p, shape[1], shape[2])
            target = pvars[y]
            if not (moved[1:] == target[1:] and moved[0] <= target[0] and min(target[1:]) >= 0):
                pointwise = False
            if moved != target:
                weak = False
            if moved < target:
                lex_less = True
            elif moved > target:
                strict_ok = False
                weak = False
        else:
            if len(nvars) == 1 and not strict_ok:
                # Collapse the larger side onto the single variable: if x ≤ y and y ≤ z,
                # a factor in z is at least the same factor in y (shapes are nonnegative).
                collapsed = _collapse(pkey, targets[0], ctx)
                if collapsed is not None:
                    x, shape = nvars[0]
                    p = ctx.relation(x, targets[0])
                    moved = _transport(shape, p) or (shape[0] * p, shape[1], shape[2])
                    if moved < collapsed:
                        return "strict"
                    if moved == collapsed:
                        return "weak"
            extra_ok = all(any(s) and min(s) >= 0 for y, s in pkey if y not in targets)
            if weak and extra_ok:
                return "weak"
            if strict_ok and lex_less:
                return "strict"
            if pointwise and extra_ok:
                return "weak"  # coefficients still have to compare
    return None


def _collapse(pkey: Key, y: str, ctx: Context) -> Shape | None:
    """Lower-bound a monomial by one in y alone, using y ≤ z for every other variable z."""
    total = [Fraction(0), Fraction(0), Fraction(0)]
    for z, s in pkey:
        if min(s) < 0:
            return None
        if z != y and ctx.relation(y, z) != 1:
            return None
        total = [total[i] + s[i] for i in range(3)]
    return (total[0], total[1], total[2])


def _transport(shape: Shape, p: Fraction) -> Shape | None:
    """x ≤ y^p turns x^α (log x)^β (loglog x)^γ into y^{pα}, exactly only if β = γ = 0 or p = 1."""
    a, b, d = shape
    if p == 1:
        return shape
    if b == 0 and d == 0:
        return (a * p, b, d)
    return None


# --- bound level ------------------------------------------------------------------


@dataclass(frozen=True)
class Analysed:
    bound: Bound
    terms: tuple[Term, ...] | None  # None: outside the supported class, so incomparable
    fixed: frozenset[str] = frozenset()  # stated for every fixed value of these (ε_k)


def analyse(b: Bound) -> Analysed:
    from .display import hide_constants  # local import: display imports this module

    fixed = fixed_parameters(b.expr)
    # O(·) hides constants, so O(2n/\log(2n)) and O(n/\log n) are the same statement; the
    # simpler one is in the normal form's class (bounds §4, 20 November 2026)
    plain = Bound(b.notation, hide_constants(b.expr, Context()), b.family)
    try:
        return Analysed(b, tuple(bound_terms(plain)), fixed)
    except UnsupportedBound:
        return Analysed(b, None, fixed)


def le(a: Analysed, b: Analysed, ctx: Context, mode: str) -> bool:
    """A = O(B): every term of A is dominated by a single term of B (bounds §5.1), possibly
    after raising A's variables along the constraints (bounds §5, item 9)."""
    if a.terms is None or b.terms is None:
        return False
    if a.fixed != b.fixed:
        # a bound for every fixed k (ε_k, hidden constants depending on k) is compared only
        # with bounds fixed in the same parameters (bounds §2, 17 November 2026)
        return False
    if _le_terms(a, b, ctx, mode):
        return True
    return any(_le_terms(r, b, ctx, mode) for r in _raised(a, b, ctx))


def _le_terms(a: Analysed, b: Analysed, ctx: Context, mode: str) -> bool:
    assert a.terms is not None and b.terms is not None
    if a.bound == b.bound and all(t.unspecified is None for t in a.terms):  # B3: f(k) beats nothing
        return True  # identical statements imply each other, even where the estimates of a
        # factor differ above and below (Bell numbers)
    return all(any(term_le(x, y, ctx, mode) for y in b.terms) for x in a.terms)


MAX_RAISINGS = 16


def _raised(a: Analysed, b: Analysed, ctx: Context) -> list[Analysed]:
    """A with each variable x that B does not use replaced by y^p for a variable y of B with
    x ≤ y^p, if A is nondecreasing in every variable: then A(x) ≤ A(y^p), so A ≤ B follows
    from A(y^p) ≤ B. The monomial check alone cannot see k! 2^{o(k)} ≤ n! 2^{o(n)} for k ≤ n
    (Stirling's x! has a negative x log e term), nor n^k ≤ n^n (20 November 2026)."""
    a_vars = variables(a.bound.expr)
    b_vars = variables(b.bound.expr)
    extra = sorted(a_vars - b_vars)
    if not extra or not b_vars or not _monotone(a.bound):
        return []
    options: list[list[tuple[str, Fraction, Fraction]]] = []
    for x in extra:
        targets = [(y, p, ctx.scale(x, y)) for y in sorted(b_vars) if (p := ctx.relation(x, y)) is not None]
        if not targets:
            return []  # x would stay, and B does not bound it
        options.append(targets)
    out = []
    for choice in itertools.islice(itertools.product(*options), MAX_RAISINGS):
        mapping = tuple((x, y, p, c) for x, (y, p, c) in zip(extra, choice))
        r = _raise(a.bound, mapping)
        if r is not None and r.terms is not None and r.fixed == b.fixed:
            out.append(r)
    return out


@functools.lru_cache(maxsize=65536)
def _monotone(b: Bound) -> bool:
    return is_monotone(b)


@functools.lru_cache(maxsize=65536)
def _raise(b: Bound, mapping: tuple[tuple[str, str, Fraction, Fraction], ...]) -> Analysed | None:
    from .display import simplify, substitute  # local import: display imports this module

    subst = {x: power_of(y, p, c) for x, y, p, c in mapping}
    try:
        return analyse(Bound(b.notation, simplify(substitute(b.expr, subst)), b.family))
    except Exception:  # noqa: BLE001 - outside the supported class: no conclusion
        return None


def power_of(y: str, p: Fraction, c: Fraction = Fraction(1)) -> Node:
    """c y^p, written y, y^{2}, y^{2}/2 or 0.5 y."""
    core: Node = Var(y) if p == 1 else Pow(Var(y), Num(Fraction(p), _fraction_text(Fraction(p))))
    if c == 1:
        return core
    inv = 1 / c
    if inv.denominator == 1:
        return Div(core, Num(inv, _fraction_text(inv)))
    return Mul((Num(c, _fraction_text(c)), core))


def _exact_fraction(v: float) -> Fraction:
    """A float coefficient from a constraint, as the nearby simple fraction (1/2, 1/4), never
    below the float (a larger coefficient is a weaker, still valid constraint)."""
    f = Fraction(v).limit_denominator(1000)
    return f if f >= Fraction(v) or abs(f - Fraction(v)) < Fraction(1, 10**12) else Fraction(v)


def _fraction_text(p: Fraction) -> str:
    return str(p.numerator) if p.denominator == 1 else f"{p.numerator}/{p.denominator}"


# --- disproof: witnesses that A is not at most B (bounds §5) -----------------------------


def refuted(a: Analysed, b: Analysed, ctx: Context, mode: str) -> str | None:
    """Why A ⪯ B fails, if it can be shown: a rule (B3, fixed parameters) or a slice of the
    domain along which some term of A outgrows every term of B (faster than any polynomial
    in O* mode)."""
    from .disprove import POLY3, ZERO3, slices, leading_terms, tends_to_minus_infinity

    if a.terms is None or b.terms is None:
        return None
    if a.fixed != b.fixed:
        return "fixed parameters differ (bounds §2)"
    if any(t.unspecified is not None for t in a.terms):
        return "f(k) beats nothing (B3)"
    if any(t.unspecified is not None for t in b.terms):
        return "explicit bounds in other parameters do not beat f(k) (B3)"
    ranges: dict[str, tuple[float, float]] = {}
    for t in (*a.terms, *b.terms):
        for g in (t.hi, t.lo):
            for cs in (g.terms.values() if g is not None else ()):
                for c in cs:
                    if c.kind.startswith("sym:expr#"):
                        name = c.kind[4:]
                        r = interval(CONST_EXPRS[name], ctx.constants) if name in CONST_EXPRS else None
                        if r is None or r[0] <= 0:
                            return None
                        ranges[name] = (math.log2(r[0]) - 1e-9, math.log2(r[1]) + 1e-9)
    if mode == "ostar" and any(not ctx.poly_bounded(v) for t in (*a.terms, *b.terms) for v in t.vars):
        return None  # O* hides polynomials in N only: no slice reasoning about such variables
    above = POLY3 if mode == "ostar" else ZERO3
    names = sorted(ctx.constants)
    scenarios = [dict(zip(names, ends)) for ends in itertools.product(*[ctx.constants[n] for n in names])] or [{}]
    for ta in a.terms:
        if ta.lo is None:
            continue
        for values in scenarios:
            gs = []
            for tb in b.terms:
                hi_b = tb.hi if mode == "ostar" else tb.hi + tb.hidden
                lo_a = ta.lo if mode == "ostar" else ta.lo + ta.hidden
                gs.append(_reduce(hi_b, ctx, mode) - _reduce(lo_a, ctx, mode))
            names_g = set(ctx.symbols) | {v for g in gs for k in g.terms for v, _ in k}
            for sl in slices(ctx, names_g):
                ok = True
                for g in gs:
                    terms = leading_terms(g, sl, values, ranges)
                    if terms is None or not tends_to_minus_infinity(terms, above):
                        ok = False
                        break
                if ok:
                    return f"witness: {sl.label()}"
    return None


def le_status(a: Analysed, b: Analysed, ctx: Context, mode: str) -> str:
    """proved | refuted | unknown."""
    if le(a, b, ctx, mode):
        return "proved"
    return "refuted" if refuted(a, b, ctx, mode) is not None else "unknown"


def compare(a: Bound | Analysed, b: Bound | Analysed, ctx: Context, witnesses: bool = True) -> Relation:
    """`witnesses=False` skips the search that tells INCOMPARABLE from UNDECIDED (both are
    then reported as UNDECIDED), for callers that only act on an order."""
    a = a if isinstance(a, Analysed) else analyse(a)
    b = b if isinstance(b, Analysed) else analyse(b)
    ab, ba = le(a, b, ctx, "ostar"), le(b, a, ctx, "ostar")
    if not ab and not ba:
        return _unordered(a, b, ctx) if witnesses else Relation.UNDECIDED
    if ab and ba:  # equal in O*: compare exact forms (bounds §5.4)
        ab, ba = le(a, b, ctx, "exact"), le(b, a, ctx, "exact")
        if ab and ba:
            return Relation.EQUAL
        if ab:
            return Relation.BETTER
        if ba:
            return Relation.WORSE
        return Relation.TIE
    if ab:
        return Relation.BETTER
    if ba:
        return Relation.WORSE
    return Relation.INCOMPARABLE


def compare_ostar(a: Bound | Analysed, b: Bound | Analysed, ctx: Context, witnesses: bool = True) -> Relation:
    """Compare O* forms only (what the Overview tab shows)."""
    a = a if isinstance(a, Analysed) else analyse(a)
    b = b if isinstance(b, Analysed) else analyse(b)
    ab, ba = le(a, b, ctx, "ostar"), le(b, a, ctx, "ostar")
    if ab and ba:
        return Relation.EQUAL
    if ab:
        return Relation.BETTER
    if ba:
        return Relation.WORSE
    return _unordered(a, b, ctx) if witnesses else Relation.UNDECIDED


_UNORDERED: dict[tuple, Relation] = {}


def _unordered(a: Analysed, b: Analysed, ctx: Context) -> Relation:
    """Neither is proved at most the other: incomparable with a witness each way, else
    undecided."""
    key = (a.bound, b.bound, id(ctx))
    got = _UNORDERED.get(key)
    if got is None:
        both = refuted(a, b, ctx, "ostar") is not None and refuted(b, a, ctx, "ostar") is not None
        got = _UNORDERED[key] = Relation.INCOMPARABLE if both else Relation.UNDECIDED
        _KEEP_CTX[id(ctx)] = ctx
    return got


_KEEP_CTX: dict[int, Context] = {}


def best(bounds: Sequence[Bound | Analysed], ctx: Context) -> list[int]:
    """Indices of the bounds no other bound strictly beats (an antichain)."""
    items = [x if isinstance(x, Analysed) else analyse(x) for x in bounds]
    keep = []
    for i, x in enumerate(items):
        if not any(compare(y, x, ctx) == Relation.BETTER for j, y in enumerate(items) if j != i):
            keep.append(i)
    return keep
