"""Deciding whether a growth is bounded below on a problem's domain (docs/specs/bounds.md §5).

A comparison A ⪯ B comes down to one question (bounds §5, "Definition"): is

    g = log2(B) - log2(A) = Σ_K c_K · K(x)

bounded below on the domain D of the problem, where each K is a monomial
Π x^α (log x)^β (log log x)^γ and each c_K is an exact number (plus an infinitesimal) or one
of the unknowns of the statements (an O(·) constant, an o(·) function, the δ of a family)?

The answer is a certificate, found in tiers, each tried only if the one before fails:

1. **Linear programming.** Every monomial with a negative part (a "demand") is covered by
   monomials with positive parts ("supplies") along dominance edges between monomials:
   K ≤ κ K' + C on D (weak, at rate κ) or K = o(K') on D (strict: any positive amount of K'
   covers any amount of K). Expressions known to be nonnegative on D (constraint gaps such
   as n(n-1)/2 - m, parameter-map expressions) may be subtracted with multipliers λ ≥ 0.
   Whether the leftovers can all be nonnegative is a linear program, solved exactly
   (`lp.py`); its solution is the certificate, checked again by `verify`.
   Edges come from the problem's constraints: in log coordinates u = log x the monomial
   constraints x ≤ c y^p are linear, so whether one power monomial is at most a constant
   times another, or of lower order, is itself a linear program.
2. **Z3** (MIT licence; optional). If the linear program fails and g is a polynomial in the
   variables (no logarithms, no unknowns), Z3's nonlinear real arithmetic is asked whether
   g < -C can hold on D for a large C, with the constraints and nonnegative expressions as
   hypotheses. "unsat" proves the bound.
3. Otherwise there is no proof. The comparator then looks for a witness that g is not
   bounded below (`disprove.py`); without one, the comparison is **undecided**.

Everything here is sound: a proof is only claimed with a certificate that holds for every
value of the unknowns the statements allow, and for every value of ω in its range (g is
linear in ω, so both ends suffice).
"""

from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass, field
from fractions import Fraction

from .growth import EPS, Growth, Key
from .lp import solve

ETA = Fraction(1, 10**9)  # stands for the infinitesimal of c - ε: residual + s·η >= 0 as well
TAU = Fraction(1, 10**9)  # a positive leftover: any positive amount covers an o(·) or a family
BIG_M = Fraction(10**6)  # strict edges: covered amount <= BIG_M · leftover of the source
Z3_BOUND = 10**9  # Z3 proves g >= -Z3_BOUND on D
Z3_RLIMIT = 200_000  # a resource limit, not a time limit, so results do not depend on the machine


# --- edges between monomials ---------------------------------------------------------------


@dataclass(frozen=True)
class Edge:
    kind: str  # weak | strict
    kappa: Fraction = Fraction(1)  # weak: K_to <= kappa K_from on D (up to a constant)
    why: str = ""


def _log_domain(ctx) -> tuple[list[str], list[tuple[dict[str, Fraction], Fraction]]]:  # noqa: ANN001
    """The domain in log coordinates u_x = log2 x >= 1: u_x - p u_y <= log2 c for every
    constraint x <= c y^p (bounds B5), a superset of D's image."""
    names = sorted({v for pair in ctx.le for v in pair})
    rows = []
    for (x, y), p in ctx.le.items():
        c = ctx.scale(x, y)
        off = _log2_up(c)
        rows.append(({x: Fraction(1), y: -p}, off))
    return names, rows


def _log2_up(c: Fraction) -> Fraction:
    """A rational upper bound on log2 c (c > 0)."""
    if c == 1:
        return Fraction(0)
    num, den = c.numerator, c.denominator
    if num & (num - 1) == 0 and den & (den - 1) == 0:  # a power of two
        return Fraction(num.bit_length() - den.bit_length())
    return Fraction(math.log2(c)).limit_denominator(10**6) + Fraction(1, 10**6)


def _log2_down(c: Fraction) -> Fraction:
    """A rational lower bound on log2 c (c >= 2)."""
    num, den = c.numerator, c.denominator
    if num & (num - 1) == 0 and den & (den - 1) == 0:
        return Fraction(num.bit_length() - den.bit_length())
    return Fraction(math.log2(c)).limit_denominator(10**6) - Fraction(1, 10**6)


