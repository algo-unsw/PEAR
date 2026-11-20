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

from .expr import Bound, Num, Pow, Var, fixed_parameters, parse_expr, variables
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
    exact,
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
    # named constants: (best lower bound, best upper bound), from data/constants
    constants: dict[str, tuple[float, float]] = field(default_factory=dict)
    # expressions known to be nonnegative on every instance, as growths: large - small for
    # every constraint small <= large, and every parameter-map expression of a reduction
    # from this problem (it bounds a parameter of the produced instance, which is >= 0);
    # e.g. n(n-1)/2 - m for Clique (18 November 2026)
    nonneg: tuple[Growth, ...] = ()

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
    nonneg: Iterable[str] = (),
) -> Context:
    """Parse constraints such as 'k \\le n', 'm \\le n^{2}', 'n \\ge k', 'tw \\le n - 1'.
    `nonneg`: further expressions known to be nonnegative (parameter-map expressions)."""
    syms = set(symbols)
    edges: dict[tuple[str, str], Fraction] = {}
    known: list[Growth] = []
    for text in constraints:
        for x, y, p in _parse_constraint(text, syms):
            if (x, y) not in edges or p < edges[(x, y)]:
                edges[(x, y)] = p
        known += _constraint_gaps(text, syms)
    for text in nonneg:
        try:
            known.append(value_growth(parse_expr(text, syms)))
        except (UnsupportedBound, ValueError):
            pass
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
    useful = [g for g in known if any(c.sign < 0 for k, cs in g.terms.items() if k for c in cs)]
    return Context(frozenset(not_poly_bounded), edges, dict(constants or {}), tuple(useful))


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
            out.append((small.name, p[0], p[1]))
    return out


def _upper_power(node) -> tuple[str, Fraction] | None:
    """If node ≤ y^p for a single variable y (e.g. y, y^{2}, y - 1, y/2, y(y-1)/2), return
    (y, p): the highest power of y with coefficient at most 1, and every other term negative."""
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
    """Is this sum of monomials bounded below on all inputs? Sound, incomplete. Besides the
    monomial check, g is bounded below if g - λE is, for an expression E known to be
    nonnegative and λ >= 0 (18 November 2026): e.g. 2^{X} beats 1.1996^{X} only if X >= 0."""
    if _bounded_below_terms(g, ctx):
        return True
    for e in ctx.nonneg:
        for lam in _multipliers(g, e):
            if _bounded_below_terms(g - e.scale(exact(lam)), ctx):
                return True
    return False


def _multipliers(g: Growth, e: Growth) -> list[float]:
    """Candidate λ > 0 that cancel a negative monomial of e against the same one in g."""
    out = []
    for key, ecs in e.terms.items():
        if not key or key not in g.terms:
            continue
        ev = [c for c in ecs if c.kind == "exact"]
        gv = [c for c in g.terms[key] if c.kind == "exact"]
        if len(ev) == 1 and len(gv) == 1 and ev[0].value < 0 and gv[0].value < 0:
            out.append(gv[0].value / ev[0].value)
    return sorted(set(out))


def _bounded_below_terms(g: Growth, ctx: Context) -> bool:
    """The monomial check: positive coefficients come from the bound that should be larger
    (its unknowns may be chosen), negative ones from the other (its unknowns are arbitrary)."""
    pos: list[list] = []  # [key, coef, strict]: strict once it has beaten a smaller shape
    neg: list[tuple[Key, Coef]] = []
    g = _cancel_named(g, ctx)
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
    for c in pos:
        c.append(False)
    neg.sort(key=lambda kc: _size(kc[0]), reverse=True)
    for nkey, ncoef in neg:
        for slot in pos:
            pkey, pcoef, strict = slot
            if pkey == N_LOG and pcoef.kind == "big" and _hidden(nkey, ctx, "ostar"):
                break  # the polynomial O* hides absorbs any polynomial factor
            dom = _dominates(pkey, nkey, ctx)
            if dom is None:
                continue
            if dom == "strict" and pcoef.sign > 0:
                # A larger shape with a positive coefficient beats any smaller one, but only
                # if that coefficient stays positive: once used this way, the slot may not be
                # used up by monomials of its own shape (20 November 2026: k log n - tw log n
                # - c k is not bounded below when tw = k).
                slot[2] = True
                break
            absorbed, rest = _absorb_same(pcoef, ncoef)
            if absorbed and strict and not _positive(rest):
                continue
            if absorbed:
                slot[1] = rest
                break
        else:
            return False
    return True


