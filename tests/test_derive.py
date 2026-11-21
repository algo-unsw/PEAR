"""Derivation engine tests, one group per section of docs/specs/rulebook.md.

All problems, algorithms and reductions here are fictional; every bound is arithmetic.
"""

from __future__ import annotations

import json

import pytest

from pear.__main__ import main
from pear.bounds import parse_bound
from pear.bounds.expr import render_bound, variables
from pear.derive import Engine, derive, to_json
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
        "versions": {"arxiv-v1": {"kind": "preprint", "arxiv": "0000.00000", "year": year, "open_access": True},
                     # a peer-reviewed version: a paper with preprints only counts as unrefereed
                     "journal": {"kind": "journal", "venue": "A Journal", "year": year, "open_access": False}},
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
            "techniques" if "applies_to" in e else
            "constants" if "symbol" in e else
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


def test_substitution_uses_a_monotone_upper_bound():
    # A1, A2 (20 November 2026): the complement map m -> n(n - 1)/2 - m makes b's bound decrease
    # in m, a decrease its growth estimate hides; substituting the upper bound m -> n(n - 1)/2
    # into it would give the lower bound 0, so the subtracted term is dropped first.
    data = dataset(
        problem("a"), problem("b"), problem("c"),
        alg("c-alg", "c", r"O(1.1^{k} + m)"),
        red("b-to-c", "b", "c", {"n": "n", "m": "n (n - 1) / 2 - m", "k": "k"}, time="O(n^{2})"),
        red("a-to-b", "a", "b", {"n": "n", "m": "n (n - 1) / 2", "k": "k"}, time="O(n^{2})"),
    )
    (b,) = derived(data, "b")
    assert "- m" in b["exact"]  # b's own bound keeps the exact form
    (r,) = [x for x in derive(data).results[("a", "decision")] if x.derived]
    assert render_bound(r.bound) == r"O(n^{2} + n^{2} + 1.1^{k} + n (n - 1)/2)"
    (row,) = derived(data, "a")
    assert row["exact"] == r"O(n^{2} + 1.1^{k})"  # constants and repeated terms hidden (bounds §4)
    assert row["shown"] == r"O^*(1.1^{k})"


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
    # listed under the composite parameter n - k, not under k and n (20 November 2026)
    assert shown[r"O^*(1.5^{n - k})"]["parameters"] == ["n - k"]
    assert shown[r"O^*(1.5^{n - k})"]["composite"] is True
    assert shown[r"O^*(1.5^{n})"]["parameters"] == ["n"]
    assert shown[r"O^*(1.5^{n})"]["chain"][-1]["kind"] == "projection"
    assert shown[r"O^*(1.5^{n})"]["steps"] == 1  # projections are not counted


def test_composite_parameter_competes_through_its_variables():
    # a bound by m - k is not dropped by a bound in k or m alone that does not beat it,
    # and is dropped by one in k and m that does (D1 compares variables)
    data = dataset(
        problem("a", constraints=[r"k \le m"]), problem("b"),
        alg("a-k", "a", r"O^*(1.1^{k})"),
        alg("b-alg", "b", r"O^*(1.5^{k})"),
        red("a-to-b", "a", "b", {"k": "m - k"}),
    )
    assert r"O^*(1.5^{m - k})" in {r["shown"] for r in rows(data, "a")}
    data = dataset(
        problem("a", constraints=[r"k \le m"]), problem("b"),
        alg("a-km", "a", r"O^*(1.1^{m - k})"),
        alg("b-alg", "b", r"O^*(1.5^{k})"),
        red("a-to-b", "a", "b", {"k": "m - k"}),
    )
    assert r"O^*(1.5^{m - k})" not in {r["shown"] for r in rows(data, "a")}


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


