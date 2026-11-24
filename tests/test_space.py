"""Time–space frontiers (decided 23 November 2026): stated space bounds, domination in both
time and space, transfer along reductions and projections, and the frontier output."""

from __future__ import annotations

import pytest

from pear.derive import derive, to_json
from pear.schema import ENTITY_TYPES
from pear.validate import validate_raw

from test_derive import alg, dataset, problem, red, rows


def spaced(aid, prob, bound, space_bound=None, space="exponential", **kw):
    out = alg(aid, prob, bound, space=space, **kw)
    if space_bound is not None:
        out["properties"]["space"]["bound"] = space_bound
    return out


def frontier(data, pid, node="decision"):
    out = to_json(data, derive(data))
    by_id = {r["id"]: r for r in out["problems"].get(pid, {}).get(node, [])}
    entries = out["frontier"].get(pid, {}).get(node, [])
    return [(by_id[e["members"][0]]["shown"], by_id[e["members"][0]]["space"]) for e in entries]


def test_a_slower_algorithm_in_less_space_is_kept_and_the_frontier_is_slowest_first():
    data = dataset(
        problem("a"),
        spaced("a-poly", "a", r"O^*(10^{n})", space="polynomial", params=("n",)),
        spaced("a-8", "a", r"O^*(8^{n})", r"O^*(2^{n})", params=("n",)),
        spaced("a-6", "a", r"O^*(6^{n})", r"O^*(4^{n})", params=("n",)),
        spaced("a-5", "a", r"O^*(5^{n})", params=("n",)),
    )
    kept = {r["id"]: r["space"] for r in rows(data, "a")}
    assert kept == {"a-poly": "poly", "a-8": r"O^*(2^{n})", "a-6": r"O^*(4^{n})", "a-5": "time"}
    assert frontier(data, "a") == [
        (r"O^*(10^{n})", "poly"), (r"O^*(8^{n})", r"O^*(2^{n})"),
        (r"O^*(6^{n})", r"O^*(4^{n})"), (r"O^*(5^{n})", "time"),
    ]


def test_a_result_beaten_in_both_time_and_space_is_dropped():
    data = dataset(
        problem("a"),
        spaced("a-slow", "a", r"O^*(8^{n})", r"O^*(4^{n})", params=("n",)),
        spaced("a-fast", "a", r"O^*(6^{n})", r"O^*(2^{n})", params=("n",)),
    )
    assert {r["id"] for r in rows(data, "a")} == {"a-fast"}


def test_a_space_bound_not_below_the_time_counts_as_the_time():
    data = dataset(
        problem("a"),
        spaced("a-alg", "a", r"O^*(2^{n})", r"O^*(2^{n})", params=("n",)),
    )
    (r,) = rows(data, "a")
    assert r["space"] == "time"


def test_no_frontier_from_polynomial_space_and_one_faster_algorithm():
    data = dataset(
        problem("a"),
        spaced("a-poly", "a", r"O^*(3^{n})", space="polynomial", params=("n",)),
        spaced("a-exp", "a", r"O^*(2^{n})", params=("n",)),
    )
    assert frontier(data, "a") == []


def test_space_bounds_transfer_along_reductions():
    data = dataset(
        problem("a"), problem("b"),
        spaced("b-alg", "b", r"O^*(4^{k})", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "2 k"}),
    )
    (r,) = [r for r in rows(data, "a") if r["origin"] == "derived"]
    assert r["shown"] == r"O^*(16^{k})" and r["space"] == r"O^*(4^{k})"


def test_space_bounds_follow_projections():
    data = dataset(
        problem("a", constraints=[r"k \le n"]),
        spaced("a-alg", "a", r"O^*(4^{k})", r"O^*(2^{k})"),
    )
    proj = [r for r in rows(data, "a") if r["origin"] == "derived"]
    assert [(r["shown"], r["space"]) for r in proj] == [(r"O^*(4^{n})", r"O^*(2^{n})")]


@pytest.mark.parametrize("space, bound, message", [
    ("polynomial", r"O^*(2^{n})", "only for exponential space"),
    ("exponential", r"O^*(2^{m})", "which the running time does not"),
])
def test_validator_checks_space_bounds(space, bound, message):
    raw = {folder: {} for folder in ENTITY_TYPES}
    raw["problems"]["a"] = problem("a")
    a = spaced("a-alg", "a", r"O^*(3^{n})", bound, space=space, params=("n",))
    raw["algorithms"]["a-alg"] = a
    _, issues = validate_raw(raw)
    assert any(message in str(i) for i in issues), [str(i) for i in issues]
