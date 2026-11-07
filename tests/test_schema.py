"""Validator tests: the fictional fixture set passes, and each rule catches its case."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import pytest

from pear.__main__ import main
from pear.validate import read_data_dir, validate_dir, validate_raw

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "valid"

PA = ("problems", "problem-a")
PB = ("problems", "problem-b")
PAPER = ("papers", "author-example-2000")
ALG = ("algorithms", "problem-a--k--author-example-2000")
RED = ("reductions", "problem-b--to--problem-a")
HYP_H = ("hypotheses", "hypothesis-h")
HYP_G = ("hypotheses", "hypothesis-g")
LB = ("lower-bounds", "problem-a--n--author-example-2000")
PARAM = ("parameters", "example-width")
CONST = ("constants", "omega")


@pytest.fixture(scope="module")
def fixture_raw() -> tuple[dict[str, dict[str, Any]], Any]:
    raw, redirects, issues = read_data_dir(FIXTURES)
    assert issues == []
    return raw, redirects


def issues_after(fixture_raw, target: tuple[str, str], change: Callable[[dict], None], redirects=None):
    raw, base_redirects = fixture_raw
    raw = copy.deepcopy(raw)
    change(raw[target[0]][target[1]])
    _, issues = validate_raw(raw, base_redirects if redirects is None else redirects)
    return [str(i) for i in issues]


def test_fixtures_are_valid():
    data, issues = validate_dir(FIXTURES)
    assert [str(i) for i in issues] == []
    assert len(data.problems) == 2


def test_repository_data_is_valid():
    _, issues = validate_dir(ROOT / "data")
    assert [str(i) for i in issues] == []


def test_cli_exit_codes(tmp_path, capsys):
    assert main(["validate", str(FIXTURES)]) == 0
    (tmp_path / "stray.yaml").write_text("x: 1\n")
    assert main(["validate", str(tmp_path)]) == 1
    assert "unexpected file" in capsys.readouterr().out


def _set(path: str, value: Any) -> Callable[[dict], None]:
    *head, last = path.split(".")

    def change(entry: dict) -> None:
        node = entry
        for key in head:
            node = node[int(key)] if isinstance(node, list) else node[key]
        if value is _DELETE:
            del node[last]
        else:
            node[last] = value

    return change


_DELETE = object()

CASES = [
    # per-file schema
    ("unknown field", PA, _set("colour", "red"), "Extra inputs are not permitted"),
    ("missing field", PA, _set("category", _DELETE), "category: Field required"),
    ("category off list", PA, _set("category", "music"), "category"),
    ("bad id pattern", PA, _set("id", "Problem_A"), "id: String should match pattern"),
    ("id differs from file", PB, _set("id", "problem-c"), "does not match the file name"),
    ("parameter redefines n", PB, _set("parameters.n", {"meaning": "x"}), "must not redefine"),
    ("unknown default version", PA, _set("default_version", "counting"), "default_version 'counting'"),
    ("decision without question", PB, _set("versions.decision.question", _DELETE), "has a question and no goal"),
    ("optimisation with question", PA, _set("versions.optimisation.question", "Q?"), "has a goal and no question"),
    ("shared_bounds unknown version", PA, _set("shared_bounds.0.versions", ["decision", "nope"]), "unknown version 'nope'"),
    (
        "overlapping shared_bounds",
        PA,
        _set("shared_bounds", [{"versions": ["decision", "search"], "because": "x"}, {"versions": ["search", "optimisation"], "because": "y"}]),
        "more than one shared_bounds group",
    ),
    ("constraint without relation", PA, _set("constraints.0.constraint", "k n"), "constraints.0.constraint"),
    ("constraint without justification", PA, _set("constraints.0.because", _DELETE), "because: Field required"),
    ("poly_bounded not boolean", PB, _set("parameters.t.poly_bounded", "sometimes"), "poly_bounded"),
    ("generalises cycle", PA, _set("versions.optimisation.generalises", ["weighted"]), "cycle"),
    ("review without date", PB, _set("review", {"approved_by": "Serge Gaspers"}), "both approved_by and date"),
    ("review by someone else", PB, _set("review", {"approved_by": "Someone Else", "date": "2026-11-07"}), "review.approved_by"),
    ("reduction type not agreed", RED, _set("type", "parameterized"), "type: Input should be"),
    ("call_sizes with one call", RED, _set("call_sizes", "all of size n"), "call_sizes only applies"),
    ("formal proof without link", RED, _set("formal", {"status": "proved"}), "needs a prover and a link"),
    ("fmm without algebraic", ALG, _set("properties.fast_matrix_multiplication", True), "sub-tag of algebraic"),
    ("missing property", ALG, _set("properties.algebraic", _DELETE), "algebraic: Field required"),
    ("unknown notation", ALG, _set("bound.notation", "Theta"), "bound.notation"),
    ("unknown randomized error", ALG, _set("properties.randomized", {"error": "sometimes"}), "randomized"),
    ("open access without link", PAPER, _set("versions.arxiv-v1.arxiv", _DELETE), "needs a url, arxiv id or doi"),
    ("claimed refuted without source", HYP_G, _set("status_sources", []), "needs at least one status source"),
    # across files
    ("unknown shared parameter", PA, _set("parameters.w", {"shared": "nope"}), "unknown shared parameter 'nope'"),
    ("shared parameter symbol mismatch", PARAM, _set("symbol", "z"), "uses the symbol 'z'"),
    ("unknown related problem", PA, _set("related.0.problem", "nope"), "unknown problem 'nope'"),
    ("related to itself", PB, _set("related", [{"problem": "problem-b", "relation": "variant"}]), "related to itself"),
    ("unknown problem", ALG, _set("problem", "nope"), "unknown problem 'nope'"),
    ("unknown proved_for version", ALG, _set("proved_for", "counting"), "has no version 'counting'"),
    ("bound uses undefined parameter", ALG, _set("bound.parameters", ["k", "tw"]), "parameter 'tw' is not defined"),
    ("unknown hypothesis", ALG, _set("conditional_on", ["eth"]), "unknown hypothesis 'eth'"),
    ("unknown paper", ALG, _set("source.paper", "nope"), "unknown paper 'nope'"),
    ("unknown paper version", ALG, _set("source.statements.journal", {"statement": "Theorem 1"}), "has no version 'journal'"),
    ("no open-access statement", ALG, _set("source.statements", {"conference": {"statement": "Theorem 2"}}), "no statement for an open-access version"),
    ("folklore reference to unknown version", RED, _set("source.reference.version", "journal"), "has no version 'journal'"),
    ("unknown reduction target version", RED, _set("to.version", "weighted-search"), "has no version 'weighted-search'"),
    ("parameter map sets unknown parameter", RED, _set("parameter_map.tw", "k"), "parameter 'tw' is not defined by problem 'problem-a'"),
    ("variant with unknown version", RED, _set("variants.0.version", "nope"), "has no version 'nope'"),
    # bound strings (bounds §1)
    ("bound with unknown variable", ALG, _set("bound.as_stated", "O(2^{x})"), "unknown variable"),
    ("bound that does not parse", ALG, _set("bound.as_stated", "O(1.5^{k}"), "unbalanced"),
    ("parameters differ from as_stated", ALG, _set("bound.parameters", ["k"]), "but as_stated uses ['k', 'n']"),
    ("notation differs from as_stated", ALG, _set("bound.notation", "O*"), "does not match the notation"),
    ("lower bound that does not parse", LB, _set("bound.as_stated", "2^{o(q)}"), "unknown variable"),
    ("reduction time that does not parse", RED, _set("time", "O(n + q)"), "time"),
    ("parameter map that does not parse", RED, _set("parameter_map.k", "k +"), "parameter_map.k"),
    ("parameter map using target-only variable", RED, _set("parameter_map.k", "w"), "unknown variable"),
    ("constraint with unknown variable", PA, _set("constraints.0.constraint", "k \\le zz"), "constraints"),
    # named constants (bounds §2)
    ("constant with unknown symbol", CONST, _set("symbol", "\\theta"), "not a named constant"),
    ("constant value not a number", CONST, _set("bounds.0.value", "n"), "is not a number"),
    ("constant without upper bound", CONST, _set("bounds.0.status", "refuted"), "needs at least one upper bound"),
    ("constant bounds cross", CONST, _set("bounds.1.value", "3"), "exceeds upper bound"),
    ("constant source paper unknown", CONST, _set("bounds.0.sources.0.paper", "nope"), "unknown paper 'nope'"),
    ("hypothesis implies itself", HYP_H, _set("implies", ["hypothesis-h"]), "cannot imply itself"),
    ("hypothesis implies unknown", HYP_H, _set("implies", ["nope"]), "unknown hypothesis 'nope'"),
    ("lower bound unknown version", LB, _set("version", "search-x"), "has no version 'search-x'"),
]


@pytest.mark.parametrize(
    ("target", "change", "expected"),
    [pytest.param(t, c, e, id=name) for name, t, c, e in CASES],
)
def test_rule(fixture_raw, target, change, expected):
    issues = issues_after(fixture_raw, target, change)
    assert any(expected in i for i in issues), issues


def test_m_is_only_defined_when_problem_has_relations(fixture_raw):
    def drop_m(problem: dict) -> None:
        del problem["objects"]["m"]

    raw, redirects = fixture_raw
    raw = copy.deepcopy(raw)
    drop_m(raw["problems"]["problem-a"])
    raw["algorithms"]["problem-a--k--author-example-2000"]["bound"]["parameters"] = ["k", "m"]
    _, issues = validate_raw(raw, redirects)
    assert any("parameter 'm' is not defined" in str(i) for i in issues)


@pytest.mark.parametrize(
    ("redirects", "expected"),
    [
        ({"problems": {"old-problem-a": "nope"}}, "redirect target 'nope' does not exist"),
        ({"problems": {"problem-b": "problem-a"}}, "shadows an existing entry"),
        ({"widgets": {}}, "unknown folder 'widgets'"),
    ],
)
def test_redirects(fixture_raw, redirects, expected):
    issues = issues_after(fixture_raw, PB, lambda e: None, redirects=redirects)
    assert any(expected in i for i in issues), issues


def test_no_follow_on_errors_for_invalid_entries(fixture_raw):
    issues = issues_after(fixture_raw, PB, _set("category", "music"))
    assert any("problem-b.yaml: category" in i for i in issues)
    assert not any("unknown problem 'problem-b'" in i for i in issues), issues


def test_wrong_extension_and_location(tmp_path):
    (tmp_path / "problems").mkdir()
    (tmp_path / "problems" / "x.yml").write_text("id: x\n")
    (tmp_path / "widgets").mkdir()
    (tmp_path / "widgets" / "y.yaml").write_text("id: y\n")
    _, issues = validate_dir(tmp_path)
    text = [str(i) for i in issues]
    assert any("use the .yaml extension" in t for t in text)
    assert any("unexpected location" in t for t in text)


def test_bound_using_a_constant_needs_its_entry(fixture_raw):
    raw, redirects = fixture_raw
    raw = copy.deepcopy(raw)
    raw["algorithms"]["problem-a--k--author-example-2000"]["bound"]["as_stated"] = "O(1.5^{k} + k n^{\\omega})"
    _, issues = validate_raw(raw, redirects)
    assert [str(i) for i in issues] == []
    del raw["constants"]["omega"]
    _, issues = validate_raw(raw, redirects)
    assert any("data/constants/omega.yaml does not exist" in str(i) for i in issues)


def test_problem_context_uses_data(fixture_raw):
    from pear.validate import problem_context

    raw, redirects = fixture_raw
    data, _ = validate_raw(copy.deepcopy(raw), redirects)
    ctx = problem_context(data, data.problems["problem-b"])
    assert not ctx.poly_bounded("t") and ctx.poly_bounded("k")
    assert ctx.constants == {"omega": (2.0, 2.5)}
    assert problem_context(data, data.problems["problem-a"]).relation("k", "n") == 1