def _powers(key: Key) -> dict[str, Fraction] | None:
    """The exponents of a power monomial; None if it has logarithmic factors."""
    out = {}
    for v, (a, b, d) in key:
        if b or d:
            return None
        out[v] = a
    return out


def _logs_at_least_one(key: Key) -> bool:
    return all(b >= 0 and d >= 0 for _, (_, b, d) in key)


def _split(key: Key) -> tuple[dict[str, Fraction], Key]:
    """The power part and the log part of a monomial."""
    powers = {v: a for v, (a, _, _) in key if a}
    logs = tuple((v, (Fraction(0), b, d)) for v, (_, b, d) in key if b or d)
    return powers, logs


def _lp_max(obj: dict[str, Fraction], names: list[str], rows, extra_eq=None):  # noqa: ANN001
    """max obj·u' over u' >= 0 subject to rows (coeffs·u' <= off); extra_eq: equalities."""
    idx = {v: i for i, v in enumerate(names)}
    n = len(names)
    c = [obj.get(v, Fraction(0)) for v in names]
    a_ub = []
    b_ub = []
    for coeffs, off in rows:
        row = [Fraction(0)] * n
        for v, w in coeffs.items():
            row[idx[v]] += w
        a_ub.append(row)
        b_ub.append(off)
    a_eq, b_eq = [], []
    for coeffs, rhs in extra_eq or ():
        row = [Fraction(0)] * n
        for v, w in coeffs.items():
            row[idx[v]] += w
        a_eq.append(row)
        b_eq.append(rhs)
    return solve(c, a_ub, b_ub, a_eq, b_eq)


def _power_edge(frm: dict[str, Fraction], to: dict[str, Fraction], ctx) -> Edge | None:  # noqa: ANN001
    """Edge between power monomials Π x^a from the log-domain linear programs."""
    if any(a < 0 for a in frm.values()) or any(a < 0 for a in to.values()):
        return None
    names, rows = _log_domain(ctx)
    names = sorted(set(names) | set(frm) | set(to))
    diff = {v: to.get(v, Fraction(0)) - frm.get(v, Fraction(0)) for v in names}
    # every variable is at least 2 (bounds §2, definition item 1), or more by a constraint
    # such as k >= 3: u = L + u' with u' >= 0 and L <= log2 of the lower bound
    low = {v: _log2_down(ctx.at_least(v)) for v in names}
    shifted = [(coeffs, off - sum(w * low[v] for v, w in coeffs.items())) for coeffs, off in rows]
    weak = _lp_max(diff, names, shifted)
    if weak.status != "optimal":
        return None
    kappa = _pow2_up(weak.value + sum(w * low[v] for v, w in diff.items()))
    # strict: on the recession cone (offsets 0), to·d <= rho · frm·d with rho < 1, and to·d <= 0
    # where frm·d = 0
    cone = [(coeffs, Fraction(0)) for coeffs, _ in rows]
    if frm:
        r = _lp_max(to, names, cone, [(frm, Fraction(1))])
        flat = _lp_max(to, names, cone + [({v: Fraction(1) for v in names}, Fraction(1))], [(frm, Fraction(0))])
        rho_ok = r.status == "infeasible" or (r.status == "optimal" and r.value < 1)
        if rho_ok and flat.status == "optimal" and flat.value <= 0 and r.status == "optimal":
            return Edge("strict", why="power LP")
    return Edge("weak", kappa, "power LP")


def _pow2_up(v: Fraction) -> Fraction:
    """A rational upper bound on 2^v."""
    if v.denominator == 1:
        return Fraction(2) ** int(v)
    return Fraction(2 ** float(v)).limit_denominator(10**6) * Fraction(1000001, 1000000)


@functools.lru_cache(maxsize=200000)
def _edge_cached(frm: Key, to: Key, ctx_key) -> Edge | None:  # noqa: ANN001
    ctx = _CTX[ctx_key]
    return _edge(frm, to, ctx)


