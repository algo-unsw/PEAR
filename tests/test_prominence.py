"""Prominence score (src/pear/prominence.py) and the front page grouped by category."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from pear import prominence as pm
from pear.derive import derive
from pear.site import FRONT_PAGE_TOP, build
from pear.validate import validate_dir

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data():
    data, issues = validate_dir(ROOT / "data")
    assert issues == []
    return data


def test_percentile_ranks():
    r = pm.percentile_ranks({"a": 10, "b": 1000, "c": 0, "d": None, "e": 10})
    assert r["d"] is None and r["c"] == 0.0 and r["b"] == 1.0
    # a and e tie: one smaller value (c), one equal other: (1 + 1/2) / 3
    assert r["a"] == r["e"] == pytest.approx(0.5)
    assert pm.percentile_ranks({"x": 5}) == {"x": 1.0}
    assert pm.percentile_ranks({"x": 0, "y": 0}) == {"x": 0.0, "y": 0.0}


def test_ranks_ignore_scale():
    """Only the order of counts matters, so one huge count cannot dominate."""
    a = pm.percentile_ranks({"p": 1, "q": 2, "r": 3})
    b = pm.percentile_ranks({"p": 1, "q": 2, "r": 10 ** 9})
    assert a == b


def test_scores_weights_and_missing_groups(data):
    pids = sorted(data.problems)[:3]
    top, mid, low = pids
    signals = {"problems": {
        top: {s: 100 for s in ("openalex_works", "openlibrary_books", "google_books", "wikipedia_pageviews",
                               "wikipedia_mentions", "stackexchange_questions")},
        mid: {"openalex_works": 50, "openlibrary_books": 50, "google_books": None, "wikipedia_pageviews": 0,
              "wikipedia_mentions": 50, "stackexchange_questions": None},
        low: {"openalex_works": 1},
    }}
    rows = pm.scores(data, signals)
    assert rows[top]["groups"]["scholarly"] == 100.0
    assert rows[mid]["groups"]["web"] is None and rows[mid]["complete"] is False
    # Wikipedia for mid: page views 0 -> rank 0; mentions 50 of {100, 50} -> rank 0; mean 0
    assert rows[mid]["groups"]["wikipedia"] == 0.0
    # problems without fetched signals are scored on PEAR entries alone
    other = sorted(data.problems)[5]
    assert rows[other]["score"] == rows[other]["groups"]["pear"]
    for r in rows.values():
        assert 0 <= r["score"] <= 100


def test_score_formula(data):
    pid = sorted(data.problems)[0]
    rows = pm.scores(data, {"problems": {pid: {"openalex_works": 10}}})
    g = rows[pid]["groups"]
    # scholarly (0.30) is the only external group with data: (0.3 * 100 + 0.15 * pear) / 0.45
    assert g["scholarly"] == 100.0
    assert rows[pid]["score"] == pytest.approx(round((0.3 * 100 + 0.15 * g["pear"]) / 0.45, 1), abs=0.11)


def test_pear_entries_counts_results_and_reductions(data):
    counts = pm.pear_entries(data)
    assert set(counts) == set(data.problems)
    algs = sum(1 for a in data.entries["algorithms"].values() if a.problem == "vertex-cover")
    assert counts["vertex-cover"] > algs  # plus the reductions from and to Vertex Cover


def test_phrases_and_wikipedia_candidates():
    assert pm.phrases_for("3-Coloring", None) == ["3-Coloring", "3-Colouring"]
    assert pm.phrases_for("Travelling Salesperson", None) == ["Travelling Salesperson", "Traveling Salesperson"]
    assert pm.phrases_for("SAT", {"phrases": ["Boolean satisfiability"]}) == ["Boolean satisfiability"]
    assert pm.phrases_for("x", {"phrases": ["graph 3-coloring"]}) == ["graph 3-coloring", "graph 3-colouring"]
    c = pm.wikipedia_candidates("Vertex Cover", ["Vertex Cover"], {"wikipedia": "Vertex cover"})
    assert c[0] == "Vertex cover" and "Vertex Cover" in c and "Vertex cover problem" in c
    assert pm.wikipedia_candidates("3-Coloring", ["3-colorability"], {"wikipedia": False}) == []


def test_fetch_with_fake_network(data):
    """The fetcher parses each source's response; a failing source becomes a gap, not a crash."""
    def fake(url: str):
        if "openalex" in url:
            return {"meta": {"count": 42}}
        if "openlibrary" in url:
            return {"hits": {"total": {"value": 7}}}
        if "googleapis" in url:
            raise OSError("blocked")
        if "list=search" in url:
            return {"query": {"searchinfo": {"totalhits": 3}}}
        if "en.wikipedia.org" in url:
            return {"query": {"redirects": [{"from": "Vertex Cover", "to": "Vertex cover"}],
                              "pages": {"1": {"ns": 0, "title": "Vertex cover"}}}}
        if "pageviews" in url:
            return {"items": [{"views": 10}, {"views": 5}]}
        if "stackexchange" in url:
            return {"total": 2, "quota_remaining": 100}
        raise AssertionError(url)

    f = pm.Fetcher(delay=0, opener=fake)
    snap = pm.fetch(data, {}, today=dt.date(2026, 11, 21), fetcher=f, only=["vertex-cover"], log=lambda s: None)
    row = snap["problems"]["vertex-cover"]
    assert row["openalex_works"] == 42 and row["openlibrary_books"] == 7 and row["google_books"] is None
    assert row["wikipedia_title"] == "Vertex cover" and row["wikipedia_pageviews"] == 15
    assert row["stackexchange_questions"] == 2 * len(pm.STACKEXCHANGE_SITES)
    assert any("blocked" in e for e in snap["errors"])