@pytest.mark.parametrize("what", ["algorithm", "reduction"])
def test_easily_fixable_results_count_with_a_site_written_fix(what):
    # rulebook A3, version 5 (21 November 2026): PLAN's "easily fixable" grade counts, marked as
    # relying on a site-written fix
    data = dataset(
        problem("a"), problem("b"),
        alg("b-alg", "b", r"O^*(2^{k})", status="easily-fixable" if what == "algorithm" else "valid"),
        red("a-to-b", "a", "b", {"k": "k"}, status="easily-fixable" if what == "reduction" else "valid"),
    )
    (r,) = derived(data, "a")
    assert "site-written-fix" in r["flags"]
    (b,) = rows(data, "b")
    assert ("site-written-fix" in b["flags"]) == (what == "algorithm")


def _counting(pid):
    out = problem(pid, params=(), versions=("decision",))
    out["versions"] = {"counting": {"kind": "counting", "input": "An input.", "goal": "Count."}}
    out["default_version"] = "counting"
    return out


def test_counting_reduction_transfers_between_counting_versions():
    # rulebook §2a (version 5, approved 21 November 2026)
    data = dataset(
        _counting("sharp-a"), _counting("sharp-b"),
        alg("b-alg", "sharp-b", r"O^*(1.5^{n + m})", params=(), version="counting"),
        red("a-to-b", "sharp-a", "sharp-b", {"n": "n", "m": "n"}, type="polytime-counting",
            frm_v="counting", to_v="counting"),
    )
    (r,) = derived(data, "sharp-a", "counting")
    assert r["shown"] == r"O^*(2.25^{n})"
    assert r["chain"][0]["type"] == "polytime-counting"


def test_counting_reduction_needs_counting_versions():
    raw = {folder: {} for folder in ENTITY_TYPES}
    for e in (_counting("sharp-a"), problem("b"),
              red("a-to-b", "sharp-a", "b", {"n": "n"}, type="polytime-counting", frm_v="counting")):
        folder = "problems" if "objects" in e else "reductions"
        raw[folder][e["id"]] = e
    _, issues = validate_raw(raw)
    assert any("polytime-counting reduction needs counting versions" in str(i) for i in issues)


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
    assert payload["rulebook_version"] == 5
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


def test_preprint_result_is_optional_in_the_overview():
    # decided 18 November 2026: a paper with no peer-reviewed version is a preprint; its results
    # stay out of the Overview by default, are never preferred over a published result when
    # keeping, and carry the "preprint" flag (not "unverified")
    pre = paper("p-pre", 2026)
    pre["versions"] = {"arxiv-v1": pre["versions"]["arxiv-v1"]}
    data = dataset(
        problem("a"), pre, paper("p-ok", 2010),
        alg("a-pre", "a", r"O^*(1.1^{k})", paper="p-pre"),
        alg("a-ok", "a", r"O^*(1.5^{k})", paper="p-ok"),
    )
    out = to_json(data, derive(data))
    rows = {r["id"]: r for r in out["problems"]["a"]["decision"]}
    assert set(rows) == {"a-pre", "a-ok"}
    assert "preprint" in rows["a-pre"]["flags"] and "unverified" not in rows["a-pre"]["flags"]
    assert [e["cite"] for e in out["overview"]["a"]["decision"]] == [["a-ok"]]
    assert out["overview_optional"]["a"]["decision"] == [{"id": "a-pre", "beats": ["a-ok"], "year": 2026}]


def test_overview_prefers_a_deterministic_result_with_the_same_bound():
    # decided 18 November 2026: a randomized algorithm is a record only if it is faster than the
    # fastest deterministic one; with equal O* bounds the deterministic result is shown
    data = dataset(
        problem("a"), paper("p-r", 2000), paper("p-d", 2010),
        alg("a-rand", "a", r"O^*(1.5^{k})", paper="p-r", randomized={"error": "one-sided"}),
        alg("a-det", "a", r"O^*(1.5^{k})", paper="p-d"),
    )
    out = to_json(data, derive(data))
    cites = [e["cite"] for e in out["overview"]["a"]["decision"]]
    assert cites == [["a-det"]]


