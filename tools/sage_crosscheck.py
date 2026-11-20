"""Cross-check the comparator against SageMath's asymptotic expansions (decided 21 November 2026).

Run by hand when adding or changing running times; not part of CI and not imported by PEAR.
SageMath is GPLv2+; this script only calls it from a separate environment.

Setup (once):

    python -m venv ~/.venvs/pear-sage
    ~/.venvs/pear-sage/bin/pip install passagemath-symbolics passagemath-repl \\
        passagemath-combinat passagemath-graphs passagemath-maxima
    ~/.venvs/pear-sage/bin/pip install -e .

Use:

    ~/.venvs/pear-sage/bin/python tools/sage_crosscheck.py --since origin/main
    ~/.venvs/pear-sage/bin/python tools/sage_crosscheck.py --algorithm max-cut--n--folklore
    ~/.venvs/pear-sage/bin/python tools/sage_crosscheck.py --problem max-cut

What it checks. Sage treats variables as independent and has no constraints, so the
comparison is made on one-variable slices: every variable is set to a simple function of t
(t, t/2, t - 3, 3, sqrt(t), t^2/4, ...), keeping only slices that satisfy the problem's
constraints for large t. On each slice, Sage compares the two O* forms, up to a factor
t^50 for polynomial factors. Then:

- the comparator says a is at most b (better, equal, tie): a must be at most b on every
  slice; otherwise the comparator is wrong, or a constraint is missing (ERROR);
- the comparator says incomparable: with --notes, list pairs where a is at most b on every
  slice (NOTE). Often this is only because the slices that separate them are not expressible
  (Sage has no 2^(t^2) or 2^(sqrt t)), so a NOTE is a hint, never a reason to change a result.

Pairs or slices Sage cannot express (o() and O() in exponents, ε and δ families, f(k), k!,
Bell numbers, mixed growth such as n^k with k not constant) are skipped and counted. Named
constants (ω) are checked at both ends of their known range; a verdict that differs between
the ends is skipped.

The exit status is 1 if there is an ERROR.
"""

from __future__ import annotations

import argparse
import itertools
import random
import subprocess
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

from pear.bounds.compare import Relation, compare_ostar
from pear.bounds.display import ostar
from pear.bounds.expr import (Add, Asym, Bell, Const, Div, Fact, Func, Log, Mul, Num, Pow, Sqrt, Var, children,
                              render, variables)
from pear.bounds.expr import parse_expr
from pear.bounds.numeric import value
from pear.derive import Engine
from pear.validate import validate_dir

ROOT = Path(__file__).resolve().parent.parent
POLY_SLACK = 50  # O* on a slice: a <=* b iff a = O(b t^50)


class Inexpressible(Exception):
    pass


# --- slices -------------------------------------------------------------------------------

# each variable is c * t^e + d; n-like variables also get the edge-count shapes
MENU: list[tuple[str, str]] = [
    ("t", "t"), ("t/2", "t/2"), ("2t", "2 t"), ("t-3", "t - 3"), ("3", "3"),
    ("sqrt t", "t^{1/2}"), ("t^2/4", "t^{2}/4"), ("t(t-1)/2", "t (t - 1)/2"), ("t^2", "t^{2}"),
]