def test_section_redirect_counts_the_redirect():
    def fake(url: str):
        return {"query": {"redirects": [{"from": "Total dominating set", "to": "Dominating set", "tofragment": "Variants"}],
                          "pages": {"1": {"ns": 0, "title": "Dominating set"}}}}
    title, section = pm.Fetcher(delay=0, opener=fake).wikipedia_article(["Total dominating set"])
    assert title == "Total dominating set" and section == "Dominating set#Variants"


def test_unrelated_section_redirects_are_skipped():
    def fake(url: str):
        if "titles=Max+Cut&" in url:
            return {"query": {"redirects": [{"from": "Max Cut", "to": "Ava Max", "tofragment": "Public image"}],
                              "pages": {"1": {"ns": 0, "title": "Ava Max"}}}}
        return {"query": {"pages": {"2": {"ns": 0, "title": "Maximum cut"}}}}
    words = pm.significant_words("max cut maximum cut")
    title, section = pm.Fetcher(delay=0, opener=fake).wikipedia_article(["Max Cut", "Maximum cut"], words)
    assert (title, section) == ("Maximum cut", None)


def test_disambiguation_pages_are_skipped():
    def fake(url: str):
        if "titles=Clique&" in url:
            return {"query": {"pages": {"1": {"ns": 0, "title": "Clique", "pageprops": {"disambiguation": ""}}}}}
        return {"query": {"pages": {"2": {"ns": 0, "title": "Clique problem"}}}}
    title, _ = pm.Fetcher(delay=0, opener=fake).wikipedia_article(["Clique", "Clique problem"])
    assert title == "Clique problem"


def test_queries_file_names_real_problems(data):
    import yaml
    overrides = yaml.safe_load((ROOT / "prominence" / "queries.yaml").read_text(encoding="utf-8"))
    assert set(overrides) <= set(data.problems)
    for entry in overrides.values():
        assert set(entry) <= {"phrases", "wikipedia", "why"}


def test_front_page_groups_by_category_in_prominence_order(data, tmp_path):
    signals = ROOT / "prominence" / "signals.yaml"
    site = build(data, derive(data), tmp_path, signals_path=signals)
    score = {pid: r["score"] for pid, r in pm.scores(data, pm.load_signals(signals)).items()}
    cats = site["categories"]
    assert [c["id"] for c in cats][0] == "graph"
    assert sum(c["count"] for c in cats) == len(data.problems)
    for c in cats:
        got = [score[e["id"]] for e in c["problems"]]
        assert got == sorted(got, reverse=True)
        assert c["top"] == c["problems"][:FRONT_PAGE_TOP]
        assert all(e["category"] == c["id"] for e in c["problems"])
    # the search list stays complete and alphabetical
    names = [e["name"].lower() for e in site["index"]]
    assert names == sorted(names) and len(names) == len(data.problems)


def test_site_reveals_nothing_about_prominence(data, tmp_path):
    """Serge, 21 November 2026: no scores, ranks or mention of prominence on the site."""
    import json
    site = build(data, derive(data), tmp_path, signals_path=ROOT / "prominence" / "signals.yaml")
    text = json.dumps(site).lower()
    assert text.find("prominen") == -1  # (find, not "in": pytest would diff the whole text)
    templates = ROOT / "site" / "src"
    for f in list(templates.rglob("*.njk")) + list(templates.rglob("*.css")) + list(templates.rglob("*.js")):
        assert "prominen" not in f.read_text(encoding="utf-8").lower(), f
