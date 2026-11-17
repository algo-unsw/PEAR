"""Derivation engine tests, one group per section of docs/specs/rulebook.md.

All problems, algorithms and reductions here are fictional; every bound is arithmetic.
"""

from __future__ import annotations

import json

import pytest

from pear.__main__ import main
from pear.bounds import parse_bound
from pear.bounds.expr import variables
from pear.derive import derive, to_json
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


def paper(pid, year):
    return {
        "id": pid,
        "title": "A fictional paper",
        "authors": ["A. Author"],
        "versions": {"arxiv-v1": {"kind": "preprint", "arxiv": "0000.00000", "year": year, "open_access": True}},
    }


def cited(pid):
    return {"paper": pid, "statements": {"arxiv-v1": {"statement": "Theorem 1"}}}


def alg(aid, prob, bound, params=("k",), version="decision", randomized=False, space="polynomial",
        algebraic=False, constructive=True, quantum=False, conditional_on=(), formal=None, status="valid",
        paper=None):
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
        "source": cited(paper) if paper else {"folklore": True, "note": "Fixture."},
        "status": status,
    }
    if formal:
        out["formal"] = formal
    return out


def red(rid, frm, to, pmap, type="polytime-deterministic", calls=1, time="O(n + m)", frm_v="decision",
        to_v="decision", formal=None, status="valid", properties=None, call_sizes=None, paper=None, variants=()):
    out = {
        "id": rid,
        "from": {"problem": frm, "version": frm_v},
        "to": {"problem": to, "version": to_v},
        "type": type,
        "calls": calls,
        "time": time,
        "parameter_map": pmap,
        "source": cited(paper) if paper else {"folklore": True, "note": "Fixture."},
        "status": status,
    }
    if formal:
        out["formal"] = formal
    if properties:
        out["properties"] = properties
    if call_sizes:
        out["call_sizes"] = call_sizes
    if variants:
        out["variants"] = list(variants)
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
            "papers" if "authors" in e else
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
    # rulebook §2 (D2): n_B only occurs in a polynomial factor
    data = dataset(problem("a"), problem("b"), alg("b-alg", "b", r"O(1.2^{k} n^{3})"), red("a-to-b", "a", "b", {"k": "k"}))
    (r,) = derived(data, "a")
    assert r["shown"] == r"O^*(1.2^{k})"


def test_non_monotone_bounds_do_not_transfer_but_their_projections_do():
    data = dataset(
        problem("a"), problem("b", constraints=[r"k \le n"]),
        alg("b-alg", "b", r"O^*(1.5^{n-k})"), red("a-to-b", "a", "b", {"n": "n", "k": "k"}),
    )
    assert any("monotone" in line for line in derive(data).log)
    (r,) = derived(data, "a")
    assert r["shown"] == r"O^*(1.5^{n})"
    assert [s["kind"] for s in r["chain"]] == ["projection", "reduction"]


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


def superseded(data, pid, node="decision"):
    out = to_json(data, derive(data))
    return {r["id"]: r for r in out["superseded"].get(pid, {}).get(node, [])}


