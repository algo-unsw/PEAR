"""A small exact linear-programming solver over the rationals (docs/specs/bounds.md §5).

The comparator's linear programs are tiny (tens of variables), and their solutions are
certificates that are checked again with exact arithmetic, so a plain two-phase simplex
method with Bland's rule over `Fraction` is enough and needs no dependency.

    solve(c, A_ub, b_ub, A_eq, b_eq) maximises c·x subject to A_ub x <= b_ub, A_eq x = b_eq,
    x >= 0, and returns an LPResult with status "optimal", "unbounded" or "infeasible".
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

Vector = list[Fraction]


@dataclass(frozen=True)
class LPResult:
    status: str  # optimal | unbounded | infeasible
    x: tuple[Fraction, ...] = ()
    value: Fraction | None = None


def _f(v) -> Fraction:  # noqa: ANN001
    return v if isinstance(v, Fraction) else Fraction(v)


def solve(
    c: Sequence,
    a_ub: Sequence[Sequence] = (),
    b_ub: Sequence = (),
    a_eq: Sequence[Sequence] = (),
    b_eq: Sequence = (),
    max_pivots: int = 5000,
) -> LPResult:
    n = len(c)
    rows: list[Vector] = []
    rhs: list[Fraction] = []
    kinds: list[str] = []  # ub | eq
    for row, b in zip(a_ub, b_ub):
        rows.append([_f(v) for v in row])
        rhs.append(_f(b))
        kinds.append("ub")
    for row, b in zip(a_eq, b_eq):
        rows.append([_f(v) for v in row])
        rhs.append(_f(b))
        kinds.append("eq")
    m = len(rows)
    # standard form: one slack per inequality, one artificial per row that needs it
    n_slack = sum(1 for k in kinds if k == "ub")
    width = n + n_slack
    tab: list[Vector] = []
    basis: list[int] = []
    artificial: list[int] = []
    slack_i = n
    for i in range(m):
        row = rows[i] + [Fraction(0)] * n_slack
        b = rhs[i]
        if kinds[i] == "ub":
            row[slack_i] = Fraction(1)
            slack_col = slack_i
            slack_i += 1
        else:
            slack_col = None
        if b < 0:
            row = [-v for v in row]
            b = -b
            slack_col = None  # the slack now has coefficient -1: not a basis column
        tab.append(row + [b])
        basis.append(slack_col if slack_col is not None else -1)
    # artificials for rows without a basis column
    for i in range(m):
        if basis[i] == -1:
            col = width + len(artificial)
            artificial.append(col)
            basis[i] = col
    total = width + len(artificial)
    for i in range(m):
        b = tab[i].pop()
        tab[i] += [Fraction(0)] * len(artificial) + [b]
        if basis[i] >= width:
            tab[i][basis[i]] = Fraction(1)

    def pivot(r: int, col: int) -> None:
        pr = tab[r]
        pv = pr[col]
        if pv != 1:
            tab[r] = pr = [v / pv for v in pr]
        for i in range(m):
            if i != r and tab[i][col] != 0:
                f = tab[i][col]
                ti = tab[i]
                tab[i] = [a - f * b for a, b in zip(ti, pr)]
        basis[r] = col

    def run(obj: Vector, allowed: int) -> str:
        """Maximise obj·x over the current tableau; columns >= allowed may not enter."""
        for _ in range(max_pivots):
            # reduced costs: obj_j - sum obj_basis * column
            best = None
            for j in range(allowed):
                if j in basis:
                    continue
                rc = obj[j] - sum(obj[basis[i]] * tab[i][j] for i in range(m) if obj[basis[i]] != 0)
                if rc > 0:
                    best = j  # Bland: the lowest index with a positive reduced cost
                    break
            if best is None:
                return "optimal"
            ratios = [(tab[i][-1] / tab[i][best], basis[i], i) for i in range(m) if tab[i][best] > 0]
            if not ratios:
                return "unbounded"
            _, _, r = min(ratios)
            pivot(r, best)
        raise RuntimeError("simplex did not terminate")

    if artificial:
        phase1 = [Fraction(0)] * total
        for col in artificial:
            phase1[col] = Fraction(-1)
        run(phase1, total)
        if any(tab[i][-1] != 0 for i in range(m) if basis[i] >= width):
            return LPResult("infeasible")
        # drive remaining artificials out of the basis (degenerate rows)
        for i in range(m):
            if basis[i] >= width:
                col = next((j for j in range(width) if tab[i][j] != 0), None)
                if col is not None:
                    pivot(i, col)
    obj = [_f(v) for v in c] + [Fraction(0)] * (total - n)
    status = run(obj, width)
    if status == "unbounded":
        return LPResult("unbounded")
    x = [Fraction(0)] * total
    for i in range(m):
        x[basis[i]] = tab[i][-1]
    value = sum((obj[j] * x[j] for j in range(n)), Fraction(0))
    return LPResult("optimal", tuple(x[:n]), value)
