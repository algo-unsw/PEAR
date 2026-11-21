"""Witnesses that a comparison fails (docs/specs/bounds.md §5).

A witness is a **slice** of the domain: every variable set to a polynomial in one variable t
with rational coefficients (t, t/2, 2t, t - 3, 3, 2, √t, t^2/4, t(t-1)/2, t^2) such that
every constraint of the problem holds for all large t (checked exactly). Along a slice a
growth g = log2 B - log2 A becomes a function of t:

- monomials that are polynomials in the variables, with exact coefficients, are expanded
  exactly (so n(n-1)/2 - m is exactly 0 for m = t(t-1)/2, n = t);
- every other monomial is replaced by its leading term c t^a (log t)^b (log log t)^g, and the
  comparison does not look below the leading growth of such a term (its corrections are
  unknown).

g tends to -∞ when its leading term is certainly negative: an O(·) constant of A that nothing
of B matches, or a negative coefficient. Then A ⪯ B fails along the slice. Anything in doubt
(a cancellation of approximate terms, an o(·) of A, a coefficient within 10^-9 of 0) is no
witness, so the comparison stays undecided.
"""

from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass
from fractions import Fraction

from .growth import Coef, Growth

Growth3 = tuple[Fraction, Fraction, Fraction]  # t^a (log t)^b (log log t)^g
UPoly = dict[Fraction, Fraction]  # Σ coef t^exponent

F = Fraction
MENU: dict[str, UPoly] = {
    "t": {F(1): F(1)},
    "t/2": {F(1): F(1, 2)},
    "2t": {F(1): F(2)},
    "t-3": {F(1): F(1), F(0): F(-3)},
    "3": {F(0): F(3)},
    "2": {F(0): F(2)},
    "sqrt t": {F(1, 2): F(1)},
    "t^2/4": {F(2): F(1, 4)},
    "t(t-1)/2": {F(2): F(1, 2), F(1): F(-1, 2)},
    "t^2": {F(2): F(1)},
}
TOL = 1e-9
ZERO3: Growth3 = (F(0), F(0), F(0))
POLY3: Growth3 = (F(0), F(1), F(0))  # log t: a polynomial factor in log space


@dataclass(frozen=True)
class Slice:
    assign: tuple[tuple[str, str], ...]  # variable -> menu label

    def label(self) -> str:
        return ", ".join(f"{v} = {lab}" for v, lab in self.assign)


# --- one variable ----------------------------------------------------------------------------


@functools.lru_cache(maxsize=65536)
def _leading_var(label: str, shape: tuple[Fraction, Fraction, Fraction]) -> tuple[Growth3, float] | None:
    """Leading term of x^α (log2 x)^β (log2 log2 x)^γ for x the slice polynomial."""
    poly = MENU[label]
    e = max(poly)
    a, b, g = shape
    if e == 0:  # a constant
        x = float(poly[F(0)])
        if x < 2:
            return None  # every variable is at least 2 (bounds §2)
        lx = math.log2(x)
        if (b and lx == 0) or (g and lx <= 1):
            return ZERO3, 0.0  # the factor is 0 (or undefined)
        val = x ** float(a) * (lx ** float(b) if b else 1.0) * (math.log2(lx) ** float(g) if g else 1.0)
        return ZERO3, val
    c = poly[e]
    # x ~ c t^e, log2 x ~ e log2 t, log2 log2 x ~ log2 log2 t
    return (e * a, b, g), float(c) ** float(a) * float(e) ** float(b)


def _merge_key(key, assign: dict[str, str]):  # noqa: ANN001, ANN202
    """The monomial along the slice, as (label, shape) pairs: variables set to the same
    polynomial are the same function, so their factors combine exactly."""
    shapes: dict[str, tuple[Fraction, Fraction, Fraction]] = {}
    for v, (a, b, d) in key:
        lab = assign.get(v)
        if lab is None:
            return None
        o = shapes.get(lab)
        shapes[lab] = (a, b, d) if o is None else (o[0] + a, o[1] + b, o[2] + d)
    return tuple(sorted((lab, sh) for lab, sh in shapes.items() if any(sh)))


@functools.lru_cache(maxsize=262144)
def _slice_monomial(skey) -> tuple[Growth3, float] | None:  # noqa: ANN001
    growth = ZERO3
    coef = 1.0
    for lab, shape in skey:
        got = _leading_var(lab, shape)
        if got is None:
            return None
        (a, b, gg), c = got
        growth = (growth[0] + a, growth[1] + b, growth[2] + gg)
        coef *= c
    return growth, coef