_CTX: dict[int, object] = {}


def edge(frm: Key, to: Key, ctx) -> Edge | None:  # noqa: ANN001
    """K_to <= κ K_from + C on D (weak) or K_to = o(K_from) on D (strict); None if neither
    can be shown."""
    k = id(ctx)
    _CTX[k] = ctx
    return _edge_cached(frm, to, k)


def _edge(frm: Key, to: Key, ctx) -> Edge | None:  # noqa: ANN001
    from .compare import _dominates  # the per-variable shape rules (bounds §5 items 2, 3, 9)

    if frm == to:
        return Edge("weak", Fraction(1), "same")
    if not to:
        return None
    best: Edge | None = None
    dom = _dominates(frm, to, ctx)
    if dom == "strict":
        return Edge("strict", why="shapes")
    if dom == "weak":
        best = Edge("weak", Fraction(1), "shapes")
    # power parts by linear programming; log factors of `frm` (all >= 0) only help, and log
    # factors of `to` are of lower order than any strict power gap in variables of `frm`
    pf, lf = _split(frm)
    pt, lt = _split(to)
    # a factor (log x)^b of `frm` with b >= 0 is at least 1 (x >= 2), so it only helps; a
    # log log factor may be 0 (x = 2, 3) and is not used; `to` may have log factors in
    # variables of a strict power gap
    if pf and all(b >= 0 and d == 0 for _, (_, b, d) in lf):
        if not lt:
            e = _power_edge(pf, pt, ctx)
            if e is not None and e.kind == "weak" and lf:
                # (log x)^b >= (log2 of x's lower bound)^b: k >= 3 gives log k >= 1.58
                floor = Fraction(1)
                for v, (_, b, _) in lf:
                    floor *= _log2_down(ctx.at_least(v)) ** int(b) if b.denominator == 1 else Fraction(1)
                e = Edge("weak", e.kappa / floor, e.why + ", log factors")
            if e is not None and (best is None or e.kind == "strict" or e.kappa < best.kappa):
                best = e
        elif all(v in pf for v, _ in lt) and _logs_at_least_one(to):
            # (log x)^b <= C_ε x^ε: absorbed by a strict gap that grows with every such x
            e = _power_edge(pf, pt, ctx)
            if e is not None and e.kind == "strict" and _strict_in_each(pf, pt, [v for v, _ in lt], ctx):
                best = e
    return best


def _strict_in_each(pf, pt, log_vars, ctx) -> bool:  # noqa: ANN001
    """For each x with a log factor in `to`, pf / pt still grows like a power of x:
    pt · x^{1/1000} has a strict edge to pf."""
    for x in log_vars:
        bumped = dict(pt)
        bumped[x] = bumped.get(x, Fraction(0)) + Fraction(1, 1000)
        e = _power_edge(pf, bumped, ctx)
        if e is None or e.kind != "strict":
            return False
    return True


# --- the certificate -----------------------------------------------------------------------


@dataclass
class Certificate:
    """Why g is bounded below on D, for one value of the named constants."""

    method: str  # trivial | lp | z3
    scenario: dict[str, float] = field(default_factory=dict)  # values of named constants
    lam: dict[int, Fraction] = field(default_factory=dict)  # multiplier of ctx.nonneg[i]
    weak: dict[tuple[Key, Key], Fraction] = field(default_factory=dict)  # amount moved from -> to
    strict: dict[tuple[Key, Key], Fraction] = field(default_factory=dict)  # amount covered at `to`
    free: dict[Key, str] = field(default_factory=dict)  # keys covered by an unknown of B
    positive: tuple[Key, ...] = ()  # keys whose leftover must be positive (o(·), families)
    edges: dict[tuple[Key, Key], Edge] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Decision:
    proved: bool
    certificates: tuple[Certificate, ...] = ()


@dataclass
class _Slot:
    v: Fraction = Fraction(0)  # exact part
    s: int = 0  # infinitesimal part, sign
    b_big: bool = False  # an O(·) constant of B: as large as needed
    b_small: bool = False  # an o(·) function of B: chosen
    b_family: bool = False  # a δ of B: every δ > 0
    a_big: bool = False  # an O(·) constant of A: arbitrary
    a_small: bool = False  # an o(·) function of A: arbitrary
    a_family: bool = False  # a δ of A: chosen small


