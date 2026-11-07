"""Comparison of bounds (docs/specs/bounds.md §5).

`le(A, B)` holds when A's statement implies B's: for every choice of A's unknowns
(constants hidden by O(·) and O*, o(·) functions, ε) there is a choice of B's
unknowns with A = O(B) on all inputs. So a more precise bound beats a less precise
one: k^k beats n^{O(k)} under k ≤ n, and O(1.5^k + kn) beats O*(1.5^k).

Sound but incomplete: anything the comparator cannot prove is treated as
incomparable, so mistakes can only keep too many bounds, never drop a correct best one.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Iterable, Sequence

from .expr import Bound, Var, parse_expr
from .growth import (
    EPS,
    Coef,
    Growth,
    Key,
    Shape,
    Term,
    UnsupportedBound,
    bound_terms,
    value_growth,
)

ALWAYS_POLY = frozenset({"n", "m", "N"})


@dataclass(frozen=True)
class Context:
    """What a problem tells the comparator: its variables and their relations."""

    not_poly_bounded: frozenset[str] = frozenset()  # bounds B4: exceptions only
    # x ≤ y^p, from the problem's constraints (bounds B5), transitively closed
    le: dict[tuple[str, str], Fraction] = field(default_factory=dict)
    # named constants: (best lower bound, best upper bound), from data/constants
    constants: dict[str, tuple[float, float]] = field(default_factory=dict)

    def poly_bounded(self, var: str) -> bool:
        return var in ALWAYS_POLY or var not in self.not_poly_bounded

    def relation(self, x: str, y: str) -> Fraction | None:
        """The smallest p with x ≤ y^p (p = 1 for x = y), or None."""
        return Fraction(1) if x == y else self.le.get((x, y))


class ConstraintError(ValueError):
    pass


def build_context(
    symbols: Iterable[str],
    constraints: Iterable[str] = (),
    not_poly_bounded: Iterable[str] = (),
    constants: dict[str, tuple[float, float]] | None = None,
) -> Context:
    """Parse constraints such as 'k \\le n', 'm \\le n^{2}', 'n \\ge k', 'tw \\le n - 1'."""
    syms = set(symbols)
    edges: dict[tuple[str, str], Fraction] = {}
    for text in constraints:
        for x, y, p in _parse_constraint(text, syms):
            if (x, y) not in edges or p < edges[(x, y)]:
                edges[(x, y)] = p
    # transitive closure: x ≤ y^p and y ≤ z^q give x ≤ z^{pq}
    changed = True
    while changed:
        changed = False
        for (x, y), p in list(edges.items()):
            for (y2, z), q in list(edges.items()):
                if y2 == y and x != z:
                    r = p * q
                    if (x, z) not in edges or r < edges[(x, z)]:
                        edges[(x, z)] = r
                        changed = True
    return Context(frozenset(not_poly_bounded), edges, dict(constants or {}))


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
            out.append((small.name, p[0], p[1]))
    return out


def _upper_power(node) -> tuple[str, Fraction] | None:
    """If node ≤ y^p for a single variable y (e.g. y, y^{2}, y - 1, y/2), return (y, p)."""
    try:
        g = value_growth(node)
    except UnsupportedBound:
        return None
    lead = [(k, cs) for k, cs in g.terms.items() if k]
    if len(lead) != 1:
        return None
    key, cs = lead[0]
    if len(key) != 1 or len(cs) != 1 or cs[0].kind != "exact":
        return None
    (y, (a, b, d)), c = key[0], cs[0]
    if b or d or a <= 0 or c.value > 1 + EPS:
        return None
    rest = g.terms.get((), [])
    if any(r.sign > 0 for r in rest):
        return None  # y + 1 is not ≤ y
    return y, a


class Relation(Enum):
    BETTER = "<"  # strictly better in O*, or equal in O* and better in exact form
    WORSE = ">"
    EQUAL = "="
    TIE = "~"  # equal in O*, exact forms incomparable (bounds B6)
    INCOMPARABLE = "?"


# --- term level -----------------------------------------------------------------


def _hidden(key: Key, ctx: Context, mode: str) -> bool:
    """Monomials O* drops: O(log N) in polynomially bounded variables (bounds §4)."""
    if not key:
        return True
    if mode != "ostar" or len(key) != 1:
        return False
    var, (a, b, d) = key[0]
    if not ctx.poly_bounded(var) or a != 0:
        return False
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
            if name not in ctx.constants:
                return None
            lo, hi = ctx.constants[name]
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
    """Is this sum of monomials bounded below on all inputs? Positive coefficients come
    from the bound that should be larger (its unknowns may be chosen), negative ones
    from the other (its unknowns are arbitrary). Sound, incomplete."""
    pos: list[list] = []  # [key, coef]
    neg: list[tuple[Key, Coef]] = []
    for key, raw in g.terms.items():
        if not key:
            continue
        cs = _resolve(raw, ctx)
        if cs is None:
            return False
        for c in cs:
            if c.sign > 0:
                pos.append([key, c])
            elif c.sign < 0:
                neg.append((key, c))
    neg.sort(key=lambda kc: _size(kc[0]), reverse=True)
    for nkey, ncoef in neg:
        for slot in pos:
            pkey, pcoef = slot
            if pkey == N_LOG and pcoef.kind == "big" and _hidden(nkey, ctx, "ostar"):
                break  # the polynomial O* hides absorbs any polynomial factor
            dom = _dominates(pkey, nkey, ctx)
            if dom is None:
                continue
            if dom == "strict" and pcoef.sign > 0:
                break  # a larger shape with any positive coefficient wins
            absorbed, rest = _absorb_same(pcoef, ncoef)
            if absorbed:
                slot[1] = rest
                break
        else:
            return False
    return True


def _size(key: Key) -> Shape:
    return max((s for _, s in key), default=(Fraction(0), Fraction(0), Fraction(0)))


def _absorb_same(p: Coef, n: Coef) -> tuple[bool, Coef]:
    """Can p·m absorb n·m (n negative) for the same monomial m? Returns what is left."""
    if p.kind == "exact" and n.kind == "exact":
        need, need_shift = -n.value, -n.shift
        if p.value > need + EPS or (abs(p.value - need) <= EPS and p.shift >= need_shift):
            v = p.value + n.value
            s = p.shift + n.shift
            return True, Coef("exact", v, (s > 0) - (s < 0))
        return False, p
    if p.kind == "big":
        return True, p  # an unknown constant can be chosen as large as needed
    if n.infinitesimal and not p.infinitesimal and p.sign > 0:
        return True, p  # any positive constant beats an infinitesimal
    if p.kind == "small":
        return n.kind == "small", p  # o(x) implies o(x); a family does not give one o(x)
    if p.sign > 0 and n.kind in ("small", "family"):
        return True, p  # 2^{o(n)} implies the family form; equal families coincide
    return False, p


def _dominates(pkey: Key, nkey: Key, ctx: Context) -> str | None:
    """'weak' if nkey ≤ pkey pointwise with equal shapes, 'strict' if nkey/pkey → 0."""
    pvars = dict(pkey)
    nvars = list(nkey)
    if len(nvars) > len(pvars):
        return None
    for targets in itertools.permutations(pvars, len(nvars)):
        weak = True
        strict_ok = len(nvars) == 1 and len(pvars) == 1
        lex_less = False
        for (x, shape), y in zip(nvars, targets):
            p = ctx.relation(x, y)
            if p is None:
                weak = strict_ok = False
                break
            moved = _transport(shape, p)
            if moved is None:  # only exact transport keeps coefficients
                weak = False
                moved = (shape[0] * p, shape[1], shape[2])
            target = pvars[y]
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
            if weak and all(any(s) and min(s) >= 0 for y, s in pkey if y not in targets):
                return "weak"
            if strict_ok and lex_less:
                return "strict"
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


def analyse(b: Bound) -> Analysed:
    try:
        return Analysed(b, tuple(bound_terms(b)))
    except UnsupportedBound:
        return Analysed(b, None)


def le(a: Analysed, b: Analysed, ctx: Context, mode: str) -> bool:
    """A = O(B): every term of A is dominated by a single term of B (bounds §5.1)."""
    if a.terms is None or b.terms is None:
        return False
    return all(any(term_le(x, y, ctx, mode) for y in b.terms) for x in a.terms)


def compare(a: Bound | Analysed, b: Bound | Analysed, ctx: Context) -> Relation:
    a = a if isinstance(a, Analysed) else analyse(a)
    b = b if isinstance(b, Analysed) else analyse(b)
    ab, ba = le(a, b, ctx, "ostar"), le(b, a, ctx, "ostar")
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


def compare_ostar(a: Bound | Analysed, b: Bound | Analysed, ctx: Context) -> Relation:
    """Compare O* forms only (what the default display shows)."""
    a = a if isinstance(a, Analysed) else analyse(a)
    b = b if isinstance(b, Analysed) else analyse(b)
    ab, ba = le(a, b, ctx, "ostar"), le(b, a, ctx, "ostar")
    if ab and ba:
        return Relation.EQUAL
    if ab:
        return Relation.BETTER
    if ba:
        return Relation.WORSE
    return Relation.INCOMPARABLE


def best(bounds: Sequence[Bound | Analysed], ctx: Context) -> list[int]:
    """Indices of the bounds no other bound strictly beats (an antichain)."""
    items = [x if isinstance(x, Analysed) else analyse(x) for x in bounds]
    keep = []
    for i, x in enumerate(items):
        if not any(compare(y, x, ctx) == Relation.BETTER for j, y in enumerate(items) if j != i):
            keep.append(i)
    return keep
