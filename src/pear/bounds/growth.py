"""Internal normal form of bounds (docs/specs/bounds.md §3). Never displayed.

A term t is represented by its growth exponent G = log2 t, a sum of monomials

    coef · Π_x x^α (log x)^β (log log x)^γ

The coefficient is exact (a real number, possibly minus or plus an infinitesimal,
as in log2(2 - ε) = 1 - ε'), or one of three unknowns:
  big     the unknown positive constant of an inner O(·)
  small   the unknown positive infinitesimal of an inner o(·) (one algorithm)
  family  the δ of "for every δ > 0" (a family of algorithms)

Each term gets two growth exponents: `hi` (an upper bound on log2 t, used when the
term is the one that must be small) and `lo` (a lower bound, used when it must be
large). They differ only where the language forces an estimate, e.g. log(n + m).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

from .expr import (
    Add,
    Asym,
    Bound,
    Const,
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
    variables,
)

EPS = 1e-12


class UnsupportedBound(ValueError):
    """The expression is valid but outside what the comparator can reason about."""


Shape = tuple[Fraction, Fraction, Fraction]  # (α, β, γ)
Key = tuple[tuple[str, Shape], ...]  # sorted by variable; () is the constant monomial


@dataclass(frozen=True)
class Coef:
    kind: str  # exact | big | small | family
    value: float  # exact: the real value; otherwise the sign, +1 or -1
    shift: int = 0  # exact only: sign of an infinitesimal added to value

    @property
    def sign(self) -> int:
        if self.kind != "exact":
            return 1 if self.value > 0 else -1
        if abs(self.value) > EPS:
            return 1 if self.value > 0 else -1
        return self.shift

    @property
    def infinitesimal(self) -> bool:
        return self.kind in ("small", "family") or (self.kind == "exact" and abs(self.value) <= EPS)

    def neg(self) -> Coef:
        return Coef(self.kind, -self.value, -self.shift)


def exact(v: float | Fraction, shift: int = 0) -> Coef:
    return Coef("exact", float(v), shift)


def _sgn(x: float) -> int:
    return 0 if abs(x) <= EPS else (1 if x > 0 else -1)


def coef_mul(a: Coef, b: Coef) -> Coef:
    if a.kind == "exact" and b.kind == "exact":
        shift = _sgn(a.value * b.shift + b.value * a.shift)
        if shift == 0 and a.shift and b.shift:
            shift = a.shift * b.shift
        return Coef("exact", a.value * b.value, shift)
    if a.kind != "exact":
        a, b = b, a
    if a.kind == "exact":  # exact · unknown
        if a.sign == 0:
            return exact(0)
        kind = b.kind
        if b.kind == "big" and a.infinitesimal:
            kind = "small"  # ε · O(1)
        return Coef(kind, a.sign * b.sign)
    if a.kind == b.kind and a.kind in ("big", "small"):
        return Coef(a.kind, a.sign * b.sign)
    raise UnsupportedBound(f"cannot multiply {a.kind} and {b.kind} constants")


@dataclass
class Growth:
    """A sum of monomials, each with one or more coefficients of different kinds."""

    terms: dict[Key, list[Coef]] = field(default_factory=dict)

    def copy(self) -> Growth:
        return Growth({k: list(v) for k, v in self.terms.items()})

    def add_term(self, key: Key, c: Coef) -> None:
        bucket = self.terms.setdefault(key, [])
        if c.kind == "exact":
            for i, old in enumerate(bucket):
                if old.kind == "exact":
                    v = old.value + c.value
                    s = _sgn(old.shift + c.shift) if (old.shift or c.shift) else 0
                    bucket[i] = Coef("exact", v, s)
                    break
            else:
                bucket.append(c)
        else:
            bucket.append(c)
        bucket[:] = [b for b in bucket if not (b.kind == "exact" and abs(b.value) <= EPS and b.shift == 0)]
        if not bucket:
            del self.terms[key]

    def __add__(self, other: Growth) -> Growth:
        out = self.copy()
        for k, cs in other.terms.items():
            for c in cs:
                out.add_term(k, c)
        return out

    def __neg__(self) -> Growth:
        return Growth({k: [c.neg() for c in cs] for k, cs in self.terms.items()})

    def __sub__(self, other: Growth) -> Growth:
        return self + (-other)

    def scale(self, c: Coef) -> Growth:
        out = Growth()
        for k, cs in self.terms.items():
            for old in cs:
                out.add_term(k, coef_mul(old, c))
        return out

    def __mul__(self, other: Growth) -> Growth:
        out = Growth()
        for k1, cs1 in self.terms.items():
            for k2, cs2 in other.terms.items():
                key = key_mul(k1, k2)
                for a in cs1:
                    for b in cs2:
                        out.add_term(key, coef_mul(a, b))
        return out

    def variables(self) -> set[str]:
        return {v for key in self.terms for v, _ in key}

    def all_nonnegative(self) -> bool:
        return all(c.sign >= 0 for k, cs in self.terms.items() if k for c in cs)

    def single(self) -> tuple[Key, Coef] | None:
        if len(self.terms) == 1:
            (k, cs), = self.terms.items()
            if len(cs) == 1:
                return k, cs[0]
        return None


def key_mul(a: Key, b: Key) -> Key:
    shapes: dict[str, Shape] = dict(a)
    for v, s in b:
        if v in shapes:
            t = shapes[v]
            shapes[v] = (t[0] + s[0], t[1] + s[1], t[2] + s[2])
        else:
            shapes[v] = s
    return tuple(sorted((v, s) for v, s in shapes.items() if any(s)))


def const(c: Coef) -> Growth:
    g = Growth()
    g.add_term((), c)
    return g


def mono(var: str, shape: Shape, c: Coef | None = None) -> Growth:
    g = Growth()
    g.add_term(((var, shape),), c or exact(1))
    return g


ONE = Fraction(1)
ZERO = Fraction(0)


# --- exponents: the value of an expression as a Growth -----------------------


def value_growth(node: Node) -> Growth:
    """Write the *value* of an exponent expression as a sum of monomials."""
    if isinstance(node, Num):
        return const(exact(node.value))
    if isinstance(node, Var):
        return mono(node.name, (ONE, ZERO, ZERO))
    if isinstance(node, Const):
        if node.name == "varepsilon":
            return const(exact(0, +1))  # bounds §2: a positive infinitesimal
        if node.name == "delta":
            return const(Coef("family", 1))
        raise UnsupportedBound(f"\\{node.name} needs a value in data/constants, which does not exist yet")
    if isinstance(node, Add):
        out = Growth()
        for sign, t in node.terms:
            g = value_growth(t)
            out = out + (g if sign > 0 else -g)
        return out
    if isinstance(node, Mul):
        out = const(exact(1))
        for f in node.factors:
            out = out * value_growth(f)
        return out
    if isinstance(node, Div):
        return value_growth(node.num) * _invert(value_growth(node.den))
    if isinstance(node, Sqrt):
        return _power(value_growth(node.arg), Fraction(1, 2))
    if isinstance(node, Pow):
        e = value_growth(node.exp)
        s = e.single()
        if s is None or s[0] != () or s[1].kind != "exact" or s[1].shift:
            raise UnsupportedBound("only constant powers are supported inside exponents")
        return _power(value_growth(node.base), Fraction(s[1].value).limit_denominator(10**6))
    if isinstance(node, Log):  # the value log_b(arg)^p
        g = log_growth(node.arg, True).scale(exact(_log_base_scale(node)))
        return _power(g, _log_power(node))
    if isinstance(node, Asym):
        inner = value_growth(node.arg)
        if not inner.all_nonnegative():
            raise UnsupportedBound(f"{node.kind}(·) of an expression with negative parts")
        kind = "big" if node.kind == "O" else "small"
        out = Growth()
        for k, cs in inner.terms.items():
            if node.kind == "o" and k == ():
                continue  # o(1) inside an exponent is a constant factor
            out.add_term(k, Coef(kind, 1))
        return out
    raise UnsupportedBound(f"{type(node).__name__} is not supported inside an exponent")


def _invert(g: Growth) -> Growth:
    s = g.single()
    if s is None or s[1].kind != "exact" or abs(s[1].value) <= EPS:
        raise UnsupportedBound("division only by a single monomial")
    key, c = s
    inv_key = tuple((v, (-a, -b, -d)) for v, (a, b, d) in key)
    return Growth({inv_key: [exact(1 / c.value)]}) if inv_key else const(exact(1 / c.value))


def _power(g: Growth, r: Fraction) -> Growth:
    if r == 1:
        return g
    s = g.single()
    if s is None or s[1].kind != "exact" or s[1].value <= 0:
        raise UnsupportedBound("powers only of a single positive monomial inside exponents")
    key, c = s
    new_key = tuple((v, (a * r, b * r, d * r)) for v, (a, b, d) in key)
    return Growth({new_key: [exact(c.value ** float(r))]}) if new_key else const(exact(c.value ** float(r)))


def _log_power(node: Log) -> Fraction:
    if node.power is None:
        return ONE
    p = value_growth(node.power).single()
    if p is None or p[0] != () or p[1].kind != "exact" or p[1].shift:
        raise UnsupportedBound("log powers must be constants")
    return Fraction(p[1].value).limit_denominator(10**6)


def _log_of(g: Growth) -> Growth:
    """log2 of a single monomial: log2(c · Π x^α (log x)^β) = log2 c + Σ α log x + β loglog x."""
    s = g.single()
    if s is None or s[1].sign <= 0:
        raise UnsupportedBound("logarithm only of a single positive monomial")
    key, c = s
    out = const(exact(math.log2(c.value))) if c.kind == "exact" and c.value > EPS else Growth()
    for v, (a, b, d) in key:
        if d != 0:
            raise UnsupportedBound("log of log log is not supported")
        if a:
            out = out + mono(v, (ZERO, ONE, ZERO), exact(a))
        if b:
            out = out + mono(v, (ZERO, ZERO, ONE), exact(b))
    return out


def _log_base_scale(node: Log) -> float:
    if node.base is None:
        return 1.0
    if isinstance(node.base, Const) and node.base.name == "e":
        return 1 / math.log2(math.e)
    if isinstance(node.base, Num) and node.base.value > 1:
        return 1 / math.log2(float(node.base.value))
    raise UnsupportedBound("log base must be a number")


# --- factors: log2 of a factor's value ----------------------------------------


class Unspecified(Exception):
    def __init__(self, var_names: set[str]):
        self.var_names = var_names


def log_growth(node: Node, upper: bool) -> Growth:
    """log2 of the value of a factor; `upper` picks the safe side of estimates."""
    if isinstance(node, Num):
        if node.value <= 0:
            raise UnsupportedBound("factors must be positive")
        return const(exact(math.log2(float(node.value))))
    if isinstance(node, Var):
        return mono(node.name, (ZERO, ONE, ZERO))
    if isinstance(node, Const):
        return Growth()  # a positive constant factor
    if isinstance(node, Mul):
        out = Growth()
        for f in node.factors:
            out = out + log_growth(f, upper)
        return out
    if isinstance(node, Div):
        return log_growth(node.num, upper) - log_growth(node.den, not upper)
    if isinstance(node, Sqrt):
        return log_growth(node.arg, upper).scale(exact(Fraction(1, 2)))
    if isinstance(node, Pow):
        e = value_growth(node.exp)
        base = _base_log(node.base, upper if e.all_nonnegative() else not upper)
        if not e.all_nonnegative() and not _is_constant(base):
            raise UnsupportedBound("a growing base with a decreasing exponent")
        return e * base
    if isinstance(node, Log):  # log2 of log_b(arg)^p = p · log2(log2 arg) + constant
        return _log_of(log_growth(node.arg, upper)).scale(exact(_log_power(node)))
    if isinstance(node, Asym):
        if node.kind == "O" or upper:
            return log_growth(node.arg, upper)  # constants are hidden by O
        raise UnsupportedBound("o(·) as a factor has no lower bound")
    if isinstance(node, Poly):
        return Growth({k: [Coef("big", 1)] for k in log_growth(node.arg, True).terms if k})
    if isinstance(node, Func):
        raise Unspecified(variables(node.arg))
    if isinstance(node, Add):
        return _base_log(node, upper)
    raise UnsupportedBound(f"unsupported factor {type(node).__name__}")


def _is_constant(g: Growth) -> bool:
    return all(k == () for k in g.terms)


def _base_log(node: Node, upper: bool) -> Growth:
    """log2 of a power's base. Handles c - ε and sums of positive terms."""
    if isinstance(node, Add):
        nums = [(s, t) for s, t in node.terms]
        if len(nums) == 2 and isinstance(nums[0][1], Num) and nums[1] == (-1, Const("varepsilon")) and nums[0][0] > 0:
            return const(exact(math.log2(float(nums[0][1].value)), -1))  # log2(c - ε)
        if all(s > 0 for s, _ in nums):
            logs = [log_growth(t, upper) for _, t in nums]
            if upper:  # a1 + ... + ar ≤ r · a1 · ... · ar for ai ≥ 1
                out = const(exact(math.log2(len(logs))))
                for g in logs:
                    out = out + g
                return out
            return logs[0]  # any one term is a lower bound
        raise UnsupportedBound("a base with subtraction, other than c - ε")
    return log_growth(node, upper)


