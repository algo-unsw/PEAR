"""Numeric evaluation of bounds, for a common-sense cross-check of the comparator.

The comparator (compare.py) is sound but incomplete: what it cannot prove it treats as
incomparable, so a bound that is obviously beaten can stay listed. This module evaluates
O* forms at sample points that satisfy a problem's constraints. When one bound is at most
another at every sample, the pair is reported as *undecided*: the engine should be able to
decide it, and a person or an AI should add the missing fact (a constraint) or comparator
rule (decided 18 November 2026). Numeric evidence never decides anything by itself.
"""

from __future__ import annotations

import math
import random
from typing import Iterable

from .expr import Add, Asym, Bell, Const, Div, Fact, Func, Log, Mul, Node, Num, Poly, Pow, Sqrt, Var, parse_expr


def value(node: Node, env: dict[str, float]) -> float | None:
    """The value of an expression without unknowns, or None (unknowns, overflow, domain)."""
    try:
        if isinstance(node, Num):
            return float(node.value)
        if isinstance(node, Var):
            return env.get(node.name)
        if isinstance(node, Const):
            return env.get("\\" + node.name) if not node.deps else None
        if isinstance(node, Add):
            vals = [value(t, env) for _, t in node.terms]
            return None if None in vals else sum(s * v for (s, _), v in zip(node.terms, vals))  # type: ignore[misc]
        if isinstance(node, Mul):
            out = 1.0
            for f in node.factors:
                v = value(f, env)
                if v is None:
                    return None
                out *= v
            return out
        if isinstance(node, Div):
            a, b = value(node.num, env), value(node.den, env)
            return None if a is None or not b else a / b
        if isinstance(node, Pow):
            a, b = value(node.base, env), value(node.exp, env)
            if a is None or b is None or a < 0 or (a == 0 and b <= 0):
                return None
            return a ** b
        if isinstance(node, Sqrt):
            a = value(node.arg, env)
            return None if a is None or a < 0 else math.sqrt(a)
        if isinstance(node, Log):
            return _log(node, env, value(node.arg, env))
        if isinstance(node, (Fact, Bell)):
            a = value(node.arg, env)
            if a is None or a < 0:
                return None
            return math.gamma(a + 1) if isinstance(node, Fact) else math.exp(_log_bell(a))
    except (OverflowError, ZeroDivisionError, ValueError):
        return None
    return None  # Asym, Func, Poly: unknown functions


def _bell_numbers(limit: int) -> list[int]:
    """B_0, ..., B_limit by the Bell triangle."""
    out, row = [1], [1]
    for _ in range(limit):
        nxt = [row[-1]]
        for v in row:
            nxt.append(nxt[-1] + v)
        row = nxt
        out.append(row[0])
    return out


_BELL = _bell_numbers(400)


def _log_bell(x: float) -> float:
    """ln B_x: exact for integers up to 400 (interpolated in between), else de Bruijn's
    asymptotic expansion ln B_x = x(ln x - ln ln x - 1 + ln ln x/ln x + 1/ln x + (ln ln x/ln x)^2/2) + O(x (ln ln x/ln x)^2 / ln x)."""
    if x <= 400:
        lo = int(math.floor(x))
        a, b = math.log(_BELL[lo]), math.log(_BELL[min(lo + 1, 400)])
        return a + (x - lo) * (b - a)
    l, ll = math.log(x), math.log(math.log(x))
    return x * (l - ll - 1 + ll / l + 1 / l + (ll / l) ** 2 / 2)


def _log(node: Log, env: dict[str, float], arg: float | None) -> float | None:
    base = 2.0 if node.base is None else value(node.base, env)
    if arg is None or base is None or arg <= 0 or base <= 1:
        return None
    out = math.log(arg) / math.log(base)
    if node.power is not None:
        p = value(node.power, env)
        if p is None or out <= 0:
            return None
        out = out ** p
    return out


def log_value(node: Node, env: dict[str, float]) -> float | None:
    """The natural logarithm of a positive expression, computed so that c^{n^2} does not
    overflow; None if unknown or not positive."""
    try:
        if isinstance(node, Mul):
            parts = [log_value(f, env) for f in node.factors]
            return None if None in parts else sum(parts)  # type: ignore[arg-type]
        if isinstance(node, Div):
            a, b = log_value(node.num, env), log_value(node.den, env)
            return None if a is None or b is None else a - b
        if isinstance(node, Pow):
            e = value(node.exp, env)
            b = log_value(node.base, env)
            return None if e is None or b is None else e * b
        if isinstance(node, Sqrt):
            a = log_value(node.arg, env)
            return None if a is None else a / 2
        if isinstance(node, Add):
            pos = [log_value(t, env) for s, t in node.terms if s > 0]
            neg = [log_value(t, env) for s, t in node.terms if s < 0]
            if None in pos or None in neg or not pos:
                return None
            p = _logsumexp(pos)  # type: ignore[arg-type]
            if not neg:
                return p
            q = _logsumexp(neg)  # type: ignore[arg-type]
            return None if q >= p else p + math.log1p(-math.exp(q - p))
        if isinstance(node, (Asym, Func, Poly)):
            return None
        if isinstance(node, (Fact, Bell)):
            a = value(node.arg, env)
            if a is None or a < 0:
                return None
            return math.lgamma(a + 1) if isinstance(node, Fact) else _log_bell(a)
        v = value(node, env)
        return None if v is None or v <= 0 else math.log(v)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None


