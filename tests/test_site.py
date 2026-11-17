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
    [("1.2738^{k}", 1.2738), ("2^{n/4}", 2 ** 0.25), ("2^{tw}", 2.0), ("1.5^{2 n}", 2.25),
     ("(2 + (1 + \\sqrt{5})/2)^{k}", 2 + (1 + 5 ** 0.5) / 2)],
)
def test_single_base(expr, base):
    assert single_base(parse_expr(expr, {"k", "n", "tw"})) == pytest.approx(base)


@pytest.mark.parametrize("expr", ["1.2^{n - k}", "k^{k}", "2^{n^{2}}", "n^{3}", "2^{\\sqrt{n}}"])
def test_single_base_only_for_simple_exponentials(expr):
    assert single_base(parse_expr(expr, {"k", "n"})) is None


def _row(rid, year, params=("k",), flags=(), quantum=False, deterministic=True):
    return {"id": rid, "year": year, "parameters": list(params), "flags": list(flags), "shown": rid,
            "refs": [], "origin": "direct", "properties": {"quantum": quantum, "deterministic": deterministic}}


def test_history_keeps_only_improvements_in_year_order():
    rows = [_row("a", 2006), _row("b", 2023), _row("c", 2010), _row("d", 2025), _row("u", 2001, flags=["unverified"])]
    bases = {"a": 1.2738, "b": 1.25284, "c": 1.28, "d": 1.25281, "u": 1.2}
    steps = history(rows, bases)["k"]
    assert [s["row"] for s in steps] == ["a", "b", "d"]


def test_randomized_results_are_records_only_if_faster_than_every_earlier_result():
    # decided 18 November 2026: a deterministic algorithm is also a randomized one, so a
    # randomized result is a record only if it beats the fastest deterministic one (and every
    # earlier randomized one); deterministic results are records against deterministic ones
    rows = [_row("d1", 2000), _row("r1", 2005, deterministic=False), _row("d2", 2010),
            _row("r2", 2012, deterministic=False), _row("r3", 2015, deterministic=False), _row("d3", 2020)]
    bases = {"d1": 2.0, "r1": 1.5, "d2": 1.8, "r2": 1.6, "r3": 1.4, "d3": 1.4}
    steps = history(rows, bases)["k"]
    assert [(s["row"], s["deterministic"]) for s in steps] == [
        ("d1", True), ("r1", False), ("d2", True), ("r3", False), ("d3", True)]
    # a randomized result that only matches a deterministic one of the same year is no record
    rows = [_row("d", 2010), _row("r", 2010, deterministic=False)]
    assert [s["row"] for s in history(rows, {"d": 1.5, "r": 1.5})["k"]] == ["d"]


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
    headings = [g["heading"] for g in node["overview"]]
    assert headings[0] == "By solution size" and headings[-1] == "By treewidth"
    assert "By number of vertices" in headings
    # Overview: no unverified result; Details: every kept result
    shown = [e["cite"][0]["id"] for g in node["overview"] for e in g["entries"] if not e.get("optional")]
    assert not any("robson" in s or "kundu" in s for s in shown)
    assert any("kundu" in r["id"] for r in node["rows"])
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


def test_projection_names_only_the_constraint_used(tmp_path):
    from test_derive import alg, dataset, problem

    data = dataset(
        problem("a", params=("k", "tw"), constraints=[r"k \le n", r"tw \le n", r"m \le n^{2}"]),
        alg("a-tw", "a", r"O^*(2^{tw})", params=("tw",)),
    )
    site = build(data, derive(data), tmp_path)
    rows = site["pages"]["a"]["nodes"]["decision"]["rows"]
    proj = [i for r in rows for i in r["chain_items"] if i["kind"] == "projection"]
    assert proj and proj[0]["constraints"] == ["tw \\le n"]


def test_entries_written_as_json(real):
    _, _, out = real
    vc = json.loads((out / "entries" / "problems" / "vertex-cover.json").read_text())
    assert vc["id"] == "vertex-cover" and "results" in vc
    assert (out / "entries" / "papers" / "karp-1972.json").exists()


def test_index_lists_all_pilot_problems(real):
    _, site, _ = real
    names = [e["name"] for e in site["index"]]
    assert names[:2] == ["Vertex Cover", "Independent Set"] and len(names) >= 12
    assert all(e["id"] for e in site["index"][:12])  # all pilot problems entered


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


def test_unverified_results_can_be_switched_into_the_overview(real):
    # decided 12 November 2026: unverified results are off by default, each can be included
    _, site, _ = real
    groups = site["pages"]["3-coloring"]["nodes"]["decision+search"]["overview"]
    entries = [e for g in groups for e in g["entries"]]
    optional = {e["cite"][0]["id"] for e in entries if e.get("optional")}
    kundu = "3-coloring--n--kundu-panolan-saurabh-xue-zehavi-2026"
    assert kundu in optional
    beigel = next(e for e in entries if "3-coloring--n--beigel-eppstein-2000" in e["members"])
    assert kundu in beigel["beaten_by"]


