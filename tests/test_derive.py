"""Derivation engine tests, one group per section of docs/specs/rulebook.md.

All problems, algorithms and reductions here are fictional; every bound is arithmetic.
"""

from __future__ import annotations

import json

import pytest

from pear.__main__ import main
from pear.bounds import parse_bound
from pear.bounds.expr import variables
from pear.derive import MAX_STEPS, derive, to_json
from pear.schema import ENTITY_TYPES
from pear.validate import validate_raw

BASE = ("n", "m", "N")


# --- builders -----------------------------------------------------------------------


def problem(pid, params=("k",), versions=("decision",), shared=None, generalises=(), constraints=()):
    vers = {}
    for v in versions:
        if v == "decision":
            vers[v] = {"kind": "decision", "input": "An input.", "question": "Yes?"}
        else:
            vers[v] = {"kind": "optimisation", "input": "An input.", "goal": "Optimise."}
    for general, special in generalises:
        vers[general]["generalises"] = [special]
    out = {
        "id": pid,
        "name": pid,
        "category": "graph",
        "complexity": {"class": "NP-complete", "source": {"folklore": True, "note": "Fixture."}},
        "objects": {"n": "objects", "m": "relations", "N": "size"},
        "parameters": {p: {"meaning": p} for p in params},
        "versions": vers,
        "default_version": versions[0],
    }
    if shared:
        out["shared_bounds"] = [{"versions": list(shared), "because": "Fixture."}]
    if constraints:
        out["constraints"] = [{"constraint": c, "because": "Fixture."} for c in constraints]
    return out


def alg(aid, prob, bound, params=("k",), version="decision", randomized=False, space="polynomial",
        algebraic=False, constructive=True, quantum=False, conditional_on=(), formal=None, status="valid"):
    b = parse_bound(bound, BASE + tuple(params))
    out = {
        "id": aid,
        "problem": prob,
        "proved_for": version,
        "bound": {"as_stated": bound, "notation": b.notation or "O", "parameters": sorted(variables(b.expr))},
        "properties": {
            "randomized": randomized,
            "space": {"class": space},
            "algebraic": algebraic,
            "fast_matrix_multiplication": False,
            "constructive": constructive,
            "quantum": quantum,
        },
        "conditional_on": list(conditional_on),
        "source": {"folklore": True, "note": "Fixture."},
        "status": status,
    }
    if formal:
        out["formal"] = formal
    return out


def red(rid, frm, to, pmap, type="polytime-deterministic", calls=1, time="O(n + m)", frm_v="decision",
        to_v="decision", formal=None, status="valid", properties=None, call_sizes=None):
    out = {
        "id": rid,
        "from": {"problem": frm, "version": frm_v},
        "to": {"problem": to, "version": to_v},
        "type": type,
        "calls": calls,
        "time": time,
        "parameter_map": pmap,
        "source": {"folklore": True, "note": "Fixture."},
        "status": status,
    }
    if formal:
        out["formal"] = formal
    if properties:
        out["properties"] = properties
    if call_sizes:
        out["call_sizes"] = call_sizes
    return out


def hyp(hid, status="open", implies=()):
    out = {"id": hid, "name": hid, "statement": "Fixture.", "status": status, "implies": list(implies)}
    if status != "open":
        out["status_sources"] = [{"url": "https://example.org/fixture", "date": "2026-01-01"}]
    return out


def dataset(*entries):
    raw = {folder: {} for folder in ENTITY_TYPES}
    for e in entries:
        folder = (
            "problems" if "objects" in e else
            "algorithms" if "proved_for" in e else
            "reductions" if "parameter_map" in e else
            "hypotheses"
        )
        raw[folder][e["id"]] = e
    data, issues = validate_raw(raw)
    assert [str(i) for i in issues] == []
    return data


def rows(data, pid, node="decision"):
    out = to_json(data, derive(data))
    return out["problems"].get(pid, {}).get(node, [])


def derived(data, pid, node="decision"):
    return [r for r in rows(data, pid, node) if r["origin"] == "derived"]


# --- §2 many-one reductions --------------------------------------------------------------