def test_overview_prefers_a_polynomial_space_result_with_the_same_bound():
    # decided 18 November 2026: polynomial space beats exponential space at equal bounds
    data = dataset(
        problem("a"), paper("p-e", 2000), paper("p-p", 2010),
        alg("a-exp", "a", r"O^*(1.5^{k})", paper="p-e", space="exponential"),
        alg("a-poly", "a", r"O^*(1.5^{k})", paper="p-p"),
    )
    out = to_json(data, derive(data))
    assert [e["cite"] for e in out["overview"]["a"]["decision"]] == [["a-poly"]]


def test_a_result_can_be_unverified_in_a_published_paper():
    # decided 18 November 2026: a statement in no peer-reviewed version (dropped from the
    # journal version) is treated like a result from an unverified paper
    data = dataset(
        problem("a"), paper("p", 2013),
        alg("a-journal", "a", r"O^*(1.6^{k})", paper="p"),
        alg("a-arxiv", "a", r"O^*(1.5^{k})", paper="p") | {"unverified": True},
    )
    out = to_json(data, derive(data))
    rows = {r["id"]: r for r in out["problems"]["a"]["decision"]}
    assert "unverified" in rows["a-arxiv"]["flags"] and "unverified" not in rows["a-journal"]["flags"]
    assert [e["cite"] for e in out["overview"]["a"]["decision"]] == [["a-journal"]]
    assert [e["id"] for e in out["overview_optional"]["a"]["decision"]] == ["a-arxiv"]


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


def test_the_real_data_leaves_nothing_to_common_sense():
    # decided 18 November 2026: whatever common sense decides, the engine decides. The numeric
    # cross-check lists Overview bounds that the comparator cannot order although one is at
    # most the other at every sample point; each needs a fact (constraint) or a rule.
    from pathlib import Path

    from pear.validate import validate_dir

    data, issues = validate_dir(Path(__file__).resolve().parents[1] / "data")
    assert issues == []
    assert derive(data).undecided == []


def test_omega_takes_its_best_published_or_claimed_value():
    # decided 18 November 2026: comparisons use the current best upper bound on ω, published
    # in the default Overview and claimed in the Overview with everything included; a result is
    # kept unless it is beaten at both values
    omega = {
        "id": "omega", "name": "Matrix multiplication exponent", "symbol": "\\omega",
        "definition": "A test constant.",
        "bounds": [
            {"relation": "le", "value": "2.4", "status": "established", "sources": [{"folklore": True, "note": "Test."}]},
            {"relation": "le", "value": "2.2", "status": "claimed", "sources": [{"folklore": True, "note": "Test."}]},
            {"relation": "ge", "value": "2", "sources": [{"folklore": True, "note": "Test."}]},
        ],
    }
    data = dataset(
        omega, problem("a"), paper("p1", 2000), paper("p2", 2010),
        alg("a-omega", "a", r"O^*(2^{\omega k})", paper="p1"),
        alg("a-plain", "a", r"O^*(2^{2.3 k})", paper="p2"),
    )
    out = to_json(data, derive(data))
    assert {r["id"] for r in out["problems"]["a"]["decision"]} == {"a-omega", "a-plain"}
    assert [e["cite"] for e in out["overview"]["a"]["decision"]] == [["a-plain"]]
    assert [e["cite"] for e in out["overview_all"]["a"]["decision"]] == [["a-omega"]]


CHECKS = ("subset-problem", "extension", "single-exponential", "error", "classical")