def test_lean_proved_checked_results_count_as_verified(real):
    # decided 12 November 2026: a Lean-proved result whose statement was checked against our
    # definition counts as verified even though its paper is marked unverified
    _, site, _ = real
    groups = site["pages"]["sharp-3-sat"]["nodes"]["counting"]["overview"]
    entries = [e for g in groups for e in g["entries"]]
    shown = {e["cite"][0]["id"] for e in entries if not e.get("optional")}
    assert {"sharp-3-sat--n--anthropic-2026", "sharp-3-sat--m--anthropic-2026"} <= shown
    assert not any(e.get("optional") for e in entries)


def test_flawed_result_is_listed_but_not_used(real):
    # Fomin–Gaspers–Saurabh 2006, Theorem 2: marked flawed by Serge (11 November 2026)
    _, site, _ = real
    node = site["pages"]["independent-set"]["nodes"]["weighted"]
    assert not any("fomin-gaspers-saurabh" in r["id"] for r in node["rows"])
    flagged = {f["id"]: f for f in node["flagged"]}
    assert flagged["independent-set--n--fomin-gaspers-saurabh-2006"]["status"] == "unrepaired"


def test_results_list_what_they_use(real):
    # decided 13 November 2026: `uses`, shown in the Source column
    _, site, _ = real
    node = site["pages"]["vertex-cover"]["nodes"]["decision+optimisation+search"]
    row = next(r for r in node["rows"] if r["id"] == "vertex-cover--k--kundu-panolan-saurabh-xue-zehavi-2026")
    assert [u["id"] for u in row["uses"]] == ["sharp-3-sat--n--anthropic-2026"]
    assert row["uses"][0]["problem"] == "#3-SAT" and not row["uses"][0]["same"]


def test_references_name_the_journal_version_and_the_cited_statement(real):
    # decided 17 November 2026: a reference names the journal version, else the conference
    # version, else a technical report or preprint; the cited statement is shown with the
    # version it is in, and the other versions follow.
    _, site, _ = real
    refs = {r["id"]: r for r in site["pages"]["feedback-vertex-set"]["references"]}
    kp = refs["kociumaka-pilipczuk-2014"]
    assert kp["primary"] == "Information Processing Letters 114(10), pp. 556–560, 2014"
    assert kp["cited"] == ["Theorem 2 of arXiv v1"]
    assert kp["others"] == ["arXiv:1306.3566v1, 2013"]
    assert kp["links"][0]["url"] == "https://doi.org/10.1016/j.ipl.2014.05.001"
    # journal over conference; a retitled journal version brings its own title
    refs = {r["id"]: r for r in site["pages"]["vertex-cover"]["references"]}
    ckx = refs["chen-kanj-xia-2006"]
    assert ckx["primary"].startswith("Theoretical Computer Science 411")
    assert ckx["title"] == "Improved upper bounds for vertex cover"
    # other versions show their own title (and authors) where they differ from the named one's
    assert ckx["others"][0].startswith("Improved Parameterized Upper Bounds for Vertex Cover. Mathematical Foundations")
    # conference over preprint
    hn = refs["harris-narayanaswamy-2022"]
    assert "STACS 2024" in hn["primary"]
    assert any(c.endswith("arXiv v7") or "arXiv v" in c for c in hn["cited"])


def test_primary_version_order():
    from pear.schema import Paper
    from pear.site import primary_version

    def paper(**kinds):
        return Paper.model_validate({"id": "p", "title": "T", "authors": ["A"], "versions": {
            vid: {"kind": kind, "year": year, "open_access": False} for vid, (kind, year) in kinds.items()}})

    assert primary_version(paper(a=("preprint", 2020), b=("conference", 2021), c=("journal", 2023))) == "c"
    assert primary_version(paper(a=("preprint", 2020), b=("technical-report", 2019))) == "b"
    assert primary_version(paper(a=("preprint", 2020), b=("workshop", 2019), c=("conference", 2018))) == "c"
    assert primary_version(paper(a=("preprint", 2020), b=("preprint", 2022))) == "b"


def test_merged_journal_version_brings_its_authors(real):
    # decided 18 November 2026: Fomin, Gaspers and Saurabh (ISAAC 2006) was merged with
    # another paper into Fomin, Gaspers, Saurabh and Stepanov (Algorithmica 2009), which
    # counts as its journal version; the reference names that version, with its authors.
    _, site, _ = real
    refs = {r["id"]: r for r in site["pages"]["independent-set"]["references"]}
    fgs = refs["fomin-gaspers-saurabh-2006"]
    assert fgs["authors"] == "Fedor V. Fomin, Serge Gaspers, Saket Saurabh and Alexey A. Stepanov"
    assert fgs["title"] == "On Two Techniques of Combining Branching and Treewidth"
    assert fgs["primary"] == "Algorithmica 54(2), pp. 181–207, 2009"
    assert fgs["cited"] == ["Theorem 2 of ISAAC 2006"]