def _slots(g: Growth, values: dict[str, Fraction]) -> dict[Key, _Slot] | None:
    out: dict[Key, _Slot] = {}
    for key, cs in g.terms.items():
        if not key:
            continue  # a constant: bounded
        s = out.setdefault(key, _Slot())
        for c in cs:
            if c.kind == "exact":
                s.v += Fraction(c.value)
                s.s += c.shift
            elif c.kind.startswith("sym:"):
                name = c.kind[4:]
                if name not in values:
                    return None
                s.v += Fraction(c.value) * values[name]
            elif c.kind == "big":
                if c.sign > 0:
                    s.b_big = True
                else:
                    s.a_big = True
            elif c.kind == "small":
                if c.sign > 0:
                    s.b_small = True
                else:
                    s.a_small = True
            elif c.kind == "family":
                if c.sign > 0:
                    s.b_family = True
                else:
                    s.a_family = True
            else:
                return None
        s.s = (s.s > 0) - (s.s < 0)
        if abs(s.v) < Fraction(EPS):
            s.v = Fraction(0)
    return out


def _scenarios(g: Growth, ctx) -> list[dict[str, Fraction]] | None:  # noqa: ANN001
    """Values for the named constants: both ends of each range (g is linear in each plain
    named constant); a constant base with named constants (expr#) takes its safe value."""
    from .compare import CONST_EXPRS, interval  # noqa: F401

    plain: set[str] = set()
    exprs: dict[str, tuple[Fraction, Fraction]] = {}
    for cs in g.terms.values():
        for c in cs:
            if not c.kind.startswith("sym:"):
                continue
            name = c.kind[4:]
            if name.startswith("expr#"):
                node = CONST_EXPRS.get(name)
                r = interval(node, ctx.constants) if node is not None else None
                if r is None or r[0] <= 0:
                    return None
                exprs[name] = (Fraction(math.log2(r[0])) - Fraction(1, 10**9), Fraction(math.log2(r[1])) + Fraction(1, 10**9))
            elif name in ctx.constants:
                plain.add(name)
            else:
                return None
    names = sorted(plain)
    out = []
    for ends in itertools.product((0, 1), repeat=len(names)):
        vals = {n: Fraction(ctx.constants[n][e]) for n, e in zip(names, ends)}
        out.append(vals)
    if exprs:
        # the coefficient of an expr# monomial decides which end of its interval is safe:
        # positive (B's side) -> lower end, negative (A's side) -> upper end
        signs: dict[str, int] = {}
        for cs in g.terms.values():
            for c in cs:
                if c.kind.startswith("sym:expr#"):
                    name = c.kind[4:]
                    sg = 1 if c.value > 0 else -1
                    if signs.get(name, sg) != sg:
                        return None  # on both sides: no single safe value
                    signs[name] = sg
        for vals in out:
            for name, (lo, hi) in exprs.items():
                vals[name] = lo if signs[name] > 0 else hi
    return out or [{}]


def growth_key(g: Growth) -> tuple:
    return tuple(sorted((k, tuple(sorted((c.kind, c.value, c.shift) for c in cs))) for k, cs in g.terms.items()))


_CACHE: dict[tuple, Decision] = {}
_KEEP: dict[int, object] = {}


def bounded_below(g: Growth, ctx) -> Decision:  # noqa: ANN001
    key = (growth_key(g), id(ctx))
    _KEEP[id(ctx)] = ctx  # keeps the id from being reused while the cache holds it
    got = _CACHE.get(key)
    if got is None:
        got = _CACHE[key] = _bounded_below(g, ctx)
    return got


def _bounded_below(g: Growth, ctx) -> Decision:  # noqa: ANN001
    scen = _scenarios(g, ctx)
    if scen is None:
        return Decision(False)
    certs = []
    for values in scen:
        slots = _slots(g, values)
        if slots is None:
            return Decision(False)
        cert = _prove(slots, g, ctx, values)
        if cert is None:
            return Decision(False)
        certs.append(cert)
    return Decision(True, tuple(certs))


