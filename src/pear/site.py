"""Page data for the static site (HANDOFF step 7, docs/DESIGN.md).

`python -m pear site` validates the data, runs the derivation engine and writes

- build/site/site.json: everything the Eleventy templates need, one page object per problem;
- build/site/entries/<folder>/<id>.json: every entry as JSON (the site's "JSON" links),
  problems with their kept results.

Text fields keep their inline TeX ($...$); the templates typeset it with KaTeX at build time.
Bounds are TeX strings without dollars. Nothing here decides what is best: that is the
derivation engine's job (rulebook); this module only arranges its output for reading.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any

from .bounds import display, ostar, parse_bound, parse_expr, render
from .bounds.expr import Add, Div, Mul, Node, Num, Pow, Var, variables
from .derive import Derivation, node_key, to_json
from .schema import (
    Algorithm,
    FolkloreSource,
    Implementation,
    Paper,
    PaperSource,
    Problem,
    Reduction,
    SharedParameter,
    SharedParameterRef,
)
from .validate import Dataset

# The pilot problems of Phase 1 (HANDOFF.md), in the order the brief lists them.
PILOT = [
    "Vertex Cover", "Independent Set", "Clique", "Set Cover", "Hitting Set", "SAT", "#3-SAT",
    "3-Coloring", "Hamiltonian Cycle", "Dominating Set", "Connected Dominating Set", "Subset Sum",
]

VERSION_LABELS = {"decision": "Decision", "optimisation": "Optimisation", "search": "Search", "weighted": "Weighted"}
REDUCTION_TYPES = {
    "polytime-deterministic": "deterministic polynomial time",
    "polytime-randomized": "randomized polynomial time",
    "serf": "subexponential reduction family (SERF)",
}
NUMBER_WORDS = {1: "one call", 2: "two calls", 3: "three calls"}


# --- small helpers -------------------------------------------------------------------------


def _join(words: list[str], last: str = "and") -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + f" {last} " + words[-1]


def _sentence_fragment(text: str) -> str:
    """'Binary search on $k$ and self-reducibility.' -> 'binary search on $k$ and self-reducibility'"""
    text = text.strip().rstrip(".")
    return text[:1].lower() + text[1:] if text[:1].isupper() and not text[1:2].isupper() else text


def version_label(vid: str) -> str:
    return VERSION_LABELS.get(vid, vid.replace("-", " ").capitalize())


def node_versions(node: str) -> list[str]:
    return node.split("+")


# --- papers and references ------------------------------------------------------------------


def paper_version_label(paper: Paper, vid: str) -> str:
    """How a cited paper version is named next to a statement: 'arXiv v4', 'STACS 2024', 'book'."""
    v = paper.versions[vid]
    if v.arxiv:
        m = re.search(r"v(\d+)$", v.arxiv)
        return f"arXiv v{m.group(1)}" if m else "arXiv"
    if v.venue:
        m = re.search(r"\(([A-Z][A-Za-z]*\s\d{4})\)", v.venue)
        if m:
            return m.group(1)
    return {"technical-report": "technical report", "conference": "conference version",
            "journal": "journal version", "preprint": "preprint"}.get(v.kind, v.kind)


def paper_links(paper: Paper) -> list[dict[str, Any]]:
    links = []
    for vid, v in paper.versions.items():
        if v.arxiv:
            links.append({"label": f"arXiv:{v.arxiv}", "url": f"https://arxiv.org/abs/{v.arxiv}", "open": True})
        if v.doi:
            links.append({"label": f"doi:{v.doi}", "url": f"https://doi.org/{v.doi}", "open": v.open_access and not v.url})
        if v.url:
            links.append({"label": "open access" if v.open_access else "publisher", "url": v.url, "open": v.open_access})
    seen, out = set(), []
    for link in links:
        if link["url"] not in seen:
            seen.add(link["url"])
            out.append(link)
    return out


def paper_reference(paper: Paper) -> dict[str, Any]:
    versions = []
    for vid, v in sorted(paper.versions.items(), key=lambda kv: kv[1].year):
        where = v.venue or ({"preprint": "Preprint"}.get(v.kind) or v.kind.replace("-", " ").capitalize())
        if v.arxiv and not v.venue:
            where = f"arXiv:{v.arxiv}"
        versions.append(f"{where}, {v.year}" if str(v.year) not in where else where)
    return {
        "id": paper.id,
        "authors": _join(paper.authors),
        "title": paper.title,
        "versions": versions,
        "links": paper_links(paper),
        "unverified": paper.unverified,
        "year": min(v.year for v in paper.versions.values()),
    }


def short_citation(paper: Paper) -> str:
    """'Karp 1972', 'Chen and Kanj 2001', 'Chen et al. 2006'."""
    surnames = [a.split()[-1] for a in paper.authors]
    who = surnames[0] if len(surnames) == 1 else " and ".join(surnames) if len(surnames) == 2 else f"{surnames[0]} et al."
    return f"{who} {min(v.year for v in paper.versions.values())}"


class References:
    """Numbers papers in order of first citation on a page."""

    def __init__(self, data: Dataset):
        self.data = data
        self.order: list[str] = []

    def cite(self, paper_id: str) -> int:
        if paper_id not in self.order:
            self.order.append(paper_id)
        return self.order.index(paper_id) + 1

    def source(self, src: PaperSource | FolkloreSource | None) -> dict[str, Any]:
        """A citation: footnote number(s), statement labels and the source's note."""
        if src is None:
            return {"refs": [], "statements": [], "folklore": False, "note": None}
        if isinstance(src, FolkloreSource):
            refs, statements = [], []
            if src.reference is not None:
                refs.append(self.cite(src.reference.paper))
                paper = self.data.papers[src.reference.paper]
                statements.append(f"{src.reference.statement}, {paper_version_label(paper, src.reference.version)}")
            return {"refs": refs, "statements": statements, "folklore": True, "note": src.note}
        paper = self.data.papers[src.paper]
        statements = []
        for vid, st in src.statements.items():
            page = f", p. {st.page}" if st.page is not None else ""
            statements.append(f"{st.statement}, {paper_version_label(paper, vid)}{page}")
        return {"refs": [self.cite(src.paper)], "statements": statements, "folklore": False, "note": src.note}

    def listing(self) -> list[dict[str, Any]]:
        return [{"n": i + 1, **paper_reference(self.data.papers[pid])} for i, pid in enumerate(self.order)]