def interval(node: Node, ranges: dict[str, tuple[float, float]]) -> tuple[float, float] | None:
    """Bounds on a constant expression whose named constants lie in the given ranges (e.g.
    1 + 3 \\cdot 2^{\\omega - 1} with 2 <= ω <= 2.372). None if not such an expression."""
    try:
        if isinstance(node, Num):
            v = float(node.value)
            return v, v
        if isinstance(node, Const):
            return ranges.get(node.name) if not node.deps else None
        if isinstance(node, Add):
            lo = hi = 0.0
            for sign, t in node.terms:
                r = interval(t, ranges)
                if r is None:
                    return None
                lo, hi = (lo + r[0], hi + r[1]) if sign > 0 else (lo - r[1], hi - r[0])
            return lo, hi
        if isinstance(node, (Mul, Div)):
            parts = [interval(f, ranges) for f in (node.factors if isinstance(node, Mul) else (node.num, node.den))]
            if None in parts:
                return None
            lo, hi = parts[0]  # type: ignore[misc]
            for i, (a, b) in enumerate(parts[1:]):  # type: ignore[misc]
                if isinstance(node, Div):
                    if a <= 0 <= b:
                        return None
                    a, b = 1 / b, 1 / a
                cands = [lo * a, lo * b, hi * a, hi * b]
                lo, hi = min(cands), max(cands)
            return lo, hi
        if isinstance(node, Pow):
            base, exp = interval(node.base, ranges), interval(node.exp, ranges)
            if base is None or exp is None or base[0] <= 0:
                return None
            # x^y is monotone in x and in y separately for x > 0: corners, plus x = 1 or y = 0
            xs = list(base) + ([1.0] if base[0] < 1 < base[1] else [])
            ys = list(exp) + ([0.0] if exp[0] < 0 < exp[1] else [])
            cands = [x ** y for x in xs for y in ys]
            return min(cands), max(cands)
        if isinstance(node, Sqrt):
            r = interval(node.arg, ranges)
            return None if r is None or r[0] < 0 else (math.sqrt(r[0]), math.sqrt(r[1]))
    except (OverflowError, ZeroDivisionError, ValueError):
        return None
    return None


def _logsumexp(xs: list[float]) -> float:
    m = max(xs)
    return m + math.log(sum(math.exp(x - m) for x in xs))


def samples(symbols: Iterable[str], constraints: Iterable[str], constants: dict[str, tuple[float, float]],
            count: int = 400, seed: int = 0) -> list[dict[str, float]]:
    """Points with every variable at least 1 that satisfy the constraints (small ≤ large),
    at several scales; each named constant at both ends of its known range."""
    syms = sorted(set(symbols))
    parsed = []
    for text in constraints:
        for op, flip in (("\\le", False), ("\\ge", True)):
            if op in text:
                left, right = (s.strip() for s in text.split(op, 1))
                small, large = (right, left) if flip else (left, right)
                parsed.append((parse_expr(small, syms), parse_expr(large, syms)))
                break
    rng = random.Random(seed)
    out: list[dict[str, float]] = []
    ends = [{f"\\{c}": lo for c, (lo, _) in constants.items()}, {f"\\{c}": hi for c, (_, hi) in constants.items()}]
    tight = [(small.name, large) for small, large in parsed if isinstance(small, Var)]
    tries = 0
    while len(out) < count and tries < count * 200:
        tries += 1
        scale = 10 ** rng.choice([2, 3, 4, 6])
        env = {v: math.exp(rng.uniform(0, math.log(scale ** 3))) for v in syms}
        env.update(ends[tries % 2])
        # extremes matter (k close to n, m close to n(n-1)/2, a variable at 1): push some
        # variables to their upper limit minus a little, or down to 1
        for name, large in rng.sample(tight, len(tight)):
            r = rng.random()
            if r < 0.35:
                top = value(large, env)
                if top is not None and top >= 1:
                    env[name] = max(1.0, top - rng.choice([0, 0, 1, 2, rng.uniform(0, math.sqrt(top))]))
            elif r < 0.45:
                env[name] = 1.0
        ok = True
        for small, large in parsed:
            a, b = value(small, env), value(large, env)
            if a is None or b is None or a > b:
                ok = False
                break
        if ok:
            out.append(env)
    return out


def dominates(a: Node, b: Node, points: list[dict[str, float]], margin: float = 1e-9) -> bool | None:
    """True if a ≤ b at every point (in logarithms, up to a relative margin), False if not,
    None if a value is unknown at some point or there are no points."""
    if not points:
        return None
    for env in points:
        la, lb = log_value(a, env), log_value(b, env)
        if la is None or lb is None:
            return None
        if la > lb + margin * max(1.0, abs(lb)):
            return False
    return True