def _positive(c: Coef) -> bool:
    """Is c a positive constant (not merely a positive infinitesimal)?"""
    if c.kind == "exact":
        return c.value > EPS
    return c.sign > 0 and not c.infinitesimal


def _cancel_named(g: Growth, ctx: Context) -> Growth:
    """Cancel a negative multiple of a positive named constant (ω) against a positive multiple
    of the same constant on a monomial at least as large: ω x ≤ ω y when x ≤ y, whatever ω
    is (20 November 2026: (n_G n_H)^{ω k/3} ≤ (n_G n_H)^{ω n_G n_H/3} for k ≤ n_G)."""
    terms = {k: list(cs) for k, cs in g.terms.items()}
    changed = False
    for nkey in list(terms):
        for i, nc in enumerate(terms[nkey]):
            name = nc.kind[4:] if nc.kind.startswith("sym:") else None
            if name is None or nc.value >= 0 or name not in ctx.constants or ctx.constants[name][0] <= 0:
                continue
            for pkey, pcs in terms.items():
                if pkey == nkey or not pkey:
                    continue
                j = next((j for j, pc in enumerate(pcs) if pc.kind == nc.kind and pc.value + nc.value >= -EPS), None)
                if j is None or _dominates(pkey, nkey, ctx) is None:
                    continue
                pcs[j] = Coef(nc.kind, pcs[j].value + nc.value)
                terms[nkey][i] = Coef(nc.kind, 0.0)
                changed = True
                break
    if not changed:
        return g
    return Growth({k: [c for c in cs if not (c.kind.startswith("sym:") and abs(c.value) <= EPS)]
                   for k, cs in terms.items()})


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
    fixed = fixed_parameters(b.expr)
    try:
        return Analysed(b, tuple(bound_terms(b)), fixed)
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
    options: list[list[tuple[str, Fraction]]] = []
    for x in extra:
        targets = [(y, p) for y in sorted(b_vars) if (p := ctx.relation(x, y)) is not None]
        if not targets:
            return []  # x would stay, and B does not bound it
        options.append(targets)
    out = []
    for choice in itertools.islice(itertools.product(*options), MAX_RAISINGS):
        mapping = tuple((x, y, p) for x, (y, p) in zip(extra, choice))
        r = _raise(a.bound, mapping)
        if r is not None and r.terms is not None and r.fixed == b.fixed:
            out.append(r)
    return out


@functools.lru_cache(maxsize=65536)
def _monotone(b: Bound) -> bool:
    return is_monotone(b)


@functools.lru_cache(maxsize=65536)
def _raise(b: Bound, mapping: tuple[tuple[str, str, Fraction], ...]) -> Analysed | None:
    from .display import simplify, substitute  # local import: display imports this module

    subst = {x: Var(y) if p == 1 else Pow(Var(y), Num(Fraction(p), _fraction_text(Fraction(p)))) for x, y, p in mapping}
    try:
        return analyse(Bound(b.notation, simplify(substitute(b.expr, subst)), b.family))
    except Exception:  # noqa: BLE001 - outside the supported class: no conclusion
        return None


def _fraction_text(p: Fraction) -> str:
    return str(p.numerator) if p.denominator == 1 else f"{p.numerator}/{p.denominator}"


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
    return Relation.INCOMPARABLE


def best(bounds: Sequence[Bound | Analysed], ctx: Context) -> list[int]:
    """Indices of the bounds no other bound strictly beats (an antichain)."""
    items = [x if isinstance(x, Analysed) else analyse(x) for x in bounds]
    keep = []
    for i, x in enumerate(items):
        if not any(compare(y, x, ctx) == Relation.BETTER for j, y in enumerate(items) if j != i):
            keep.append(i)
    return keep
