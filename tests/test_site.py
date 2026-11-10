"""Site data (src/pear/site.py): what the pages are built from."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pear.bounds import parse_expr
from pear.derive import derive
from pear.site import build, history, paper_version_label, parameter_info, single_base
from pear.validate import validate_dir

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "valid"


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    data, issues = validate_dir(ROOT / "data")
    assert issues == []
    out = tmp_path_factory.mktemp("site")
    return data, build(data, derive(data), out), out


@pytest.mark.parametrize(
    ("expr", "base"),
    [("1.2738^{k}", 1.2738), ("2^{n/4}", 2 ** 0.25), ("2^{tw}", 2.0), ("1.5^{2 n}", 2.25)],
)
def test_single_base(expr, base):
    assert single_base(parse_expr(expr, {"k", "n", "tw"})) == pytest.approx(base)


@pytest.mark.parametrize("expr", ["1.2^{n - k}", "k^{k}", "2^{n^{2}}", "n^{3}", "2^{\\sqrt{n}}"])
def test_single_base_only_for_simple_exponentials(expr):
    assert single_base(parse_expr(expr, {"k", "n"})) is None


def _row(rid, year, params=("k",), flags=(), quantum=False):
    return {"id": rid, "year": year, "parameters": list(params), "flags": list(flags), "shown": rid,
            "refs": [], "origin": "direct", "properties": {"quantum": quantum}}


def test_history_keeps_only_improvements_in_year_order():
    rows = [_row("a", 2006), _row("b", 2023), _row("c", 2010), _row("d", 2025), _row("u", 2001, flags=["unverified"])]
    bases = {"a": 1.2738, "b": 1.25284, "c": 1.28, "d": 1.25281, "u": 1.2}
    steps = history(rows, bases)["k"]
    assert [s["row"] for s in steps] == ["a", "b", "d"]


def test_history_skips_quantum_and_multi_parameter_bounds():
    rows = [_row("q", 2020, quantum=True), _row("m", 2021, params=("k", "n"))]
    assert history(rows, {"q": 1.1, "m": 1.1}) == {}


def test_paper_version_labels(real):
    data, _, _ = real
    hn = data.papers["harris-narayanaswamy-2022"]
    assert paper_version_label(hn, "arxiv-v4") == "arXiv v4"
    assert paper_version_label(hn, "stacs") == "STACS 2024"
    assert paper_version_label(data.papers["cygan-fomin-kowalik-2016"], "book-pdf") == "book"


def test_parameter_headings(real):
    data, _, _ = real
    short = {p["symbol"]: p["short"] for p in parameter_info(data, data.problems["vertex-cover"])}
    assert short == {"k": "solution size", "n": "number of vertices", "m": "number of edges",
                     "N": "input size", "tw": "treewidth"}


def test_vertex_cover_page(real):
    _, site, _ = real
    page = site["pages"]["vertex-cover"]
    node = page["nodes"]["decision+optimisation+search"]
    assert [g["heading"] for g in node["overview"]] == ["By solution size", "By number of vertices", "By treewidth"]
    # Overview: no unverified result; Details: every kept result
    shown = [e["cite"][0]["id"] for g in node["overview"] for e in g["entries"]]
    assert not any("robson" in s for s in shown)
    assert any("robson" in r["id"] for r in node["rows"])
    # every cited paper has a reference, numbered from 1 without gaps
    assert [r["n"] for r in page["references"]] == list(range(1, len(page["references"]) + 1))
    cited = {n for r in node["rows"] for n in r["refs"]}
    assert cited <= {r["n"] for r in page["references"]}
    # derived bounds carry their chain, from the source algorithm to this problem
    derived = next(r for r in node["rows"] if r["origin"] == "derived" and "xiao" in r["id"])
    kinds = [i["kind"] for i in derived["chain_items"]]
    assert kinds == ["start", "reduction", "end"]
    assert derived["chain_items"][0]["problem"] == "Independent Set"
    assert page["implementations"]["items"][0]["id"] == "wegotyoucovered"


def test_projection_names_only_the_constraint_used(real):
    _, site, _ = real
    rows = site["pages"]["independent-set"]["nodes"]["weighted"]["rows"]
    proj = next(i for r in rows for i in r["chain_items"] if i["kind"] == "projection")
    assert proj["constraints"] == ["tw \\le n"]


def test_entries_written_as_json(real):
    _, _, out = real
    vc = json.loads((out / "entries" / "problems" / "vertex-cover.json").read_text())
    assert vc["id"] == "vertex-cover" and "results" in vc
    assert (out / "entries" / "papers" / "karp-1972.json").exists()


def test_index_lists_all_pilot_problems(real):
    _, site, _ = real
    names = [e["name"] for e in site["index"]]
    assert names[:2] == ["Vertex Cover", "Independent Set"] and len(names) >= 12
    assert site["index"][2]["id"] is None  # not entered yet


def test_fixture_data_builds(tmp_path):
    data, issues = validate_dir(FIXTURES)
    assert issues == []
    site = build(data, derive(data), tmp_path)
    assert set(site["pages"]) == set(data.problems)


def test_beaten_direct_result_only_in_history(real):
    # rulebook version 3: Chen–Kanj–Xia 2006 is beaten in every filter by Harris–Narayanaswamy
    _, site, _ = real
    node = site["pages"]["vertex-cover"]["nodes"]["decision+optimisation+search"]
    assert not any("chen-kanj-xia" in r["id"] for r in node["rows"])
    assert [s["year"] for s in node["history"]["k"]["steps"]] == [2006, 2023, 2025]