# --- parameters -------------------------------------------------------------------------------


def parameter_info(data: Dataset, problem: Problem) -> list[dict[str, Any]]:
    """Every symbol a bound can use, in reading order: problem parameters, then n, m, N,
    then shared parameters; with a short name for headings ('solution size')."""
    shared: dict[str, SharedParameter] = data.entries["parameters"]  # type: ignore[assignment]
    local, common = [], []
    for symbol, entry in problem.parameters.items():
        if isinstance(entry, SharedParameterRef):
            p = shared[entry.shared]
            meaning = p.name.lower() + (f" of {entry.of}" if entry.of else "")
            common.append({"symbol": symbol, "short": meaning, "meaning": meaning, "definition": p.definition, "shared": p.id})
        else:
            short = entry.meaning.split(":")[0].strip()
            short = re.sub(r"^the ", "", short)
            local.append({"symbol": symbol, "short": short, "meaning": entry.meaning, "definition": None, "shared": None})
    sizes = [{"symbol": "n", "short": problem.objects.n, "meaning": problem.objects.n}]
    if problem.objects.m is not None:
        sizes.append({"symbol": "m", "short": problem.objects.m, "meaning": problem.objects.m})
    sizes.append({"symbol": "N", "short": "input size", "meaning": problem.objects.N})
    for s in sizes:
        s.update({"definition": None, "shared": None})
    out = local + sizes + common
    for p in out:
        p["tex"] = render(Var(p["symbol"]))
    return out


# --- properties in words ------------------------------------------------------------------------


def property_words(row: dict[str, Any], alg: Algorithm, chain_randomized: bool) -> dict[str, Any]:
    p = row["properties"]
    words, short = [], []
    if p["deterministic"]:
        words.append("deterministic")
        short.append("det")
    else:
        err = alg.properties.randomized
        if not isinstance(err, bool) and not chain_randomized:
            kind = {"one-sided": "one-sided error", "two-sided": "two-sided error", "las-vegas": "Las Vegas"}[err.error]
            words.append(f"randomized ({kind})")
        else:
            words.append("randomized")
        short.append("rand")
    words.append("in polynomial space" if p["polynomial_space"] else "in exponential space")
    short.append("poly space" if p["polynomial_space"] else "exp space")
    if not p["constructive"]:
        words.append("non-constructive")
        short.append("non-constr")
    if p["fast_matrix_multiplication"]:
        words.append("using fast matrix multiplication")
        short.append("FMM")
    elif p["algebraic"]:
        words.append("algebraic")
        short.append("alg")
    if p["quantum"]:
        words.append("quantum")
        short.append("quantum")
    if p["lean_verified"]:
        short.append("Lean")
    return {"words": words, "sentence": _join(words), "short": ", ".join(short)}