def technique(approved=True, problems=("a",), skip_check=None):
    out = {
        "id": "mls", "name": "Monotone Local Search",
        "source": {"paper": "p-mls", "statements": {"arxiv-v1": {"statement": "Theorems 1 and 2"}}},
        "input_parameter": "k", "output_parameter": "n", "base": "2 - 1/c",
        "prerequisites": [{"check": c, "statement": "Theorem 1", "text": "Fixture."} for c in CHECKS if c != skip_check],
        "rules": [
            {"id": "randomized", "statement": "Theorem 1", "accepts": ["deterministic", "one-sided", "two-sided"],
             "output_deterministic": False},
            {"id": "deterministic", "statement": "Theorem 2", "accepts": ["deterministic"],
             "output_deterministic": True, "keeps_polynomial_space": False, "subexponential_factor": True},
        ],
        "applies_to": [
            {"problem": p, "version": "decision", "universe": "n", "budget": "k",
             "setting": {"statement": "Section 1", "because": "Fixture."},
             "extension": {"statement": "Section 1", "because": "Fixture."}}
            for p in problems
        ],
    }
    if approved:
        out["review"] = {"approved_by": "Serge Gaspers", "date": "2026-11-18"}
    return out


def technique_rows(data, pid="a", node="decision"):
    return {r["id"]: r["shown"] for r in rows(data, pid, node) if "technique:" in r["id"]}


def test_monotone_local_search_combines_with_every_compatible_result():
    # decided 18 November 2026: a technique such as Monotone Local Search is applied by the
    # engine to every compatible result, so its bound improves whenever they do
    data = dataset(
        problem("a", params=("k",), constraints=[r"k \le n"]), paper("p-mls", 2015), paper("p1", 2010), paper("p2", 2020),
        technique(),
        alg("a-det", "a", r"O^*(4^{k})", paper="p1"),
        alg("a-rand", "a", r"O^*(3^{k})", paper="p2", randomized={"error": "one-sided"}),
    )
    out = to_json(data, derive(data))
    got = {r["id"]: (r["shown"], r["properties"]["deterministic"], r["year"]) for r in out["problems"]["a"]["decision"]}
    # 4^k, deterministic: 1.7501^n deterministic (Theorem 2, base rounded up strictly to absorb
    # the 2^{o(n)} factor); its randomized 1.75^n (Theorem 1) is beaten by the one from 3^k
    assert "a-det|technique:mls:randomized" not in got
    assert got["a-det|technique:mls:deterministic"] == ("O^*(1.7501^{n})", True, 2015)
    # 3^k, randomized: only Theorem 1 applies, dated by the later of the two
    assert got["a-rand|technique:mls:randomized"] == ("O^*(1.6667^{n})", False, 2020)
    assert "a-rand|technique:mls:deterministic" not in got


# Approved 18 November 2026 on condition that a technique is applied only when all its
# prerequisites are met (rulebook §9a); each test below fails one of them.


def mls_data(*algs, tech=None, versions=("decision",)):
    return dataset(problem("a", params=("k",), versions=versions, constraints=[r"k \le n"]), paper("p-mls", 2015),
                   tech or technique(), *algs)


def test_technique_waits_for_approval():
    data = mls_data(alg("a-det", "a", r"O^*(4^{k})"), tech=technique(approved=False))
    assert technique_rows(data) == {}
    assert any("mls: technique awaits approval (rule 6)" in line for line in derive(data).log)


def test_technique_only_for_problems_it_lists():
    data = dataset(problem("a"), problem("b"), paper("p-mls", 2015), technique(problems=("a",)),
                   alg("b-det", "b", r"O^*(4^{k})"))
    assert technique_rows(data, "b") == {}


def test_technique_only_for_the_listed_version():
    # an algorithm for a weighted version is not an algorithm for the version the technique
    # lists, whose extension version is the one known to be solvable
    data = mls_data(alg("a-w", "a", r"O^*(4^{k})", version="weighted"), versions=("decision", "weighted"))
    assert technique_rows(data, node="weighted") == {}
    assert any("listed for another version of a, not 'weighted'" in line for line in derive(data).log)


def test_technique_needs_an_algorithm_on_the_instance_alone():
    a = alg("a-td", "a", r"O^*(4^{k})")
    a["given"] = ["tree-decomposition"]
    data = mls_data(a)
    assert technique_rows(data) == {}
    assert any("needs a given tree-decomposition" in line for line in derive(data).log)