# --- whole bounds --------------------------------------------------------------


@dataclass(frozen=True)
class Term:
    hi: Growth
    lo: Growth
    hidden: Growth = field(default_factory=Growth)  # factors hidden by O* or Õ, unknown
    unspecified: frozenset[str] | None = None  # variables of an f(k) factor
    vars: frozenset[str] = frozenset()


def bound_terms(b: Bound) -> list[Term]:
    expr = b.expr
    pieces = [expr] if not isinstance(expr, Add) else []
    if isinstance(expr, Add):
        for sign, t in expr.terms:
            if sign < 0:
                raise UnsupportedBound("a bound cannot subtract a term")
            pieces.append(t)
    all_vars = variables(expr)
    out = []
    for p in pieces:
        try:
            hi, lo = log_growth(p, True), log_growth(p, False)
            unspec = None
        except Unspecified as u:
            hi, lo, unspec = Growth(), Growth(), frozenset(u.var_names)
        hidden = Growth()
        if b.notation == "O*":
            hidden = mono("N", (ZERO, ONE, ZERO), Coef("big", 1))
        elif b.notation == "Õ":
            for v in sorted(all_vars):
                hidden = hidden + mono(v, (ZERO, ONE, ZERO), Coef("big", 1))
        out.append(Term(hi, lo, hidden, unspec, frozenset(variables(p))))
    return out


def is_monotone(b: Bound) -> bool:
    """Bounds A2: every term nondecreasing in every variable (sufficient check)."""
    try:
        terms = bound_terms(b)
    except UnsupportedBound:
        return False
    for t in terms:
        if t.unspecified is not None:
            continue
        for g in (t.hi, t.lo):
            for key, cs in g.terms.items():
                if not key:
                    continue
                if any(c.sign < 0 for c in cs):
                    return False
                if any(a < 0 or (a == 0 and (b < 0 or (b == 0 and d < 0))) for _, (a, b, d) in key):
                    return False
    return True