FLAG_TEXT = {
    "unverified": "from an unrefereed source; shown in Details only",
    "given-tree-decomposition": "a tree decomposition of width $tw$ is given with the input",
    "long-chain": "long derivation chain",
    "adaptive-sizes": "Turing reduction: every call assumed to have the largest size",
    "claimed-refuted-hypothesis": "conditional on a hypothesis claimed to be refuted",
    "site-written-variant": "uses a reduction variant written by the site",
}


# --- history ------------------------------------------------------------------------------------


def _value(node: Node, x: float) -> float | None:
    if isinstance(node, Num):
        return float(node.value)
    if isinstance(node, Var):
        return x
    if isinstance(node, Add):
        vals = [_value(t, x) for _, t in node.terms]
        return None if None in vals else sum(s * v for (s, _), v in zip(node.terms, vals))  # type: ignore[misc]
    if isinstance(node, Mul):
        out = 1.0
        for f in node.factors:
            v = _value(f, x)
            if v is None:
                return None
            out *= v
        return out
    if isinstance(node, Div):
        a, b = _value(node.num, x), _value(node.den, x)
        return None if a is None or not b else a / b
    if isinstance(node, Pow):
        a, b = _value(node.base, x), _value(node.exp, x)
        return None if a is None or b is None or a <= 0 else a**b
    return None


def single_base(expr: Node) -> float | None:
    """c for an O* expression of the form c^{a x} in one variable x, else None."""
    if len(variables(expr)) != 1 or not isinstance(expr, Pow):
        return None
    v0, v1, v2 = (_value(expr, x) for x in (0.0, 1.0, 2.0))
    if v0 is None or v1 is None or v2 is None or not math.isclose(v0, 1.0):
        return None
    if not math.isclose(v2, v1 * v1, rel_tol=1e-12):
        return None
    return v1