@functools.lru_cache(maxsize=262144)
def _slice_poly(skey) -> tuple | None:  # noqa: ANN001
    """The monomial along the slice as an exact polynomial in t, if it is one."""
    out: UPoly = {F(0): F(1)}
    for lab, (a, b, d) in skey:
        if b or d or a < 0 or a.denominator != 1:
            return None
        for _ in range(int(a)):
            out = _pmul(out, MENU[lab])
    return tuple(out.items())


def _pmul(p: UPoly, q: UPoly) -> UPoly:
    out: UPoly = {}
    for a, x in p.items():
        for b, y in q.items():
            out[a + b] = out.get(a + b, F(0)) + x * y
    return {k: w for k, w in out.items() if w}


# --- a growth along a slice ---------------------------------------------------------------


def _sum_exact(cs: list[Coef]) -> list[Coef]:
    """Add the exact coefficients (and their shifts) of merged monomials; keep the others."""
    v = sum(c.value for c in cs if c.kind == "exact")
    sh = sum(c.shift for c in cs if c.kind == "exact")
    out = [c for c in cs if c.kind != "exact"]
    if v or sh:
        out.append(Coef("exact", v, (sh > 0) - (sh < 0)))
    return out


Term = tuple  # (growth, kind, value); kinds: exact, approx, shift, big, small, family


def leading_terms(g: Growth, sl: Slice, values: dict, ranges: dict | None = None) -> list[Term] | None:
    """The terms of g along the slice. `values`: named constants; `ranges`: (lo, hi) of
    log2 of constant bases with named constants (expr#), taken at the end that makes g
    larger, so that a witness holds for every value in the range."""
    assign = dict(sl.assign)
    merged: dict[tuple, list[Coef]] = {}
    for key, cs in g.terms.items():
        skey = _merge_key(key, assign)
        if skey is None:
            return None
        merged.setdefault(skey, []).extend(cs)
    out: list[Term] = []
    exact_poly: UPoly = {}
    for skey, raw in merged.items():
        known: list[Fraction] = []  # exact coefficients (named constants resolved)
        rest: list[Coef] = []
        for c in _sum_exact(raw):
            if c.kind == "exact":
                if c.value:
                    known.append(F(c.value))
                if c.shift:
                    rest.append(Coef("exact", 0.0, c.shift))
            elif c.kind.startswith("sym:"):
                name = c.kind[4:]
                if name in values:
                    known.append(F(c.value) * F(values[name]))
                elif ranges and name in ranges:
                    lo, hi = ranges[name]
                    known.append(F(c.value) * F(hi if c.value > 0 else lo))
                else:
                    return None
            else:
                rest.append(c)
        poly = _slice_poly(skey)
        if poly is not None and known:
            total = sum(known, F(0))
            for e, w in poly:
                exact_poly[e] = exact_poly.get(e, F(0)) + total * w
            known = []
        got = _slice_monomial(skey)
        if got is None:
            return None
        growth, coef = got
        if coef == 0:
            continue
        for v in known:
            out.append((growth, "approx", float(v) * coef))
        for c in rest:
            if c.kind == "exact":
                out.append((growth, "shift", c.shift * coef))
            else:
                out.append((growth, c.kind, c.sign * (1 if coef > 0 else -1)))
    for e, w in exact_poly.items():
        if w:
            out.append(((e, F(0), F(0)), "exact", w))
    return out


