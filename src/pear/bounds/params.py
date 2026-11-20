"""The parameters a bound is listed under (rulebook §7, D1).

A bound whose O* form depends on its variables only through one sum or difference of
variables is listed under that expression: $1.977^{m-k}$ is a bound "by $m - k$", not "by $k$
and $m$" (Serge, 20 November 2026: a general rule). Otherwise a bound is listed under its
variables, as before: $1.4423^{dk}$ by $d$ and $k$, $2^{m - 3n/5}$ by $m$ and $n$ (Serge,
20 November 2026, same day).

The composite expression is found syntactically. The maximal polynomial subterms that carry
variables (the "atoms") are collected; a positive constant factor and an additive constant are
stripped from each ($2^{(n(n-1)/2 - m)/4}$ has the atom $n(n-1)/2 - m$). If every atom is
the same sum or difference of at least two variables up to a constant factor, the bound is
listed under it; if every atom has a single variable, under those variables; anything mixed
(e.g. $n^{\\omega (n - k)/3}$, atoms $n$ and $n - k$) is listed under its variables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Sequence

from .expr import Add, Const, Div, Mul, Node, Num, Pow, Var, children, render, variables

Monomial = tuple[tuple[str, int], ...]
Polynomial = dict[Monomial, Fraction]


@dataclass(frozen=True)
class Parameter:
    """A parameter a bound is listed under: a variable ('k') or a composite expression,
    keyed by its TeX ('m - k')."""

    key: str
    variables: frozenset[str]
    composite: bool = False
    node: Node | None = field(default=None, compare=False, hash=False)

    @property
    def tex(self) -> str:
        return self.key if self.composite else render(Var(self.key))


def _poly(node: Node) -> Polynomial | None:
    """The polynomial a node denotes, with rational coefficients, or None."""
    if isinstance(node, Num):
        return {(): node.value} if node.value else {}
    if isinstance(node, Var):
        return {((node.name, 1),): Fraction(1)}
    if isinstance(node, Add):
        out: Polynomial = {}
        for sign, t in node.terms:
            p = _poly(t)
            if p is None:
                return None
            for mono, c in p.items():
                out[mono] = out.get(mono, Fraction(0)) + sign * c
        return {m: c for m, c in out.items() if c}
    if isinstance(node, Mul):
        acc: Polynomial = {(): Fraction(1)}
        for f in node.factors:
            p = _poly(f)
            if p is None:
                return None
            acc = _mul(acc, p)
        return acc
    if isinstance(node, Div):
        num, den = _poly(node.num), _poly(node.den)
        if num is None or den is None or set(den) != {()} or not den[()]:
            return None
        return {m: c / den[()] for m, c in num.items()}
    if isinstance(node, Pow):
        if not isinstance(node.exp, Num) or node.exp.value.denominator != 1 or node.exp.value < 0:
            return None
        base = _poly(node.base)
        if base is None:
            return None
        acc = {(): Fraction(1)}
        for _ in range(int(node.exp.value)):
            acc = _mul(acc, base)
        return acc
    return None


def _mul(a: Polynomial, b: Polynomial) -> Polynomial:
    out: Polynomial = {}
    for ma, ca in a.items():
        for mb, cb in b.items():
            powers: dict[str, int] = {}
            for v, e in ma + mb:
                powers[v] = powers.get(v, 0) + e
            mono = tuple(sorted(powers.items()))
            out[mono] = out.get(mono, Fraction(0)) + ca * cb
    return {m: c for m, c in out.items() if c}


def _normal(p: Polynomial) -> tuple[tuple[Monomial, Fraction], ...]:
    """p without its constant term, divided by its first coefficient: equal for expressions
    that determine each other through x -> a x + b."""
    q = {m: c for m, c in p.items() if m}
    if not q:
        return ()
    lead = q[min(q)]
    return tuple(sorted((m, c / lead) for m, c in q.items()))


def _strip(node: Node) -> Node:
    """Remove a constant factor, divisor or additive term at the top: 9m/50 -> m,
    (X)/4 -> X, \\omega k/3 -> k, X + 4 -> X."""
    if isinstance(node, Div) and not variables(node.den):
        return _strip(node.num)
    if isinstance(node, Mul):
        kept = [f for f in node.factors if variables(f)]
        if len(kept) == 1:
            return _strip(kept[0])
        if len(kept) < len(node.factors):
            return Mul(tuple(kept))
        return node
    if isinstance(node, Add):
        kept = tuple((s, t) for s, t in node.terms if variables(t))
        if len(kept) == 1 and kept[0][0] > 0:
            return _strip(kept[0][1])
        if 0 < len(kept) < len(node.terms):
            return Add(kept)
        return node
    return node


def _atoms(node: Node) -> list[Node] | None:
    """The maximal polynomial subterms with variables, stripped; None if a variable occurs
    outside any (as the subscript of an ε_k)."""
    if not variables(node):
        return []
    if isinstance(node, Const):
        return None  # ε_k: depends on k in an unknown way
    stripped = _strip(node)
    if _poly(stripped) is not None:
        return [stripped]
    out: list[Node] = []
    for child in children(node):
        got = _atoms(child)
        if got is None:
            return None
        out.extend(got)
    return out


def _ordered(node: Node, order: Sequence[str]) -> Node:
    """Top-level terms in reading order: positive terms first, then by the problem's order of
    their variables, so that n + m and m + n get one key."""
    if not isinstance(node, Add):
        return node

    def key(item: tuple[int, tuple[int, Node]]) -> tuple:
        i, (sign, t) = item
        rank = min((order.index(v) if v in order else len(order) for v in variables(t)), default=len(order))
        return (sign < 0, rank, sorted(variables(t)), i)

    terms = [t for _, t in sorted(enumerate(node.terms), key=key)]
    if terms[0][0] < 0:
        return node
    return Add(tuple(terms))


def listed_parameters(expr: Node, order: Iterable[str] = ()) -> tuple[Parameter, ...]:
    """The parameters an O* expression is listed under, in the problem's reading order."""
    order = list(order)
    names = variables(expr)

    def plain() -> tuple[Parameter, ...]:
        ranked = sorted(names, key=lambda v: (order.index(v) if v in order else len(order), v))
        return tuple(Parameter(v, frozenset({v})) for v in ranked)

    atoms = _atoms(expr)
    if not atoms or len(names) < 2:
        return plain()
    forms = {_normal(_poly(a) or {}) for a in atoms}
    if len(forms) != 1 or any(len(variables(a)) < 2 for a in atoms):
        return plain()
    # only sums and differences of variables (m - k, n + m); products, other coefficients and
    # higher degrees keep their variables: d k, m - 3n/5, n(n-1)/2 - m (Serge, 20 November 2026)
    (form,) = forms
    if any(len(mono) != 1 or mono[0][1] != 1 or abs(c) != 1 for mono, c in form):
        return plain()
    node = _ordered(atoms[0], order)
    return (Parameter(render(node), frozenset(variables(node)), True, node),)