def history(rows: list[dict[str, Any]], bases: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    """Improvements of the best base over the years, per single parameter, from the results
    entered so far (verified, non-quantum). Polynomial factors ignored."""
    out: dict[str, list[dict[str, Any]]] = {}
    for param in sorted({r["parameters"][0] for r in rows if len(r["parameters"]) == 1}):
        cands = [
            r for r in rows
            if r["parameters"] == [param] and r["id"] in bases and r["year"] is not None
            and "unverified" not in r["flags"] and not r["properties"]["quantum"]
        ]
        cands.sort(key=lambda r: (r["year"], bases[r["id"]]))
        steps: list[dict[str, Any]] = []
        for r in cands:
            if not steps or bases[r["id"]] < steps[-1]["base"] - 1e-12:
                steps.append({"year": r["year"], "base": bases[r["id"]], "row": r["id"], "shown": r["shown"],
                              "refs": r["refs"], "derived": r["origin"] == "derived"})
        if steps:
            out[param] = steps
    return out


# --- one problem page ---------------------------------------------------------------------------


def chain_items(data: Dataset, d: Derivation, row: dict[str, Any], refs: References, problem: Problem) -> list[dict[str, Any]]:
    """The numbered chain under "Where this bound comes from"."""
    alg: Algorithm = data.entries["algorithms"][row["algorithm"]]  # type: ignore[assignment]
    src_problem = data.problems[alg.problem]
    ctx = d.contexts[alg.problem]
    start = display(parse_bound(alg.bound.as_stated, src_problem.symbols()), ctx)
    current = set(variables(ostar(parse_bound(alg.bound.as_stated, src_problem.symbols()), ctx).expr))
    items = [{
        "kind": "start",
        "problem": src_problem.name,
        "problem_id": src_problem.id,
        "shown": start.tex,
        "proved_for": version_label(alg.proved_for).lower(),
        **refs.source(alg.source),
    }]
    for step in row["chain"]:
        if step["kind"] == "reduction":
            red: Reduction = data.entries["reductions"].get(step["id"].split("~")[0])  # type: ignore[assignment]
            frm = data.problems[step["from"].split(":")[0]]
            to = data.problems[step["to"].split(":")[0]]
            symbols = frm.symbols() | to.symbols()
            pmap = []
            stored = red.parameter_map if red is not None else {}
            keys = [k for k in stored if k in step["parameter_map"]] + [k for k in step["parameter_map"] if k not in stored]
            for k in keys:
                v = step["parameter_map"][k]
                try:
                    tex = render(parse_expr(v, symbols))
                except Exception:  # keep the stored text if it does not parse in this context
                    tex = v
                pmap.append(f"{render(Var(k))} \\mapsto {tex}")
            mapped: set[str] = set()
            for var in current:
                try:
                    mapped |= variables(parse_expr(step["parameter_map"].get(var, var), symbols))
                except Exception:
                    mapped.add(var)
            current = mapped
            calls = red.calls if red is not None else 1
            items.append({
                "kind": "reduction",
                "from": frm.name, "from_id": frm.id, "to": to.name, "to_id": to.id,
                "type": REDUCTION_TYPES.get(step["type"] or "", step["type"]),
                "calls": NUMBER_WORDS.get(calls, f"{calls} calls") if isinstance(calls, int) else calls,
                "map": ", \\; ".join(pmap),
                "note": step["note"],
                **(refs.source(red.source) if red is not None else refs.source(None)),
            })
        elif step["kind"] == "special-case":
            general, special = step["id"].rsplit(":", 1)[1].split(">")
            items.append({
                "kind": "special-case",
                "general": version_label(general).lower(),
                "special": version_label(special).lower(),
            })
        elif step["kind"] == "projection":
            label = step["id"].split(":", 1)[1]
            if label == "drop-subtractions":
                items.append({"kind": "projection", "text": "Subtracted terms dropped (each is at most the term it is subtracted from)."})
            else:
                mentions = lambda c, v: re.search(rf"(?<![A-Za-z]){re.escape(v)}(?![A-Za-z])", c) is not None  # noqa: E731
                used = [
                    c.constraint for c in problem.constraints
                    if mentions(c.constraint, label) and any(mentions(c.constraint, v) for v in current - {label})
                ]
                items.append({"kind": "projection", "onto": render(Var(label)), "constraints": used})
                current = {label}
    items.append({"kind": "end", "problem": problem.name, "shown": row["shown"]})
    return items


def problem_page(data: Dataset, d: Derivation, derived: dict[str, Any], pid: str) -> dict[str, Any]:
    problem = data.problems[pid]
    refs = References(data)
    params = parameter_info(data, problem)
    order = {p["symbol"]: i for i, p in enumerate(params)}
    by_symbol = {p["symbol"]: p for p in params}
    nodes_rows: dict[str, list[dict]] = derived["problems"].get(pid, {})
    overview: dict[str, list[dict]] = derived["overview"].get(pid, {})

    def enrich(row: dict[str, Any]) -> dict[str, Any]:
        alg: Algorithm = data.entries["algorithms"][row["algorithm"]]  # type: ignore[assignment]
        chain_randomized = any(s["type"] in ("polytime-randomized",) for s in row["chain"])
        src = refs.source(alg.source)
        out = dict(row)
        out["refs"] = src["refs"]
        out["statements"] = src["statements"]
        out["source_note"] = src["note"]
        out["props"] = property_words(row, alg, chain_randomized)
        out["proved_for"] = version_label(alg.proved_for).lower()
        out["proved_for_problem"] = None if alg.problem == pid else data.problems[alg.problem].name
        out["from_problem"] = None if alg.problem == pid else {"id": alg.problem, "name": data.problems[alg.problem].name}
        out["flag_text"] = [FLAG_TEXT.get(f, f) for f in row["flags"]]
        out["param_tex"] = ", ".join(by_symbol[p]["tex"] for p in row["parameters"] if p in by_symbol)
        out["param_order"] = [order.get(p, 99) for p in row["parameters"]]
        out["chain_items"] = chain_items(data, d, row, refs, problem) if row["chain"] else []
        return out

    def sort_key(r: dict[str, Any]) -> tuple:
        return (r["param_order"], r["origin"] != "direct", -(r["year"] or 0))

    # Overview first, so its citations get the low numbers.
    nodes = {}
    for node in sorted(set(nodes_rows) | {node_key(problem, v)[1] for v in problem.versions}):
        rows = nodes_rows.get(node, [])
        enriched_by_id: dict[str, dict] = {}
        groups: dict[tuple[str, ...], list[dict]] = {}
        def entry_order(entry: dict) -> list[int]:
            first = next(r for r in rows if r["id"] == entry["cite"][0])
            return [order.get(x, 99) for x in first["parameters"]]

        for entry in sorted(overview.get(node, []), key=entry_order):
            cited = []
            for rid in entry["cite"]:
                row = next(r for r in rows if r["id"] == rid)
                enriched_by_id[rid] = enrich(row)
                cited.append(enriched_by_id[rid])
            params_key = tuple(cited[0]["parameters"])
            groups.setdefault(params_key, []).append({"cite": cited, "year": entry["year"], "members": entry["members"]})
        for row in rows:
            if row["id"] not in enriched_by_id:
                enriched_by_id[row["id"]] = enrich(row)
        detail_rows = sorted(enriched_by_id.values(), key=sort_key)
        ordered_groups = sorted(groups.items(), key=lambda kv: [order.get(p, 99) for p in kv[0]])
        overview_out = []
        for key, entries in ordered_groups:
            names = [by_symbol[p]["short"] for p in key if p in by_symbol]
            overview_out.append({
                "parameters": list(key),
                "heading": "By " + _join(names),
                "symbols_tex": [by_symbol[p]["tex"] for p in key if p in by_symbol],
                "entries": entries,
            })
        bases = {}
        for res in d.results.get((pid, node), []):
            b = single_base(ostar(res.bound, d.contexts[pid]).expr)
            if b is not None:
                bases[res.id] = b
        hist = history(detail_rows, bases)
        members = node_versions(node)
        group = next((g for g in problem.shared_bounds if sorted(g.versions) == sorted(members)), None)
        note = None
        if group is not None:
            names = _join([version_label(v).lower() for v in problem.versions if v in members])
            note = (f"The {names} versions are equivalent up to polynomial factors "
                    f"({_sentence_fragment(group.because)}) and share these bounds; "
                    "each result names the version its paper proved.")
        else:
            specials = [w for v in members if v in problem.versions for w in problem.versions[v].generalises]
            if specials:
                names = _join([version_label(w).lower() for w in specials])
                note = f"Bounds for this version also hold for its special case ({names}), never the reverse."
        nodes[node] = {
            "overview": overview_out,
            "rows": detail_rows,
            "note": note,
            "history": {
                p: {"param_tex": by_symbol[p]["tex"], "name": by_symbol[p]["short"], "steps": steps}
                for p, steps in hist.items() if p in by_symbol
            },
        }

    versions = []
    for vid, v in problem.versions.items():
        versions.append({
            "id": vid,
            "label": version_label(vid),
            "kind": v.kind,
            "input": v.input,
            "question": v.question,
            "goal": v.goal,
            "node": node_key(problem, vid)[1],
            "default": vid == problem.default_version,
        })

    complexity_src = refs.source(problem.complexity.source)
    reductions = reduction_lists(data, problem, refs)
    related = [
        {"id": r.problem, "name": data.problems[r.problem].name, "relation": r.relation}
        for r in problem.related if r.problem in data.problems
    ]
    impls = implementations(data, problem)
    complexity_paper = (
        data.papers[problem.complexity.source.paper]
        if isinstance(problem.complexity.source, PaperSource) else None
    )
    return {
        "id": pid,
        "name": problem.name,
        "aliases": problem.aliases,
        "category": problem.category,
        "complexity": {
            "class": problem.complexity.class_,
            "short": short_citation(complexity_paper) if complexity_paper else None,
            **complexity_src,
        },
        "parameters": params,
        "constraints": [{"tex": c.constraint, "because": c.because} for c in problem.constraints],
        "versions": versions,
        "default_version": problem.default_version,
        "nodes": nodes,
        "reductions": reductions,
        "related": related,
        "implementations": impls,
        "lean": problem.lean.model_dump(mode="json"),
        "references": refs.listing(),
        "review": problem.review.model_dump(mode="json"),
    }


def reduction_lists(data: Dataset, problem: Problem, refs: References) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"from": [], "to": []}
    for rid, red in sorted(data.entries["reductions"].items()):
        assert isinstance(red, Reduction)
        if problem.id not in (red.from_.problem, red.to.problem):
            continue
        frm, to = data.problems[red.from_.problem], data.problems[red.to.problem]
        symbols = frm.symbols() | to.symbols()
        pmap = []
        for k, v in red.parameter_map.items():
            try:
                tex = render(parse_expr(v, symbols))
            except Exception:
                tex = v
            pmap.append({"from": render(Var(k)), "to": tex, "identity": tex == render(Var(k))})
        entry = {
            "id": rid,
            "from": {"id": frm.id, "name": frm.name, "version": version_label(red.from_.version).lower()},
            "to": {"id": to.id, "name": to.name, "version": version_label(red.to.version).lower()},
            "type": REDUCTION_TYPES[red.type],
            "calls": red.calls,
            "time": red.time,
            "map": pmap,
            "map_tex": ", \\; ".join(f"{p['from']} \\mapsto {p['to']}" for p in pmap),
            "changed_tex": ", \\; ".join(f"{p['from']} \\mapsto {p['to']}" for p in pmap if not p["identity"]),
            "variants": [v.note for v in red.variants],
            "formal": red.formal.status,
            **refs.source(red.source),
        }
        # "From X": reductions into this problem from X; "To Y": from this problem to Y
        if red.to.problem == problem.id and red.from_.problem != problem.id:
            out["from"].append(entry)
        if red.from_.problem == problem.id:
            out["to"].append(entry)
    return out