def test_many_one_substitutes_and_folds():
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(1.2^{k})"),
        red("a-to-b", "a", "b", {"k": "2k"}),
    )
    (r,) = derived(data, "a")
    assert r["exact"] == r"O^*(n + m + 1.2^{2 k})"  # T_R kept in the exact form (R7)
    assert r["shown"] == r"O^*(1.44^{k})"  # the plan's example
    assert r["steps"] == 1 and r["chain"][0]["parameter_map"] == {"k": "2k"}


def test_transfer_needs_every_variable_mapped():
    data = dataset(problem("a"), problem("b"), alg("b-alg", "b", r"O^*(1.2^{k})"), red("a-to-b", "a", "b", {"n": "n"}))
    assert derived(data, "a") == []
    assert any("does not cover ['k']" in line for line in derive(data).log)


def test_polynomial_factors_transfer_in_ostar_form():
    # proposal in the implementation notes: n_B only occurs in a polynomial factor
    data = dataset(problem("a"), problem("b"), alg("b-alg", "b", r"O(1.2^{k} n^{3})"), red("a-to-b", "a", "b", {"k": "k"}))
    (r,) = derived(data, "a")
    assert r["shown"] == r"O^*(1.2^{k})"


def test_non_monotone_bounds_do_not_transfer():
    data = dataset(
        problem("a"), problem("b", constraints=[r"k \le n"]),
        alg("b-alg", "b", r"O^*(1.5^{n-k})"), red("a-to-b", "a", "b", {"n": "n", "k": "k"}),
    )
    assert derived(data, "a") == []
    assert any("monotone" in line for line in derive(data).log)


# --- §3 Turing reductions, §4 randomness -------------------------------------------------------


def test_turing_multiplies_by_calls_and_flags_sizes():
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}, calls="n"),
    )
    (r,) = derived(data, "a")
    assert r["exact"] == r"O^*(n + m + n \cdot 2^{k})"
    assert "adaptive-sizes" in r["flags"]


def test_call_sizes_from_the_paper_remove_the_flag():
    data = dataset(
        problem("a"), problem("b"), alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}, calls="n", call_sizes="Fixture analysis."),
    )
    (r,) = derived(data, "a")
    assert "adaptive-sizes" not in r["flags"]


def test_randomized_calls_are_amplified():
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(2^{k})", randomized=True),
        red("a-to-b", "a", "b", {"k": "k"}, calls="n"),
    )
    (r,) = derived(data, "a")
    assert r["exact"] == r"O^*(n + m + n \log n \cdot 2^{k})"
    assert r["properties"]["deterministic"] is False


def test_randomized_reduction_makes_bound_randomized():
    data = dataset(
        problem("a"), problem("b"), alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}, type="polytime-randomized"),
    )
    (r,) = derived(data, "a")
    assert r["properties"]["deterministic"] is False


# --- §5 SERF ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bound", "transfers"),
    [
        (r"O(2^{\delta k}) \text{ for every } \delta > 0", True),
        (r"2^{o(k)}", True),
        (r"O^*(2^{\sqrt{k}})", True),
        (r"O^*(1.01^{k})", False),  # concrete bases do not transfer (R3)
    ],
)
def test_serf_transfers_only_subexponential(bound, transfers):
    data = dataset(
        problem("a", params=("p",)), problem("b"),
        alg("b-alg", "b", bound),
        red("a-to-b", "a", "b", {"k": "p"}, type="serf", time="O^*(2^{n})"),
    )
    got = derived(data, "a")
    if transfers:
        (r,) = got
        assert r["shown"] == r"O^*(2^{\delta p}) \text{ for every } \delta > 0"
        assert r["properties"]["polynomial_space"] is False  # SERF space unknown
    else:
        assert got == []


# --- §6 versions ---------------------------------------------------------------------------------


def test_shared_versions_share_bounds_without_a_step():
    data = dataset(
        problem("a", versions=("decision", "optimisation"), shared=("decision", "optimisation")),
        alg("a-alg", "a", r"O^*(2^{k})", version="optimisation"),
    )
    (r,) = rows(data, "a", "decision+optimisation")
    assert r["origin"] == "direct"


