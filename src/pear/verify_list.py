"""The list of what still has to be read or checked (docs/to-verify.md).

Serge, 22 November 2026: results entered from abstracts or titles were approved, with the
request to "keep a record of what needs to be read/verified". This module writes that record
from the data, so it cannot go stale: `python -m pear verify-list` regenerates it, and a test
fails when the committed file differs from the data.

Sections:
1. results whose paper was not read in full (only its abstract or title);
2. results accepted on Serge's confirmation without our reading the paper;
3. papers and results marked unverified;
4. every `TODO(verify)` marker in the data;
5. classic results accepted from attestations (rule 2), for completeness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

METADATA_LABELS = {"Abstract": "abstract", "Title": "title"}
MARKER = "TODO(verify)"
HEADER = """# What still needs reading or checking

Generated from `data/` by `python -m pear verify-list`; do not edit by hand (a test checks that this file matches the data). Kept at Serge's request of 22 November 2026: results entered from abstracts or titles are approved, but their papers still have to be read.

Papers we tried and failed to read, and that have no record yet, are listed in the research notes (`unreachable/` ledger), not here.
"""


def _load(data_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir.rglob("*.yaml")):
        rel = path.relative_to(data_dir).as_posix()
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        if isinstance(doc, dict):
            out[rel] = doc
    return out


def _walk(node: Any, path: str = ""):
    """Yield (yaml path, value) for every node."""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def _paper_sources(doc: dict[str, Any]):
    for ypath, node in _walk(doc):
        if isinstance(node, dict) and "paper" in node and isinstance(node.get("paper"), str) and (
                "statements" in node or "attested_by" in node or "confirmed_by" in node):
            yield ypath, node


def _paper_ref(papers: dict[str, dict[str, Any]], pid: str) -> str:
    p = papers.get(pid)
    if p is None:
        return f"`{pid}` (no paper file)"
    links = []
    for vid, v in (p.get("versions") or {}).items():
        doi = v.get("doi")
        url = v.get("url")
        arxiv = v.get("arxiv")
        where = v.get("venue") or (f"arXiv:{arxiv}" if arxiv else vid)
        if doi:
            links.append(f"[{where}](https://doi.org/{doi})")
        elif arxiv:
            links.append(f"[{where}](https://arxiv.org/abs/{arxiv})")
        elif url:
            links.append(f"[{where}]({url})")
        else:
            links.append(str(where))
    return f"{p.get('title', pid)} ({'; '.join(links)})"


def _record_id(rel: str, doc: dict[str, Any]) -> str:
    return str(doc.get("id") or rel.rsplit("/", 1)[-1].removesuffix(".yaml"))


def _approved(doc: dict[str, Any]) -> str:
    review = doc.get("review") or {}
    if review.get("approved_by"):
        return f"approved {review.get('date')}"
    return "not yet approved"


def _snippet(text: str, width: int = 240) -> str:
    text = " ".join(str(text).split())
    i = text.find(MARKER)
    if len(text) <= width:
        return text
    start = max(0, i - width // 2)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def build_list(data_dir: Path) -> str:
    docs = _load(data_dir)
    papers = {d.get("id"): d for rel, d in docs.items() if rel.startswith("papers/")}
    unread, confirmed, attested, unverified, markers = [], [], [], [], []

    for rel, doc in docs.items():
        rid = _record_id(rel, doc)
        kind = rel.split("/", 1)[0]
        for ypath, src in _paper_sources(doc):
            where = f"`{rid}`" + (f" ({ypath})" if ypath not in ("source", "") else "")
            ref = _paper_ref(papers, src["paper"])
            labels = [str((s or {}).get("statement", "")) for s in (src.get("statements") or {}).values()]
            if labels and all(lbl in METADATA_LABELS for lbl in labels):
                basis = " and ".join(sorted({METADATA_LABELS[lbl] for lbl in labels}))
                unread.append((kind, where, basis, ref, _approved(doc)))
            elif not labels and src.get("confirmed_by"):
                c = src["confirmed_by"]
                confirmed.append((kind, where, f"{c.get('by')}, {c.get('date')}", ref))
            elif not labels and src.get("attested_by"):
                attested.append((kind, where, len(src["attested_by"]), ref))
        if doc.get("unverified") is True:
            unverified.append((kind, f"`{rid}`", doc.get("title") or ""))
        for ypath, node in _walk(doc):
            if isinstance(node, str) and MARKER in node:
                markers.append((kind, f"`{rid}`", ypath, _snippet(node)))

    out = [HEADER]
    out.append(f"\n## 1. Entered from an abstract or title only ({len(unread)})\n")
    out.append("Read the paper; record the theorem; check the bound, the problem version, randomness and space; drop the `TODO(verify)` markers.\n")
    out.append("| Record | Based on | Paper | Approval |\n| --- | --- | --- | --- |")
    for kind, where, basis, ref, appr in sorted(unread):
        out.append(f"| {where} | {basis} | {_cell(ref)} | {appr} |")
    out.append(f"\n## 2. Entered on Serge's confirmation, paper not read ({len(confirmed)})\n")
    if confirmed:
        out.append("| Record | Confirmed by | Paper |\n| --- | --- | --- |")
        for kind, where, by, ref in sorted(confirmed):
            out.append(f"| {where} | {by} | {_cell(ref)} |")
    else:
        out.append("None.")
    out.append(f"\n## 3. Marked unverified ({len(unverified)})\n")
    if unverified:
        out.append("Shown in Details only, never in the Overview.\n")
        for kind, rid, what in sorted(unverified):
            out.append(f"- {kind[:-1]} {rid}" + (f": {_cell(str(what))}" if what else ""))
    else:
        out.append("None.")
    out.append(f"\n## 4. `TODO(verify)` markers ({len(markers)})\n")
    out.append("| Record | Field | Text |\n| --- | --- | --- |")
    for kind, rid, ypath, text in sorted(markers):
        out.append(f"| {rid} | `{ypath}` | {_cell(text)} |")
    out.append(f"\n## 5. Classic results accepted from attestations ({len(attested)})\n")
    out.append("Rule 2 accepts these without reading the paper (at least three independent sources each). Listed for completeness.\n")
    for kind, where, n, ref in sorted(attested):
        out.append(f"- {where}: {n} attestations; {_cell(ref)}")
    return "\n".join(out) + "\n"


def write_list(data_dir: Path, out: Path) -> str:
    text = build_list(data_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return text