def implementations(data: Dataset, problem: Problem) -> dict[str, Any] | None:
    if problem.implementations is None:
        return None
    items = []
    for iid in problem.implementations.ranked:
        impl: Implementation = data.entries["implementations"][iid]  # type: ignore[assignment]
        solves = next(s for s in impl.solves if s.problem == problem.id and s.exact)
        items.append({
            "id": impl.id,
            "name": impl.name,
            "url": impl.url,
            "language": impl.language,
            "licence": impl.licence,
            "versions": [version_label(v).lower() for v in solves.versions] or [version_label(problem.default_version).lower()],
            "versions_text": _join([version_label(v).lower() for v in solves.versions] or [version_label(problem.default_version).lower()]),
            "note": solves.note,
            "facts": [
                {"fact": f.fact, "source": f.source, "as_of": f.as_of.isoformat() if f.as_of else None,
                 "urls": re.findall(r"https?://[^\s;)]+", f.source),
                 "label": re.sub(r"https?://\S+\s*", "", f.source).strip(" ;").strip("()") or None}
                for f in impl.facts
            ],
        })
    return {"as_of": problem.implementations.as_of.isoformat(), "note": problem.implementations.note, "items": items}


# --- the whole site -------------------------------------------------------------------------------


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("#", "sharp-")).strip("-")