def test_corrected_deterministic_fvs_uses_kociumaka_pilipczuk(real):
    # decided 18 November 2026: Theorem 2 of Fomin et al. with the journal bound (2 + phi)^k
    _, site, _ = real
    node = site["pages"]["feedback-vertex-set"]["nodes"]["decision+optimisation+search"]
    row = next(r for r in node["rows"] if r["id"] == "feedback-vertex-set--n--fomin-gaspers-lokshtanov-saurabh-2015-deterministic")
    assert row["shown"] == "O^*(1.7237^{n})"
    assert [u["id"] for u in row["uses"]] == ["feedback-vertex-set--k--kociumaka-pilipczuk-2014"]


def test_preliminary_version_by_fewer_authors(real):
    # decided 18 November 2026: STACS 2012 (Narayanaswamy, Raman, Ramanujan, Saurabh) is the
    # conference version of Lokshtanov et al. (TALG 2014), as its authors say
    _, site, _ = real
    refs = {r["id"]: r for r in site["pages"]["odd-cycle-transversal"]["references"]}
    lp = refs["lokshtanov-narayanaswamy-raman-ramanujan-saurabh-2012"]
    assert lp["primary"].startswith("ACM Transactions on Algorithms 11(2)")
    assert lp["authors"].startswith("Daniel Lokshtanov, ")
    assert ("N. S. Narayanaswamy, Venkatesh Raman, M. S. Ramanujan and Saket Saurabh. "
            "LP can be a cure for Parameterized Problems. 29th International Symposium") in lp["others"][1]


def test_preprints_are_optional_in_the_overview_and_on_the_front_page(real):
    # decided 18 November 2026: results from preprints (no peer-reviewed version) are left out of
    # the Overview by default, like unverified ones; one browser-stored switch includes them all,
    # in the Overview and on the front page
    _, site, _ = real
    node = site["pages"]["vertex-cover"]["nodes"]["decision+optimisation+search"]
    assert node["has_optional"]
    entries = [e for g in node["overview"] for e in g["entries"]]
    clinch = next(e for e in entries if e["cite"][0]["id"] == "vertex-cover--k--clinch-gaspers-he-2025")
    assert clinch.get("optional") and "preprint" in clinch["cite"][0]["flags"]
    shown = [e["cite"][0]["id"] for e in entries if not e.get("optional")]
    assert "vertex-cover--k--harris-narayanaswamy-2022" in shown
    # Details keeps every result and the history still counts preprints (Details unchanged)
    assert any(r["id"] == "vertex-cover--k--clinch-gaspers-he-2025" for r in node["rows"])
    assert [s["year"] for s in node["history"]["k"]["steps"]] == [2006, 2023, 2025]
    front = {e["id"]: e for e in site["index"] if e["id"]}
    vc = front["vertex-cover"]["bounds"]
    assert any(b["optional"] and b["id"] == "vertex-cover--k--clinch-gaspers-he-2025" for b in vc)
    assert any(not b["optional"] and b["id"] == "vertex-cover--k--harris-narayanaswamy-2022" for b in vc)
    # every problem on the front page lists its bounds, not only the pilot problems
    assert front["feedback-vertex-set"]["bounds"]


def test_reference_names_every_conference_paper_a_paper_is_based_on(real):
    # decided 18 November 2026: ESA 2009 and MFCS 2010 are conference versions of van Rooij et al.
    # (arXiv 2018); with no journal version, the reference names both, earliest first, and the
    # paper is no longer a preprint, so its result is in the default Overview
    _, site, _ = real
    page = site["pages"]["dominating-set"]
    ref = {r["id"]: r for r in page["references"]}["van-rooij-et-al-2018"]
    assert ref["authors"] == "Johan M. M. van Rooij, Hans L. Bodlaender and Peter Rossmanith"
    assert ref["primary"].startswith("Algorithms (ESA 2009), LNCS 5757, pp. 566–577; and Hans L. Bodlaender, ")
    assert ref["others"][0].endswith("Fast Dynamic Programming on Graph Decompositions. arXiv:1806.01667, 2018")
    node = page["nodes"]["decision+optimisation+search"]
    shown = [e["cite"][0]["id"] for g in node["overview"] for e in g["entries"] if not e.get("optional")]
    assert "dominating-set--tw--van-rooij-et-al-2018" in shown


def test_vertex_cover_by_m_uses_n_at_most_m(real):
    # decided 18 November 2026: preprocessing (degree 0 and 1) gives n <= m without loss of
    # generality, so an algorithm in n is one in m and the trivial 2^m is no record
    _, site, _ = real
    for pid in ("vertex-cover", "independent-set"):
        node = site["pages"][pid]["nodes"]["decision+optimisation+search"]
        assert not any(g["parameters"] == ["m"] and not g["only_optional"] for g in node["overview"])
        assert [s["base"] for s in node["history"]["m"]["steps"]] == [1.1996]