@pytest.mark.parametrize("bound", [
    r"O^*(4^{k} 2^{\sqrt{n}})",  # a factor superpolynomial in N
    r"O^*(4^{k} 1.1^{m})",  # a factor in another parameter
    r"O^*(k^{k})",  # superexponential
    r"O^*(2^{k^{2}})",
    r"O^*(2^{O(k)})",  # no constant c
])
def test_technique_needs_time_c_to_the_k(bound):
    data = mls_data(alg("a-x", "a", bound))
    assert technique_rows(data) == {}
    assert any("not applied to a-x: single-exponential" in line for line in derive(data).log)


@pytest.mark.parametrize(("bound", "shown"), [
    # Serge, 18 November 2026: a bound subexponential in k is (1 + δ)^k for every δ > 0, so
    # Monotone Local Search gives (1 + δ)^n for every δ > 0; likewise c^{k + o(k)} and families
    (r"O^*(2^{k / \log k})", r"O^*((1 + \delta)^{n}) \text{ for every } \delta > 0"),
    (r"O^*(2^{o(k)})", r"O^*((1 + \delta)^{n}) \text{ for every } \delta > 0"),
    (r"O^*(4^{k} 2^{\sqrt{k}})", r"O^*((1.7500 + \delta)^{n}) \text{ for every } \delta > 0"),
    (r"O((4 + \delta)^{k}) \text{ for every } \delta > 0", r"O^*((1.7500 + \delta)^{n}) \text{ for every } \delta > 0"),
    (r"O(k^{3} 4^{k} n)", r"O^*(1.7501^{n})"),  # polynomial factors in k are fine
])
def test_technique_takes_c_to_the_k_plus_o_k(bound, shown):
    # the outputs before keeping (k <= n beats some of them, see below)
    data = mls_data(alg("a-x", "a", bound))
    engine = Engine(data)
    engine.run()
    got = {t.chain[-1].id: render_bound(t.bound) for t in engine.techniques(engine.direct(data.entries["algorithms"]["a-x"]))}
    assert got["technique:mls:deterministic"] == shown
    assert set(got) == {"technique:mls:randomized", "technique:mls:deterministic"}


def test_technique_family_output_is_beaten_by_the_input_itself():
    # k <= n already turns 2^{k / log k} into 2^{n / log n}, which beats (1 + δ)^n for every δ
    data = mls_data(alg("a-x", "a", r"O^*(2^{k / \log k})", randomized={"error": "one-sided"}))
    shown = {r["id"]: r["shown"] for r in rows(data, "a", "decision")}
    assert "a-x|technique:mls:randomized" not in shown
    assert any(i.startswith("a-x|projection") for i in shown)


def test_technique_needs_a_classical_algorithm():
    data = mls_data(alg("a-q", "a", r"O^*(4^{k})", quantum=True))
    assert technique_rows(data) == {}
    assert any("classical: the algorithm is quantum" in line for line in derive(data).log)


@pytest.mark.parametrize(("randomized", "theorems"), [
    (False, {"randomized", "deterministic"}),
    ({"error": "one-sided"}, {"randomized"}),
    ({"error": "two-sided"}, {"randomized"}),  # Remark 1: the output then has two-sided error
    # Serge, 18 November 2026: stopped at twice its expected running time, a Las Vegas
    # algorithm has one-sided error (Markov)
    ({"error": "las-vegas"}, {"randomized"}),
    (True, {"randomized"}),  # error not recorded: Las Vegas, one- or two-sided, all covered
])
def test_technique_rules_cover_the_inputs_their_theorems_cover(randomized, theorems):
    tech = technique()
    tech["rules"][0]["keeps_polynomial_space"] = False  # so neither output beats the other
    data = mls_data(alg("a-x", "a", r"O^*(4^{k})", randomized=randomized), tech=tech)
    assert {i.rsplit(":", 1)[1] for i in technique_rows(data)} == theorems