def tends_to_minus_infinity(terms: list[Term], above: Growth3) -> bool:
    """Is the sum certainly -∞ along the slice, with a leading growth above `above`?
    B's unknowns (positive big/small/family) at the top win; A's big wins against numbers;
    an exactly cancelled level is passed only if no approximate term reaches it."""
    by_growth: dict[Growth3, list[tuple[str, object]]] = {}
    approx_top = None
    for growth, kind, val in terms:
        by_growth.setdefault(growth, []).append((kind, val))
        if kind in ("approx", "shift") and (approx_top is None or growth > approx_top):
            approx_top = growth
    for growth in sorted(by_growth, reverse=True):
        if growth <= above:
            return False
        if approx_top is not None and growth < approx_top:
            return False  # below an approximate term's leading growth: its corrections are unknown
        parts = by_growth[growth]
        # an O(·) constant of B is as large as needed, one of A as large as A likes (B chooses
        # after A); an o(·) or a family's δ is of lower order than a nonzero number here
        if any(k == "big" and v > 0 for k, v in parts):
            return False
        if any(k == "big" and v < 0 for k, v in parts):
            return True
        exact = sum((v for k, v in parts if k == "exact"), F(0))
        approx = [v for k, v in parts if k == "approx"]
        total = float(exact) + sum(approx)
        scale = max([abs(float(exact))] + [abs(v) for v in approx])
        if total < -TOL * max(1.0, scale):
            return True
        if total > TOL * max(1.0, scale):
            return False
        if any(k in ("small", "family") and v > 0 for k, v in parts):
            return False
        if approx:
            return False  # approximately 0: no evidence
        if any(k in ("small", "family", "shift") for k, _ in parts):
            return False  # A's o(·), an infinitesimal: no evidence
        # exactly 0 at this level: the next level decides
    return False


# --- slices of a problem's domain ------------------------------------------------------------


def _upoly(g: Growth, assign: dict[str, str]) -> UPoly | None:
    """g along the slice as an exact polynomial in t, if g is a polynomial in the variables."""
    out: UPoly = {}
    for key, cs in g.terms.items():
        if len(cs) != 1 or cs[0].kind != "exact" or cs[0].shift:
            return None
        poly: UPoly = {F(0): F(cs[0].value)}
        for v, (a, b, d) in key:
            if b or d or a < 0 or a.denominator != 1 or v not in assign:
                return None
            for _ in range(int(a)):
                poly = _pmul(poly, MENU[assign[v]])
        for k, w in poly.items():
            out[k] = out.get(k, F(0)) + w
    return {k: w for k, w in out.items() if w}


def _eventually_nonneg(p: UPoly) -> bool:
    return not p or p[max(p)] > 0


_SLICES: dict[tuple, tuple[Slice, ...]] = {}


def _slices_for(domain, symbols: tuple[str, ...]) -> tuple[Slice, ...]:  # noqa: ANN001
    """Bases: all variables t; or the variables never bounded by others (n, N, ...) larger
    (2t, t^2). From each valid base, one or two variables changed."""
    from .decide import growth_key

    key = (tuple((growth_key(a), growth_key(b)) for a, b in domain), symbols)
    if key in _SLICES:
        return _SLICES[key]
    small_side = {v for a, _ in domain for k in a.terms for v, _ in k}
    bound_vars = sorted({v for a, b in domain for gg in (a, b) for k in gg.terms for v, _ in k} & set(symbols))
    sinks = [v for v in symbols if v not in small_side]
    labels = list(MENU)
    bases = [{v: "t" for v in symbols}]
    for big in ("2t", "t^2"):
        bases.append({v: (big if v in sinks else "t") for v in symbols})
    out: list[Slice] = []
    seen = set()

    def valid(c: dict[str, str]) -> bool:
        for small, large in domain:
            p = _upoly(large - small, c)
            if p is None or not _eventually_nonneg(p):
                return False
        return True

    for base in bases:
        cands = [base]
        for v in symbols:
            for lab in labels:
                cands.append({**base, v: lab})
        for v, w in itertools.combinations(bound_vars, 2):
            for a, b in itertools.product(labels, repeat=2):
                cands.append({**base, v: a, w: b})
        for c in cands:
            skey = tuple(sorted(c.items()))
            if skey in seen or all(max(MENU[x]) == 0 for x in c.values()):
                continue
            seen.add(skey)
            if valid(c):
                out.append(Slice(skey))
    _SLICES[key] = tuple(out)
    return _SLICES[key]


def slices(ctx, symbols) -> tuple[Slice, ...]:  # noqa: ANN001
    """Slices along which every constraint holds for all large t (exact check)."""
    if not ctx.exact_domain:
        return ()
    return _slices_for(ctx.domain, tuple(sorted(symbols)))


def unbounded_below(g: Growth, ctx, values: dict, above: Growth3 = ZERO3) -> Slice | None:  # noqa: ANN001
    """A slice along which g -> -∞ (faster than `above`), if one is found."""
    names = {v for key in g.terms for v, _ in key}
    if not names:
        return None
    for sl in slices(ctx, set(ctx.symbols) | names):
        terms = leading_terms(g, sl, values)
        if terms is not None and tends_to_minus_infinity(terms, above):
            return sl
    return None