def _prove(slots: dict[Key, _Slot], g: Growth, ctx, values) -> Certificate | None:  # noqa: ANN001
    demands = [k for k, s in slots.items() if s.v < 0 or (s.v == 0 and s.s < 0) or s.a_big or s.a_small or s.a_family]
    if not demands:
        return Certificate("trivial", dict(values))
    cert = _prove_lp(dict(slots), ctx, values)
    if cert is not None and verify(cert, slots, ctx):
        return cert
    if not _z3_applicable(slots):
        return None
    from .disprove import unbounded_below

    if unbounded_below(g, ctx, {k: float(v) for k, v in values.items()}) is not None:
        return None  # g -> -∞ along a slice of the domain: no proof exists
    cert = _prove_z3(slots, ctx, values)
    if cert is not None:
        return cert
    return None


def _free(slots: dict[Key, _Slot], ctx, edges) -> dict[Key, set[str]]:  # noqa: ANN001
    """For each key, the demand kinds covered by unknowns of B (no linear program needed)."""
    from .compare import N_LOG, _hidden

    out: dict[Key, set[str]] = {k: set() for k in slots}
    for to in slots:
        for frm, s in slots.items():
            e = Edge("weak", Fraction(1), "same") if frm == to else edges.get((frm, to))
            hidden = frm == N_LOG and s.b_big and _hidden(to, ctx, "ostar")
            if e is None and not hidden:
                continue
            if s.b_big or hidden:
                out[to] |= {"exact", "a_big", "a_small", "a_family"}
            if e is not None and e.kind == "strict" and (s.b_small or s.b_family):
                out[to] |= {"exact", "a_big", "a_small", "a_family"}
            if s.b_small:
                out[to] |= {"a_small"}
            if s.b_family:
                out[to] |= {"a_small", "a_family"}
    return out


MAX_CHOICES = 64


def _prove_lp(slots: dict[Key, _Slot], ctx, values) -> Certificate | None:  # noqa: ANN001
    keys = list(slots)
    # nonnegative expressions may bring monomials of their own
    nonneg = [e for e in ctx.nonneg if _exact_growth(e) is not None]
    for e in nonneg:
        for k in e.terms:
            if k and k not in slots:
                slots[k] = _Slot()
                keys.append(k)
    edges: dict[tuple[Key, Key], Edge] = {}
    for frm in keys:
        for to in keys:
            if frm != to:
                e = edge(frm, to, ctx)
                if e is not None:
                    edges[(frm, to)] = e
    free = _free(slots, ctx, edges)
    if not _reachable(slots, keys, nonneg, edges, free):
        return None
    # unbounded demands (A's unknowns) not covered by B's unknowns: some source must keep a
    # positive leftover
    options: list[list[Key]] = []
    for k, s in slots.items():
        for kind in ("a_big", "a_small", "a_family"):
            if getattr(s, kind) and kind not in free[k]:
                srcs = []
                for frm in keys:
                    if frm == k:
                        if kind != "a_big":
                            srcs.append(frm)
                        continue
                    e = edges.get((frm, k))
                    if e is None:
                        continue
                    if kind == "a_big" and e.kind != "strict":
                        continue
                    srcs.append(frm)
                if not srcs:
                    return None
                options.append(srcs)
    for choice in itertools.islice(itertools.product(*options), MAX_CHOICES):
        cert = _lp(slots, keys, nonneg, edges, free, tuple(sorted(set(choice))), values)
        if cert is not None:
            return cert
    return None


def _reachable(slots, keys, nonneg, edges, free) -> bool:  # noqa: ANN001
    """A quick necessary condition: every exact demand can be reached along edges from a
    monomial with a positive part (or one a nonnegative expression can make positive)."""
    sources = {k for k in keys if slots[k].v > 0 or slots[k].b_big or slots[k].b_small or slots[k].b_family}
    for e in nonneg:
        for k, cs in e.terms.items():
            if k and any(c.sign < 0 for c in cs):
                sources.add(k)
    reach = set(sources)
    frontier = list(sources)
    while frontier:
        f = frontier.pop()
        for t in keys:
            if t not in reach and (f, t) in edges:
                reach.add(t)
                frontier.append(t)
    for k in keys:
        s = slots[k]
        if (s.v < 0 or (s.v == 0 and s.s < 0)) and "exact" not in free[k] and k not in reach:
            return False
    return True