def test_beaten_results_leave_details_and_direct_ones_go_to_history():
    # rulebook version 3 (10 November 2026): beaten direct results leave the Details list
    data = dataset(
        problem("a"), problem("b"),
        alg("a-slow", "a", r"O^*(3^{k})"),
        alg("a-fast", "a", r"O^*(1.1^{k})"),
        alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    assert {r["id"] for r in rows(data, "a")} == {"a-fast"}  # the derived 2^k is dropped too
    old = superseded(data, "a")
    assert set(old) == {"a-slow"}  # derived results are not kept for the history
    assert old["a-slow"]["superseded_by"] == ["a-fast"]
    assert old["a-slow"]["shown"] == r"O^*(3^{k})"


def test_beaten_direct_result_is_dropped_whatever_the_insertion_order():
    # a-1 is inserted before its better rival, z-2 after (ids are sorted)
    data = dataset(
        problem("a"),
        alg("a-1-slow", "a", r"O^*(3^{k})"),
        alg("a-2-fast", "a", r"O^*(1.1^{k})"),
        alg("z-3-slow", "a", r"O^*(2^{k})"),
    )
    assert {r["id"] for r in rows(data, "a")} == {"a-2-fast"}
    assert set(superseded(data, "a")) == {"a-1-slow", "z-3-slow"}


def test_direct_result_best_under_some_filter_stays():
    # the faster bound is randomized: the deterministic one is best when "deterministic" is ticked
    data = dataset(
        problem("a"),
        alg("a-det", "a", r"O^*(1.3^{k})"),
        alg("a-rand", "a", r"O^*(1.2^{k})", randomized=True),
        alg("a-exp", "a", r"O^*(1.1^{k})", space="exponential"),
    )
    assert {r["id"] for r in rows(data, "a")} == {"a-det", "a-rand", "a-exp"}
    assert superseded(data, "a") == {}


def test_derived_bound_never_drops_a_direct_one():
    # "include derived" can be unticked, so a direct result beaten only by derived ones stays
    data = dataset(
        problem("a"), problem("b"),
        alg("a-alg", "a", r"O^*(3^{k})"),
        alg("b-alg", "b", r"O^*(2^{k})"),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert "a-alg" in got and len(derived(data, "a")) == 1
    assert got["a-alg"]["beaten_by"] == [derived(data, "a")[0]["id"]]


def test_bounds_compete_within_their_parameters():
    # 1.2^k projects to 1.2^n (k <= n), which beats the derived 1.5^n "by n"
    data = dataset(
        problem("a", constraints=[r"k \le n"]), problem("b"),
        alg("a-alg", "a", r"O^*(1.2^{k})"),
        alg("b-alg", "b", r"O^*(1.5^{k})"),
        red("a-to-b", "a", "b", {"k": "n"}),
    )
    got = {r["shown"]: r for r in rows(data, "a")}
    assert set(got) == {r"O^*(1.2^{k})", r"O^*(1.2^{n})"}
    assert got[r"O^*(1.2^{n})"]["beaten_by"] == ["a-alg"]  # for the overall best, in the browser
    assert [g["shown"] for g in overview(data, "a")] == [r"O^*(1.2^{k})"]


def test_direct_bounds_are_projected():
    data = dataset(problem("a", constraints=[r"k \le n", r"m \le n^{2}"]), alg("a-alg", "a", r"O^*(1.1^{m})"))
    got = {r["shown"]: r for r in rows(data, "a")}
    assert set(got) == {r"O^*(1.1^{m})", r"O^*(1.1^{n^{2}})"}
    assert got[r"O^*(1.1^{n^{2}})"]["origin"] == "derived" and got[r"O^*(1.1^{n^{2}})"]["steps"] == 0


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


def _entries(data):
    for folder, entries in data.entries.items():
        for e in entries.values():
            yield e.model_dump(mode="json", by_alias=True, exclude_none=True)


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


def test_long_chains_are_followed_while_they_improve():
    data, names = chain_of(12)
    (r,) = derived(data, names[0])
    assert r["steps"] == 12 and "long-chain" in r["flags"]


def test_chains_stop_when_nothing_improves():
    # a direct bound at the start of the chain beats everything the chain could bring
    data, names = chain_of(5)
    raw_alg = alg("first-alg", names[0], r"O^*(1.1^{k})")
    data2 = dataset(*(list(_entries(data)) + [raw_alg]))
    assert derived(data2, names[0]) == []


def test_cli_writes_json(tmp_path):
    out = tmp_path / "derived.json"
    assert main(["derive", "tests/fixtures/valid", "--out", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["rulebook_version"] == 3
    chains = [[s["id"] for s in r["chain"]] for r in payload["problems"]["problem-b"]["decision"]]
    assert ["problem-b--to--problem-a"] in chains


# --- Overview tab: best non-quantum bound by any means; earliest cited ----------------------------


def overview(data, pid, node="decision"):
    out = to_json(data, derive(data))
    by_id = {r["id"]: r for r in out["problems"][pid][node]}
    return [
        {"shown": by_id[g["cite"][0]]["shown"], "cite": sorted(g["cite"]), "members": sorted(g["members"]), "year": g["year"]}
        for g in out["overview"][pid][node]
    ]


def test_overview_is_best_by_any_means_without_quantum():
    data = dataset(
        problem("a"), problem("b"),
        alg("a-direct", "a", r"O^*(3^{k})"),
        alg("a-quantum", "a", r"O^*(1.1^{k})", quantum=True),
        alg("b-alg", "b", r"O^*(2^{k})", randomized=True, space="exponential"),
        red("a-to-b", "a", "b", {"k": "k"}),
    )
    (g,) = overview(data, "a")
    assert g["shown"] == r"O^*(2^{k})" and g["cite"] == ["b-alg|a-to-b"]


def test_overview_keeps_incomparable_bounds():
    data = dataset(
        problem("a"), alg("a-k", "a", r"O^*(2^{k})"), alg("a-n", "a", r"O^*(1.1^{n})"),
    )
    assert sorted(g["shown"] for g in overview(data, "a")) == [r"O^*(1.1^{n})", r"O^*(2^{k})"]


def test_equal_in_ostar_cites_the_earlier():
    # the 2010 bound is more precise, but equal in O*: the 2005 one is cited
    data = dataset(
        problem("a"), paper("p-2005", 2005), paper("p-2010", 2010),
        alg("a-2005", "a", r"O^*(1.5^{k})", paper="p-2005"),
        alg("a-2010", "a", r"O(1.5^{k} k)", paper="p-2010"),
    )
    (g,) = overview(data, "a")
    assert g["cite"] == ["a-2005"] and g["members"] == ["a-2005", "a-2010"] and g["year"] == 2005


def test_same_year_cites_all():
    data = dataset(
        problem("a"), paper("p-x", 2005), paper("p-y", 2005),
        alg("a-x", "a", r"O^*(1.5^{k})", paper="p-x"),
        alg("a-y", "a", r"O^*(1.5^{k})", paper="p-y"),
    )
    (g,) = overview(data, "a")
    assert g["cite"] == ["a-x", "a-y"]


def test_derived_year_is_the_latest_ingredient_and_earlier_derivations_are_cited():
    data = dataset(
        problem("a"), problem("b"), paper("p-alg", 1990), paper("p-red", 1995), paper("p-direct", 2005),
        alg("b-alg", "b", r"O^*(1.5^{k})", paper="p-alg"),
        red("a-to-b", "a", "b", {"k": "k"}, paper="p-red"),
        alg("a-direct", "a", r"O(1.5^{k} k)", paper="p-direct"),
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert got["b-alg|a-to-b"]["year"] == 1995 and got["b-alg|a-to-b"]["papers"] == ["p-alg", "p-red"]
    (g,) = overview(data, "a")
    assert g["cite"] == ["b-alg|a-to-b"] and g["year"] == 1995


def test_later_equal_derivation_is_dropped():
    data = dataset(
        problem("a"), problem("b"), paper("p-alg", 2010), paper("p-direct", 2005),
        alg("b-alg", "b", r"O^*(1.5^{k})", paper="p-alg"),
        red("a-to-b", "a", "b", {"k": "k"}),
        alg("a-direct", "a", r"O^*(1.5^{k})", paper="p-direct"),
    )
    assert [r["id"] for r in rows(data, "a")] == ["a-direct"]


# --- reduction variants ---------------------------------------------------------------------------


def two_parameter_problems(*variants, extra_paper=None):
    return dataset(
        problem("a", params=("k", "w")), problem("b", params=("k", "w")),
        *([paper(*extra_paper)] if extra_paper else []),
        paper("p-red", 2000),
        alg("b-k", "b", r"O^*(2^{k})", params=("k", "w")),
        alg("b-w", "b", r"O^*(3^{w})", params=("k", "w")),
        red("a-to-b", "a", "b", {"k": "k"}, paper="p-red", variants=variants),
    )


def test_variant_gives_a_result_for_another_parameter():
    data = two_parameter_problems(
        {"id": "by-w", "note": "The same construction keeps the width.", "parameter_map": {"w": "w"},
         "source": {"folklore": True, "note": "Fixture."}},
    )
    got = {r["shown"]: r for r in derived(data, "a")}
    assert set(got) == {r"O^*(2^{k})", r"O^*(3^{w})"}
    step = got[r"O^*(3^{w})"]["chain"][0]
    assert step["id"] == "a-to-b~by-w" and step["note"] == "The same construction keeps the width."


def test_site_written_variant_needs_approval():
    variant = {"id": "kernel-first", "note": "Run a kernelization for w first.", "parameter_map": {"w": "w"}}
    data = two_parameter_problems(variant)
    assert [r["shown"] for r in derived(data, "a")] == [r"O^*(2^{k})"]
    assert any("awaits approval" in line for line in derive(data).log)
    approved = dict(variant, review={"approved_by": "Serge Gaspers", "date": "2026-11-07"})
    data = two_parameter_problems(approved)
    by_w = [r for r in derived(data, "a") if r["shown"] == r"O^*(3^{w})"]
    assert len(by_w) == 1 and "site-written-variant" in by_w[0]["flags"]


def test_variant_paper_counts_for_year_and_citation():
    data = two_parameter_problems(
        {"id": "by-w", "note": "Variant from a later paper.", "parameter_map": {"w": "w"}, "source": cited("p-var")},
        extra_paper=("p-var", 2012),
    )
    (r,) = [r for r in derived(data, "a") if r["shown"] == r"O^*(3^{w})"]
    assert r["year"] == 2012 and r["papers"] == ["p-red", "p-var"]


def test_variant_between_other_problems():
    # the same construction also reduces between the weighted versions
    data = dataset(
        problem("a", versions=("optimisation", "weighted")), problem("b", versions=("optimisation", "weighted")),
        alg("b-weighted", "b", r"O^*(2^{k})", version="weighted"),
        red("a-to-b", "a", "b", {"k": "k"}, frm_v="optimisation", to_v="optimisation", variants=[
            {"id": "weighted", "note": "The same construction keeps the weights.",
             "from": {"problem": "a", "version": "weighted"}, "to": {"problem": "b", "version": "weighted"},
             "parameter_map": {"k": "k"}, "source": {"folklore": True, "note": "Fixture."}},
        ]),
    )
    (r,) = derived(data, "a", "weighted")
    assert r["chain"][0]["id"] == "a-to-b~weighted"
    assert derived(data, "a", "optimisation") == []


def test_year_comes_from_the_cited_version():
    # the result only appears in v2 of the paper
    p = paper("p-versions", 2020)
    p["versions"]["arxiv-v2"] = {"kind": "preprint", "arxiv": "0000.00001", "year": 2022, "open_access": True}
    data = dataset(
        problem("a"), p,
        alg("a-alg", "a", r"O^*(2^{k})", paper=None) | {"source": {"paper": "p-versions", "statements": {"arxiv-v2": {"statement": "Theorem 3"}}}},
    )
    (r,) = rows(data, "a")
    assert r["year"] == 2022


def test_unverified_results_stay_out_of_the_overview():
    unverified = paper("p-report", 2001) | {"unverified": True}
    data = dataset(
        problem("a"), problem("b"), unverified, paper("p-ok", 2010),
        alg("a-report", "a", r"O^*(1.1^{k})", paper="p-report"),
        alg("a-ok", "a", r"O^*(1.5^{k})", paper="p-ok"),
        red("b-to-a", "b", "a", {"k": "k"}),
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert set(got) == {"a-report", "a-ok"} and "unverified" in got["a-report"]["flags"]
    assert [g["cite"] for g in overview(data, "a")] == [["a-ok"]]
    # derived bounds inherit the tag, and a verified bound is never dropped for an unverified one
    b = {r["id"]: r for r in rows(data, "b")}
    assert set(b) == {"a-report|b-to-a", "a-ok|b-to-a"}
    assert [g["cite"] for g in overview(data, "b")] == [["a-ok|b-to-a"]]


def test_given_tree_decomposition_is_carried_along():
    data = dataset(
        problem("a", params=("k", "tw")), problem("b", params=("k", "tw")),
        alg("b-alg", "b", r"O(2^{tw} n)", params=("k", "tw")) | {"given": ["tree-decomposition"]},
        red("a-to-b", "a", "b", {"tw": "tw", "n": "n"}),
    )
    (r,) = derived(data, "a")
    assert "given-tree-decomposition" in r["flags"]


def test_unverified_result_is_optional_in_the_overview():
    # decided 12 November 2026: readers can include unverified results in the Overview
    data = dataset(
        problem("a"), paper("p-report", 2026) | {"unverified": True}, paper("p-ok", 2010),
        alg("a-report", "a", r"O^*(1.1^{k})", paper="p-report"),
        alg("a-ok", "a", r"O^*(1.5^{k})", paper="p-ok"),
        alg("a-worse", "a", r"O^*(1.6^{k})", paper="p-report"),
    )
    out = to_json(data, derive(data))
    assert [e["cite"] for e in out["overview"]["a"]["decision"]] == [["a-ok"]]
    # a-worse is beaten by a verified result, so including it would change nothing
    assert out["overview_optional"]["a"]["decision"] == [{"id": "a-report", "beats": ["a-ok"], "year": 2026}]


# --- uses (decided 13 November 2026) -----------------------------------------------------------------


def test_uses_makes_a_result_unverified_when_a_used_result_is():
    data = dataset(
        problem("a"), problem("sat"), paper("p-ok", 2010), paper("p-report", 2026) | {"unverified": True},
        alg("sat-alg", "sat", r"O^*(1.1^{k})", paper="p-report"),
        alg("a-alg", "a", r"O^*(1.2^{k})", paper="p-ok") | {"uses": ["sat-alg"]},
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert "unverified" in got["a-alg"]["flags"]


def test_uses_a_verified_result_keeps_the_result_verified():
    data = dataset(
        problem("a"), problem("sat"), paper("p-ok", 2010),
        alg("sat-alg", "sat", r"O^*(1.1^{k})", paper="p-ok"),
        alg("a-alg", "a", r"O^*(1.2^{k})", paper="p-ok") | {"uses": ["sat-alg"]},
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert "unverified" not in got["a-alg"]["flags"]


@pytest.mark.parametrize("status", ["flagged", "unrepaired", "broken"])
def test_uses_a_flagged_result_keeps_the_result_out(status):
    data = dataset(
        problem("a"), problem("sat"), problem("c"), paper("p-ok", 2010),
        alg("sat-alg", "sat", r"O^*(1.1^{k})", paper="p-ok", status=status),
        alg("c-alg", "c", r"O^*(1.15^{k})", paper="p-ok") | {"uses": ["sat-alg"]},
        alg("a-alg", "a", r"O^*(1.2^{k})", paper="p-ok") | {"uses": ["c-alg"]},  # transitively
    )
    assert derived(data, "a") == [] and derived(data, "c") == []


def test_uses_carries_the_hypotheses_of_used_results():
    data = dataset(
        problem("a"), problem("sat"), paper("p-ok", 2010), hyp("h"),
        alg("sat-alg", "sat", r"O^*(1.1^{k})", paper="p-ok", conditional_on=["h"]),
        alg("a-alg", "a", r"O^*(1.2^{k})", paper="p-ok") | {"uses": ["sat-alg"]},
    )
    got = {r["id"]: r for r in rows(data, "a")}
    assert got["a-alg"]["conditional_on"] == ["h"]