def slices(symbols: list[str], constraints: list[str], limit: int = 60, seed: int = 0) -> list[dict[str, str]]:
    """Assignments variable -> expression in t that satisfy the constraints at t = 10^6 and
    10^9; some systematic (all t, one variable varied), the rest sampled."""
    syms = sorted(symbols)
    parsed = []
    for text in constraints:
        for op, flip in (("\\le", False), ("\\ge", True)):
            if op in text:
                left, right = (s.strip() for s in text.split(op, 1))
                small, large = (right, left) if flip else (left, right)
                parsed.append((parse_expr(small, set(syms)), parse_expr(large, set(syms))))
                break
    menu_nodes = {label: parse_expr(tex, {"t"}) for label, tex in MENU}

    def ok(assign: dict[str, str]) -> bool:
        for tval in (1e6, 1e9):
            env = {v: value(menu_nodes[assign[v]], {"t": tval}) for v in syms}
            if any(x is None or x < 1 for x in env.values()):
                return False
            for small, large in parsed:
                a, b = value(small, env), value(large, env)
                if a is None or b is None or a > b * (1 + 1e-12):
                    return False
        return True

    labels = [label for label, _ in MENU]
    candidates: list[dict[str, str]] = []
    base = {v: "t" for v in syms}
    candidates.append(base)
    for v in syms:
        for label in labels:
            candidates.append({**base, v: label})
    for v, w in itertools.combinations(syms, 2):
        for a, b in itertools.product(labels, repeat=2):
            candidates.append({**base, v: a, w: b})
    rng = random.Random(seed)
    for _ in range(2000):
        candidates.append({v: rng.choice(labels) for v in syms})
    out: list[dict[str, str]] = []
    seen = set()
    for c in candidates:
        key = tuple(sorted(c.items()))
        if key in seen or all(x == "3" for x in c.values()):
            continue
        seen.add(key)
        if ok(c):
            out.append(c)
    systematic = out[: limit // 2]
    rest = out[limit // 2:]
    rng.shuffle(rest)
    return systematic + rest[: limit - len(systematic)]


# --- translation to Sage ------------------------------------------------------------------


class Sage:
    def __init__(self) -> None:
        from sage.all__sagemath_symbolics import QQ, SR, AsymptoticRing, O, RealField, log

        self.QQ, self.SR, self.O, self.log = QQ, SR, O, log
        self.RF = RealField(100)
        self.digits = 12
        self.A = AsymptoticRing("QQ^t * t^QQ * log(t)^QQ", SR, default_prec=5)
        self.t = self.A.gen()
        self.menu = {label: self.expr_in_t(parse_expr(tex, {"t"})) for label, tex in MENU}
        self.slack = self.lead(self.t ** POLY_SLACK)
        self.g_one = self.lead(self.A(1))
        self.g_t = self.lead(self.t)
        self.g_log = self.lead(self.log(self.t))
        self.digits = 12

    def q(self, f: Fraction):
        return self.QQ((f.numerator, f.denominator))

    def expr_in_t(self, node):
        return self.convert(node, {"t": None}, {})

    def convert(self, node, assign, consts):
        """node with variables replaced by Sage elements (assign[v]); None stands for t."""
        A, QQ = self.A, self.QQ
        if not variables(node) and not isinstance(node, Num):
            # a constant such as 3 * 2^(omega - 1) + 1: evaluated here, since Sage's symbolic
            # arithmetic can stall on it
            v = value(node, {"\\" + c: float(x) for c, x in consts.items()})
            if v is None or v <= 0:
                raise Inexpressible("constant")
            return A(self.q(Fraction(v).limit_denominator(10**self.digits)))
        if isinstance(node, Num):
            return A(self.q(node.value))
        if isinstance(node, Var):
            if node.name not in assign:
                raise Inexpressible(f"variable {node.name}")
            got = assign[node.name]
            return self.t if got is None else got
        if isinstance(node, Const):
            if node.deps or node.name not in consts:
                raise Inexpressible(f"constant {node.name}")
            return A(self.q(consts[node.name]))
        if isinstance(node, Add):
            out = A(0)
            for sign, term in node.terms:
                out += sign * self.convert(term, assign, consts)
            return out
        if isinstance(node, Mul):
            out = A(1)
            for f in node.factors:
                out *= self.convert(f, assign, consts)
            return out
        if isinstance(node, Div):
            return self.convert(node.num, assign, consts) / self.convert(node.den, assign, consts)
        if isinstance(node, Sqrt):
            return self.convert(node.arg, assign, consts) ** QQ((1, 2))
        if isinstance(node, Pow):
            base = self.convert(node.base, assign, consts)
            exp = self.convert(node.exp, assign, consts)
            if exp.is_exact() and len(self._terms(exp)) <= 1 and self._constant(exp):
                return base ** self._as_number(exp)
            if self._constant(base):
                return self._exp(self._as_number(base), exp)
            raise Inexpressible("power with variable base and exponent")
        if isinstance(node, Log):
            if node.base is not None or node.power is not None:
                arg = self.convert(node.arg, assign, consts)
                b = 2 if node.base is None else self._as_number(self.convert(node.base, assign, consts))
                p = 1 if node.power is None else self._as_number(self.convert(node.power, assign, consts))
                return (self.log(arg) / self.log(self.SR(b))) ** p
            return self.log(self.convert(node.arg, assign, consts)) / self.log(self.SR(2))
        if isinstance(node, (Asym, Func, Fact, Bell)):
            raise Inexpressible(type(node).__name__)
        raise Inexpressible(type(node).__name__)

    def _approx(self, x):
        """A rational within 10^-digits of x: Sage is slow with bases such as
        2^(2371339/3000000), so irrational bases are rounded; verdicts that change between
        two precisions are dropped."""
        f = Fraction(str(self.RF(x))).limit_denominator(10**self.digits)
        return self.q(f)

    def _exp(self, c, e):
        """c^e for a constant c > 0, term by term: c^(a t) = (c^a)^t, c^(a log t) = t^(a ln c),
        c^a a constant."""
        if not e.is_exact():
            raise Inexpressible("O-term in an exponent")
        out = self.A(1)
        for term in self._terms(e):
            a, g = term.coefficient, term.growth
            if g == self.g_one:
                out *= self.A(self._approx(self.SR(c) ** a))
            elif g == self.g_t:
                out *= self.A(self._approx(self.SR(c) ** a)) ** self.t
            elif g == self.g_log:
                out *= self.t ** self._approx(a * self.SR(c).log())
            else:
                raise Inexpressible(f"exponent term {g}")
        return out

    @staticmethod
    def _terms(x) -> list:
        return list(x.summands.elements())

    def _constant(self, x) -> bool:
        return all(s.growth == s.growth.parent().one() for s in self._terms(x))

    def _as_number(self, x):
        terms = self._terms(x)
        if not terms:
            return 0
        if len(terms) > 1 or not self._constant(x) or not x.is_exact():
            raise Inexpressible("not a constant")
        return terms[0].coefficient

    def lead(self, x):
        """The growth of the leading term (one variable: the order is total)."""
        tops = list(x.summands.maximal_elements())
        if len(tops) != 1:
            raise Inexpressible("no single leading term")
        return tops[0].growth

    def le_star(self, ga, gb) -> bool:
        """growth a <= growth b * t^50, i.e. a = O*(b) on the slice."""
        return ga <= gb * self.slack


# --- pairs --------------------------------------------------------------------------------


def git_changed(since: str) -> set[str]:
    out = subprocess.run(["git", "diff", "--name-only", since, "--", "data/algorithms", "data/reductions"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return {Path(p).stem for p in out.split() if p.endswith(".yaml")}


def run(args: argparse.Namespace) -> int:
    data, _ = validate_dir(ROOT / "data")
    engine = Engine(data)
    candidates: dict[tuple[str, str], list] = defaultdict(list)
    insert = engine.insert

    def recording(r):  # every result the engine considers, kept or dropped
        candidates[(r.problem, r.node)].append(r)
        return insert(r)

    engine.insert = recording  # type: ignore[method-assign]
    d = engine.run()

    focus: set[str] = set(args.algorithm or [])
    if args.since:
        focus |= git_changed(args.since)

    def in_focus(r) -> bool:
        return not focus or bool(focus & set(r.id.split("|")))

    sage = Sage()
    from cysignals.alarm import AlarmInterrupt, alarm, cancel_alarm
    errors = notes = checked = skipped = 0
    for (pid, node), rs in sorted(candidates.items()):
        if args.problem and pid not in args.problem:
            continue
        problem = data.problems[pid]
        ctx = d.published[pid]
        rs = [r for r in rs if not r.props.quantum]
        forms: dict[str, object] = {}
        for r in rs:  # one representative per O* form
            forms.setdefault(render(ostar(r.bound, ctx).expr), r)
        focus_forms = {k for k, r in forms.items() if any(in_focus(x) for x in rs
                                                         if render(ostar(x.bound, ctx).expr) == k)}
        if not focus_forms:
            continue
        if args.verbose:
            print(f"{pid} [{node}]: {len(forms)} O* forms, {len(focus_forms)} in focus", flush=True)
        cuts = slices(sorted(problem.symbols()), [c.constraint for c in problem.constraints], limit=args.slices)
        ends = [{c: Fraction(lo).limit_denominator(10**6) for c, (lo, _) in ctx.constants.items()},
                {c: Fraction(hi).limit_denominator(10**6) for c, (_, hi) in ctx.constants.items()}]
        exprs = {k: ostar(r.bound, ctx).expr for k, r in forms.items()}
        named = {c for e in exprs.values() for c in _consts(e)}
        ends = [e for i, e in enumerate(ends) if i == 0 or named & set(e)]  # one end if no named constant
        grown: dict = {}
        hopeless: set[str] = set()  # forms Sage stalled on once

        def growth(k, cut):
            """Leading growth of form k on the slice, at each end of the constants; None if
            Sage cannot express it."""
            key = (k, tuple(sorted(cut.items())))
            if k in hopeless:
                return None
            if key not in grown:
                try:
                    assign = {v: sage.menu[label] for v, label in cut.items()}
                    grown[key] = []
                    alarm(args.seconds)  # Sage can stall on some expressions: give up on them
                    for digits in (12, 9):  # each constant end, at two roundings of irrational bases
                        sage.digits = digits
                        grown[key] += [sage.lead(sage.convert(exprs[k], assign, consts)) for consts in ends]
                    cancel_alarm()
                except Inexpressible:
                    cancel_alarm()
                    grown[key] = None
                except AlarmInterrupt:
                    if args.verbose:
                        print(f"  sage: gave up after {args.seconds} s on {k}")
                    hopeless.add(k)
                    grown[key] = None
                except Exception as exc:  # Sage cannot build some growths (e.g. 2^(t^2))
                    cancel_alarm()
                    if args.verbose:
                        print(f"  sage: {type(exc).__name__}: {str(exc).splitlines()[0][:100]}")
                    grown[key] = None
            return grown[key]

        for ka, kb in itertools.permutations(forms, 2):
            if ka not in focus_forms and kb not in focus_forms:
                continue
            a, b = forms[ka], forms[kb]
            rel = compare_ostar(engine.analyse_ostar(a), engine.analyse_ostar(b), ctx)
            claim_le = rel in (Relation.BETTER, Relation.EQUAL, Relation.TIE)
            if rel not in (Relation.BETTER, Relation.EQUAL, Relation.TIE, Relation.INCOMPARABLE):
                continue  # WORSE is checked as the reversed pair
            verdicts = []
            for cut in cuts:
                ga, gb = growth(ka, cut), growth(kb, cut)
                if ga is None or gb is None:
                    continue
                at_ends = {sage.le_star(x, y) for x, y in zip(ga, gb)}
                if len(at_ends) == 1:
                    verdicts.append((cut, at_ends.pop()))
            if not verdicts:
                skipped += 1
                continue
            checked += 1
            where = f"{pid} [{node}]"
            if claim_le:
                bad = [cut for cut, le in verdicts if not le]
                if bad:
                    errors += 1
                    print(f"ERROR {where}: comparator says O*({ka}) {rel.value} O*({kb}), but Sage finds it larger on "
                          f"{len(bad)} of {len(verdicts)} slices, e.g. {_show(bad[0])}\n      {a.id}\n      {b.id}")
            elif args.notes and all(le for _, le in verdicts):
                notes += 1
                print(f"NOTE  {where}: comparator says O*({ka}) and O*({kb}) are incomparable, but the first is at "
                      f"most the second on all {len(verdicts)} slices that Sage can express\n      {a.id}\n      {b.id}")
    print(f"\n{checked} ordered pairs checked, {skipped} not expressible in Sage; {errors} errors, {notes} notes")
    return 1 if errors else 0


def _consts(node) -> set[str]:
    if isinstance(node, Const):
        return {node.name}
    out: set[str] = set()
    for child in children(node):
        out |= _consts(child)
    return out


def _show(cut: dict[str, str]) -> str:
    return ", ".join(f"{v} = {label}" for v, label in sorted(cut.items()))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--algorithm", action="append", help="check pairs involving results through this entry (algorithm or reduction id)")
    p.add_argument("--since", help="check pairs involving algorithms and reductions changed since this git ref")
    p.add_argument("--problem", action="append", help="only this problem")
    p.add_argument("--slices", type=int, default=40, help="slices per problem (default 40)")
    p.add_argument("--notes", action="store_true",
                   help="also list incomparable pairs where one side is at most the other on every slice Sage can express "
                        "(often only because Sage cannot express the slices that separate them)")
    p.add_argument("--seconds", type=float, default=5, help="time limit for one Sage conversion (default 5)")
    p.add_argument("--verbose", action="store_true")
    sys.exit(run(p.parse_args()))


if __name__ == "__main__":
    main()