def _exact_growth(e: Growth) -> dict[Key, Fraction] | None:
    out = {}
    for k, cs in e.terms.items():
        if len(cs) != 1 or cs[0].kind != "exact":
            return None
        out[k] = Fraction(cs[0].value)
    return out


def _lp(slots, keys, nonneg, edges, free, positive, values) -> Certificate | None:  # noqa: ANN001
    # variables: λ_e, weak transfers, strict covers
    var_names: list[tuple] = []
    for i, _ in enumerate(nonneg):
        var_names.append(("lam", i))
    weak_edges = [(f, t) for (f, t), e in edges.items() if e.kind == "weak"]
    strict_edges = [(f, t) for (f, t), e in edges.items() if e.kind == "strict"]
    for fe in weak_edges:
        var_names.append(("w", fe))
    for fe in strict_edges:
        var_names.append(("y", fe))
    idx = {v: i for i, v in enumerate(var_names)}
    n = len(var_names)
    exact_nonneg = [_exact_growth(e) for e in nonneg]

    def residual(k: Key) -> tuple[list[Fraction], Fraction]:
        """residual(k) = const + row·vars."""
        row = [Fraction(0)] * n
        const = slots[k].v
        for i, eg in enumerate(exact_nonneg):
            if k in eg:
                row[idx[("lam", i)]] -= eg[k]
        for f, t in weak_edges:
            if f == k:
                row[idx[("w", (f, t))]] -= 1
            if t == k:
                row[idx[("w", (f, t))]] += 1 / edges[(f, t)].kappa
        for f, t in strict_edges:
            if t == k:
                row[idx[("y", (f, t))]] += 1
        return row, const

    a_ub: list[list[Fraction]] = []
    b_ub: list[Fraction] = []
    for k in keys:
        row, const = residual(k)
        if "exact" in free[k]:
            continue  # B's unknowns cover any amount here
        # residual >= 0  <=>  -row·x <= const
        a_ub.append([-v for v in row])
        b_ub.append(const)
        if slots[k].s < 0:
            a_ub.append([-v for v in row])
            b_ub.append(const - ETA)
    for k in positive:
        row, const = residual(k)
        a_ub.append([-v for v in row])
        b_ub.append(const - TAU)
    for f, t in strict_edges:
        if "exact" in free[t]:
            continue
        row, const = residual(f)
        # y <= BIG_M · residual(f)
        line = [-BIG_M * v for v in row]
        line[idx[("y", (f, t))]] += 1
        a_ub.append(line)
        b_ub.append(BIG_M * const)
    res = solve([Fraction(0)] * n, a_ub, b_ub)
    if res.status != "optimal":
        return None
    x = res.x
    cert = Certificate(
        "lp",
        {k: float(v) for k, v in values.items()},
        lam={i: x[idx[("lam", i)]] for i in range(len(nonneg)) if x[idx[("lam", i)]]},
        weak={fe: x[idx[("w", fe)]] for fe in weak_edges if x[idx[("w", fe)]]},
        strict={fe: x[idx[("y", fe)]] for fe in strict_edges if x[idx[("y", fe)]]},
        free={k: ",".join(sorted(v)) for k, v in free.items() if v},
        positive=positive,
        edges=dict(edges),
    )
    cert.note = f"{len(keys)} monomials, {len(nonneg)} nonnegative expressions"
    cert._nonneg = exact_nonneg  # type: ignore[attr-defined]
    return cert