def test_special_case_is_a_counted_step():
    data = dataset(
        problem("a", versions=("optimisation", "weighted"), generalises=[("weighted", "optimisation")]),
        alg("a-alg", "a", r"O^*(2^{k})", version="weighted"),
    )
    (r,) = rows(data, "a", "optimisation")
    assert r["origin"] == "derived" and r["steps"] == 1 and r["chain"][0]["kind"] == "special-case"
    assert rows(data, "a", "weighted")[0]["origin"] == "direct"


def test_bounds_do_not_flow_from_special_to_general():
    data = dataset(
        problem("a", versions=("optimisation", "weighted"), generalises=[("weighted", "optimisation")]),
        alg("a-alg", "a", r"O^*(2^{k})", version="optimisation"),
    )
    assert rows(data, "a", "weighted") == []


# --- §7 composite parameters and projection ------------------------------------------------------


def test_composite_parameter_is_kept_and_projected():
    data = dataset(
        problem("a", constraints=[r"k \le n"]), problem("b"),
        alg("b-alg", "b", r"O^*(1.5^{k})"),
        red("a-to-b", "a", "b", {"k": "n - k"}),
    )
    shown = {r["shown"]: r for r in derived(data, "a")}
    assert set(shown) == {r"O^*(1.5^{n - k})", r"O^*(1.5^{n})"}
    assert shown[r"O^*(1.5^{n})"]["chain"][-1]["kind"] == "projection"
    assert shown[r"O^*(1.5^{n})"]["steps"] == 1  # projections are not counted


def test_projection_through_constraints():
    data = dataset(
        problem("a", constraints=[r"k \le n"]), problem("b"),
        alg("b-alg", "b", r"O^*(1.5^{k})"),
        red("a-to-b", "a", "b", {"k": "k + n"}),
    )
    shown = {r["shown"] for r in derived(data, "a")}
    assert shown == {r"O^*(1.5^{k + n})", r"O^*(2.25^{n})"}


# --- §8 property inheritance -------------------------------------------------------------------------


def test_properties_are_inherited():
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(2^{k})", algebraic=True, quantum=False,
            formal={"status": "proved", "prover": "lean", "link": "https://example.org/fixture"}),
        red("a-to-b", "a", "b", {"k": "k"}, properties={"constructive": False},
            formal={"status": "statement", "prover": "lean", "link": "https://example.org/fixture"}),
    )
    (r,) = derived(data, "a")
    p = r["properties"]
    assert p["algebraic"] is True and p["constructive"] is False
    assert p["formal"] == "statement" and p["lean_verified"] is False


def test_lean_verified_needs_every_step_proved_in_lean():
    proved = {"status": "proved", "prover": "lean", "link": "https://example.org/fixture"}
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(2^{k})", formal=proved),
        red("a-to-b", "a", "b", {"k": "k"}, formal=proved),
    )
    (r,) = derived(data, "a")
    assert r["properties"]["lean_verified"] is True


def test_hypotheses_reduced_to_the_weakest():
    data = dataset(
        problem("a"), hyp("h-strong", implies=["h-weak"]), hyp("h-weak"),
        alg("a-alg", "a", r"O^*(2^{k})", conditional_on=["h-strong", "h-weak"]),
    )
    (r,) = rows(data, "a")
    assert r["conditional_on"] == ["h-strong"]


def test_refuted_hypotheses_excluded_and_claimed_flagged():
    data = dataset(
        problem("a"), problem("b"), hyp("h-gone", status="refuted"), hyp("h-doubt", status="claimed-refuted"),
        alg("a-alg", "a", r"O^*(2^{k})", conditional_on=["h-gone"]),
        alg("b-alg", "b", r"O^*(2^{k})", conditional_on=["h-doubt"]),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    (r,) = rows(data, "a")
    assert r["origin"] == "derived" and "claimed-refuted-hypothesis" in r["flags"]


@pytest.mark.parametrize("what", ["algorithm", "reduction"])
def test_results_under_review_are_not_used(what):
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(2^{k})", status="flagged" if what == "algorithm" else "valid"),
        red("a-to-b", "a", "b", {"k": "k"}, status="flagged" if what == "reduction" else "valid"),
    )
    assert derived(data, "a") == []