def test_technique_through_a_randomized_reduction_only_by_theorem_1():
    # a randomized reduction records no error type, but Theorem 1 covers every kind
    # (Serge, 18 November 2026); Theorem 2 needs a deterministic input
    def data_for(rtype):
        return dataset(problem("a", constraints=[r"k \le n"]), problem("b"), paper("p-mls", 2015), technique(),
                       alg("b-det", "b", r"O^*(4^{k})"), red("a-to-b", "a", "b", {"k": "k", "n": "n"}, type=rtype))
    assert set(technique_rows(data_for("polytime-deterministic"))) == {
        "b-det|a-to-b|technique:mls:randomized", "b-det|a-to-b|technique:mls:deterministic"}
    assert set(technique_rows(data_for("polytime-randomized"))) == {"b-det|a-to-b|technique:mls:randomized"}


def test_technique_is_applied_once_per_chain():
    data = mls_data(alg("a-det", "a", r"O^*(4^{k})"))
    assert all(i.count("technique:") == 1 for i in technique_rows(data))


def raw_of(*entries):
    raw = {folder: {} for folder in ENTITY_TYPES}
    for e in entries:
        folder = "techniques" if "applies_to" in e else "papers" if "authors" in e else "problems"
        raw[folder][e["id"]] = e
    return raw


@pytest.mark.parametrize(("change", "expected"), [
    (lambda t: t.update(technique(skip_check="extension")), "missing: extension"),
    (lambda t: t["prerequisites"].append(dict(t["prerequisites"][0])), "listed twice: subset-problem"),
    (lambda t: t["prerequisites"][0].update(check="monotone"), "prerequisites.0.check"),
    (lambda t: t["applies_to"][0].update(budget="tw"), "'tw' is not a parameter of problem 'a'"),
    (lambda t: t["applies_to"][0].update(universe="k"), "'k' is not an object count of problem 'a'"),
    (lambda t: t["applies_to"][0].pop("extension"), "extension"),
    (lambda t: t["rules"][0].update(accepts=[]), "accepts"),
])
def test_technique_validation(change, expected):
    tech = technique()
    change(tech)
    _, issues = validate_raw(raw_of(problem("a"), paper("p-mls", 2015), tech))
    assert any(expected in str(i) for i in issues), [str(i) for i in issues]



def test_projection_keeps_subtracted_constants_and_constraint_coefficients():
    # 20 November 2026: m <= n(n - 1)/2 projects 1.5^m to 1.5^{n^2/2}, not 1.5^{n^2}
    data = dataset(
        problem("a", params=("k",), constraints=[r"m \le n (n - 1)/2"]),
        alg("a-alg", "a", r"O^*(1.5^{m})"),
    )
    shown = {r["shown"] for r in rows(data, "a")}
    assert r"O^*(1.5^{n^{2}/2})" in shown and r"O^*(1.5^{n^{2}})" not in shown


def test_drop_subtractions_keeps_constants():
    from pear.bounds.expr import parse_expr, render
    from pear.derive import _monotone_majorant

    e = parse_expr(r"(3 \cdot 2^{\omega - 1} + 1)^{n - k}", {"n", "k"})
    assert render(_monotone_majorant(e)) == r"(3 \cdot 2^{\omega - 1} + 1)^{n}"


# --- folklore results count as earliest (20 November 2026) ------------------------------------


def test_brute_force_drops_equal_later_derived_bounds_and_is_cited():
    data = dataset(
        problem("a", constraints=[r"k \le n"]), problem("b"), paper("p", 2000),
        alg("a-brute", "a", r"O^*(2^{n})"),  # folklore
        alg("b-alg", "b", r"O^*(2^{k})", paper="p"),
        red("a-to-b", "a", "b", {"k": "n"}),
        alg("b-slow", "b", r"O^*(4^{k})", paper="p"),
    )
    got = {r["shown"]: r for r in rows(data, "a")}
    assert set(got) == {r"O^*(2^{n})"} and got[r"O^*(2^{n})"]["origin"] == "direct"
    assert overview(data, "a") == [{"shown": r"O^*(2^{n})", "cite": ["a-brute"], "members": ["a-brute"], "year": None}]