def verify(cert: Certificate, slots: dict[Key, _Slot], ctx) -> bool:  # noqa: ANN001
    """Check an LP certificate again with exact arithmetic, independently of the solver."""
    if cert.method != "lp":
        return True
    nonneg = getattr(cert, "_nonneg", [])
    res: dict[Key, Fraction] = {k: s.v for k, s in slots.items()}
    for i, lam in cert.lam.items():
        if lam < 0:
            return False
        for k, c in nonneg[i].items():
            if k:
                res[k] = res.get(k, Fraction(0)) - lam * c
    for (f, t), w in cert.weak.items():
        e = cert.edges.get((f, t))
        if w < 0 or e is None or e.kind != "weak":
            return False
        res[f] = res.get(f, Fraction(0)) - w
        res[t] = res.get(t, Fraction(0)) + w / e.kappa
    for (f, t), y in cert.strict.items():
        e = cert.edges.get((f, t))
        if y < 0 or e is None or e.kind != "strict":
            return False
        res[t] = res.get(t, Fraction(0)) + y
    free = {k: set(v.split(",")) for k, v in cert.free.items()}
    for k, r in res.items():
        if "exact" in free.get(k, set()):
            continue
        if r < 0:
            return False
        if r == 0 and k in slots and slots[k].s < 0:
            return False
    for (f, t), y in cert.strict.items():
        if "exact" not in free.get(t, set()) and res.get(f, Fraction(0)) <= 0:
            return False
    for k in cert.positive:
        if res.get(k, Fraction(0)) <= 0:
            return False
    # every unbounded demand covered: by B's unknowns, or by a positive leftover with an edge
    for k, s in slots.items():
        for kind in ("a_big", "a_small", "a_family"):
            if not getattr(s, kind) or kind in free.get(k, set()):
                continue
            ok = False
            for frm in cert.positive:
                if frm == k and kind != "a_big":
                    ok = True
                e = cert.edges.get((frm, k))
                if e is not None and (e.kind == "strict" or kind != "a_big"):
                    ok = True
            if not ok:
                return False
    return True


# --- tier 2: Z3 ----------------------------------------------------------------------------


def _z3_applicable(slots: dict[Key, _Slot]) -> bool:
    """g is a polynomial in the variables with exact coefficients."""
    if any(s.b_big or s.b_small or s.b_family or s.a_big or s.a_small or s.a_family or s.s for s in slots.values()):
        return False
    return all(not (b or d or a < 0 or a.denominator != 1) for key in slots for _, (a, b, d) in key)


def _prove_z3(slots: dict[Key, _Slot], ctx, values) -> Certificate | None:  # noqa: ANN001
    try:
        import z3
    except ImportError:
        return None
    if not _z3_applicable(slots):
        return None
    nonneg = []
    for e in ctx.nonneg:
        eg = _exact_growth(e)
        if eg is None:
            continue
        if any(b or d or a < 0 or a.denominator != 1 for k in eg for _, (a, b, d) in k):
            continue
        nonneg.append(eg)
    names = sorted({v for k in slots for v, _ in k} | {v for eg in nonneg for k in eg for v, _ in k})
    xs = {v: z3.Real(v) for v in names}

    def mono(key: Key):  # noqa: ANN202
        out = z3.RealVal(1)
        for v, (a, _, _) in key:
            for _ in range(int(a)):
                out = out * xs[v]
        return out

    def poly(coeffs: dict[Key, Fraction]):  # noqa: ANN202
        total = z3.RealVal(0)
        for k, c in coeffs.items():
            total = total + z3.RealVal(str(c)) * mono(k)
        return total

    s = z3.Solver()
    s.set("rlimit", Z3_RLIMIT)
    for v in names:
        s.add(xs[v] >= z3.RealVal(str(ctx.at_least(v))))  # bounds §2, definition item 1
    for (x, y), p in ctx.le.items():
        if p.denominator == 1 and x in xs and y in xs:
            s.add(xs[x] <= z3.RealVal(str(ctx.scale(x, y))) * mono(((y, (p, Fraction(0), Fraction(0))),)))
    for eg in nonneg:
        s.add(poly(eg) >= 0)
    s.add(poly({k: sl.v for k, sl in slots.items()}) < -Z3_BOUND)
    if s.check() == z3.unsat:
        return Certificate("z3", {k: float(v) for k, v in values.items()},
                           note=f"z3: g >= -{Z3_BOUND} on the constraints and nonnegative expressions")
    return None