# --- §9 chaining and keeping ---------------------------------------------------------------------------


def test_slower_deterministic_bound_is_kept_next_to_faster_randomized():
    data = dataset(
        problem("a"), problem("b"),
        alg("b-fast", "b", r"O^*(1.5^{k})", randomized=True),
        alg("b-det", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    assert {r["shown"] for r in derived(data, "a")} == {r"O^*(1.5^{k})", r"O^*(2^{k})"}


def test_worse_derived_bounds_are_dropped_but_direct_ones_stay():
    data = dataset(
        problem("a"), problem("b"),
        alg("a-slow", "a", r"O^*(3^{k})"),
        alg("a-fast", "a", r"O^*(1.1^{k})"),
        alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert set(got) == {"a-slow", "a-fast"}  # the derived 2^k is beaten by a-fast
    assert "a-fast" in got["a-slow"]["beaten_by"]


def test_bounds_compete_within_their_parameters():
    # 1.2^k beats 1.5^n under k <= n, but 1.5^n is still the best bound "by n"
    data = dataset(
        problem("a", constraints=[r"k \le n"]), problem("b"),
        alg("a-alg", "a", r"O^*(1.2^{k})"),
        alg("b-alg", "b", r"O^*(1.5^{k})"),
        red("a-to-b", "a", "b", {"k": "n"}),
    )
    got = {r["shown"]: r for r in rows(data, "a")}
    assert set(got) == {r"O^*(1.2^{k})", r"O^*(1.5^{n})"}
    assert got[r"O^*(1.5^{n})"]["beaten_by"] == ["a-alg"]  # for the overall best, in the browser


def test_derived_bound_beats_but_does_not_hide_direct_bound():
    data = dataset(
        problem("a"), problem("b"),
        alg("a-slow", "a", r"O^*(3^{k})"),
        alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert set(got) == {"a-slow", "b-alg|a-to-b"}
    assert got["a-slow"]["beaten_by"] == ["b-alg|a-to-b"]


def test_equal_bounds_by_two_routes_are_kept_once():
    data = dataset(
        problem("a"), problem("b"), problem("c"),
        alg("c-alg", "c", r"O^*(2^{k})"),
        red("a-to-c", "a", "c", {"k": "k"}),
        red("a-to-b", "a", "b", {"k": "k"}),
        red("b-to-c", "b", "c", {"k": "k"}),
    )
    (r,) = derived(data, "a")
    assert r["steps"] == 1  # the shorter chain wins


def test_cycles_terminate():
    data = dataset(
        problem("a"), problem("b"), alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}), red("b-to-a", "b", "a", {"k": "k"}),
    )
    assert len(derived(data, "a")) == 1 and derived(data, "b") == []


def chain_of(length):
    names = [f"p{i}" for i in range(length + 1)]
    entries = [problem(p) for p in names]
    entries.append(alg("last-alg", names[-1], r"O^*(2^{k})"))
    entries += [red(f"{a}-to-{b}", a, b, {"k": "k"}) for a, b in zip(names, names[1:])]
    return dataset(*entries), names


def test_long_chains_are_labelled():
    data, names = chain_of(4)
    (r,) = derived(data, names[0])
    assert r["steps"] == 4 and "long-chain" in r["flags"]
    (r3,) = derived(data, names[1])
    assert "long-chain" not in r3["flags"]


def test_chains_stop_after_the_limit():
    data, names = chain_of(MAX_STEPS + 1)
    assert derived(data, names[0]) == []
    assert len(derived(data, names[1])) == 1
    assert any("not followed" in line for line in derive(data).log)


def test_cli_writes_json(tmp_path):
    out = tmp_path / "derived.json"
    assert main(["derive", "tests/fixtures/valid", "--out", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["rulebook_version"] == 1
    (r,) = payload["problems"]["problem-b"]["decision"]
    assert r["origin"] == "derived" and r["chain"][0]["id"] == "problem-b--to--problem-a"