# --- review decisions (Serge, 20 November 2026) -------------------------------------------


def test_a_bound_projected_through_constraints_is_not_transferred():
    # b's 1.2^k with b's constraint k <= n projects to 1.2^n at b; a reaches b's original
    # bound and has no such constraint, so a gets 1.2^k only, not 1.2^n
    data = dataset(
        problem("a"), problem("b", constraints=[r"k \le n"]),
        alg("b-alg", "b", r"O^*(1.2^{k})"), red("a-to-b", "a", "b", {"n": "n", "k": "k"}),
    )
    assert {r["shown"] for r in rows(data, "b")} == {r"O^*(1.2^{k})", r"O^*(1.2^{n})"}
    assert [r["shown"] for r in derived(data, "a")] == [r"O^*(1.2^{k})"]


def test_composite_projection_is_proved_and_transfers():
    # f(n - k) with f nondecreasing is at most f(n) (k >= 0), and needs no constraint
    data = dataset(
        problem("a"), problem("b"), problem("c"),
        alg("c-alg", "c", r"O^*(2^{O(k \log \log k/\sqrt{\log k})})"),
        red("b-to-c", "b", "c", {"n": "n", "k": "n - k"}),
        red("a-to-b", "a", "b", {"n": "n", "k": "k"}),
    )
    assert r"O^*(2^{O(n \log \log n/\sqrt{\log n})})" in {r["shown"] for r in derived(data, "b")}
    assert r"O^*(2^{O(n \log \log n/\sqrt{\log n})})" in {r["shown"] for r in derived(data, "a")}


def test_projection_to_n_needs_no_given_tree_decomposition():
    a = alg("a-alg", "a", r"O^*(2^{tw})", params=("tw",))
    a["given"] = ["tree-decomposition"]
    data = dataset(problem("a", params=("tw",), constraints=[r"tw \le n"]), a)
    flags = {r["shown"]: r["flags"] for r in rows(data, "a")}
    assert "given-tree-decomposition" in flags[r"O^*(2^{\mathit{tw}})"]
    assert "given-tree-decomposition" not in flags[r"O^*(2^{n})"]


def test_equal_ostar_forms_are_equal_whatever_the_polynomial_factors():
    # b's own O(2^n (n + m)) is not dropped for a's 2^n arriving through the complement map,
    # whose factor n + (n(n-1)/2 - m) has no lower estimate (20 November 2026)
    data = dataset(
        problem("a", params=()), problem("b", params=()),
        alg("a-alg", "a", r"O(2^{n} (n + m))", params=()),
        alg("b-alg", "b", r"O(2^{n} (n + m))", params=()),
        red("b-to-a", "b", "a", {"n": "n", "m": "n (n - 1)/2 - m"}),
    )
    assert "b-alg" in {r["id"] for r in rows(data, "b")}


def test_xp_bounds_are_shown_exactly():
    data = dataset(problem("a"), alg("a-alg", "a", r"O(n^{k + 1})"), alg("a-exp", "a", r"O(k^{n} n)"))
    shown = {r["id"]: r["shown"] for r in rows(data, "a")}
    assert shown["a-alg"] == r"O(n^{k + 1})"  # not O^*(n^{k})
    assert shown["a-exp"] == r"O^*(k^{n})"  # an exact exponential algorithm keeps O*


def test_other_given_structures_are_dropped_by_projection_to_n():
    # 21 November 2026: given path decompositions, deletion sets, ... are trivial at size n
    a = problem("a", params=("pw",), constraints=("pw \\le n",))
    data = dataset(a, alg("a-alg", "a", r"O^*(2^{pw})", params=("pw",)) | {"given": ["path-decomposition"]})
    got = rows(data, "a")
    direct = next(r for r in got if r["id"] == "a-alg")
    assert "given-path-decomposition" in direct["flags"]
    projected = [r for r in got if r["id"] != "a-alg" and r["shown"] == r"O^*(2^{n})"]
    assert projected and all("given-path-decomposition" not in r["flags"] for r in projected)