def build(data: Dataset, d: Derivation, out_dir: Path) -> dict[str, Any]:
    derived = to_json(data, d)
    pages = {pid: problem_page(data, d, derived, pid) for pid in sorted(data.problems)}
    index = []
    for name in PILOT:
        pid = next((p for p, prob in data.problems.items() if prob.name == name), None)
        if pid is None:
            index.append({"name": name, "id": None, "slug": _slug(name), "bounds": []})
            continue
        page = pages[pid]
        default_node = node_key(data.problems[pid], data.problems[pid].default_version)[1]
        bounds = []
        for group in page["nodes"].get(default_node, {}).get("overview", []):
            for entry in group["entries"]:
                r = entry["cite"][0]
                bounds.append({"shown": r["shown"], "params": group["symbols_tex"], "derived": r["origin"] == "derived",
                               "deterministic": r["properties"]["deterministic"], "year": entry["year"]})
        index.append({"name": name, "id": pid, "slug": pid, "bounds": bounds})
    others = [pid for pid in sorted(pages) if data.problems[pid].name not in PILOT]
    for pid in others:
        index.append({"name": data.problems[pid].name, "id": pid, "slug": pid, "bounds": []})
    site = {
        "generated": dt.date.today().isoformat(),
        "rulebook_version": derived["rulebook_version"],
        "index": index,
        "pages": pages,
        "problem_names": {pid: p.name for pid, p in data.problems.items()},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "site.json").write_text(json.dumps(site, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_entries(data, derived, out_dir / "entries")
    return site


def write_entries(data: Dataset, derived: dict[str, Any], out: Path) -> None:
    """One JSON file per entry, as in the data (CC0), problems with their kept results."""
    for folder, entries in data.entries.items():
        for eid, entry in entries.items():
            obj = entry.model_dump(mode="json", by_alias=True, exclude_defaults=False)
            if folder == "problems":
                obj["results"] = derived["problems"].get(eid, {})
                obj["overview"] = derived["overview"].get(eid, {})
                obj["rulebook_version"] = derived["rulebook_version"]
            path = out / folder / f"{eid}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


__all__ = ["build", "single_base", "history", "paper_version_label", "parameter_info"]
