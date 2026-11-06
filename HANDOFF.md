# PEAR — handoff brief for the build session

Read `CLAUDE.md` first (ground rules), then `docs/PLAN.md` (what and why) and `docs/DESIGN.md` (how it looks). This file says where things stand and what to do next.

## Where things stand (6 November 2026)

- **Planning is done.** The plan covers scope, data model, derived bounds, curation, hosting, design and phases.
- **Design is chosen.** Encyclopedia look, desktop and phone; static previews in `design/preview/`, sources in `design/source/`.
- **Name**: "PEAR: Parameterized and Exact Algorithms and Reductions".
- **Setup (step 1, done)**: repo `algo-unsw/pear`; GitHub Pages first, custom domain optional; Python pipeline + Eleventy + KaTeX. Details in `docs/PLAN.md` → Hosting and implementation → Setup.
- **Not started**: repository, schema, bound language spec, rulebook spec, any data or code.
- **Drafts exist** for the bound language and chaining rules (in `docs/PLAN.md`); they must be finished **with Serge**.

## Goal of this session: Phase 1 pilot

A working static site on GitHub Pages for **12 pilot problems**, with the bound language, automatic derived bounds and the chosen design:

Vertex Cover, Independent Set, Clique, Set Cover, Hitting Set, SAT, #3-SAT, 3-Coloring, Hamiltonian Cycle, Dominating Set, Connected Dominating Set, Subset Sum.

Not in Phase 1: automated curator, approval queue, OpenAlex tracker, Lean CI, agent skill, MCP server, embedding search (simple name/alias search is enough), history charts (unless the data is already entered).

## Steps

1. **Confirm setup with Serge**: repo name, GitHub owner (user or organisation), and stack. Suggested stack, for him to accept or change:
   - Data pipeline in Python: YAML data files, schema validation (pydantic or JSON Schema), bound parser and comparator, derivation engine, pytest.
   - Site: a static site generator (e.g. Astro or Eleventy) rendering the pipeline's JSON, with KaTeX at build time.
   - GitHub Actions: validate + test on every PR; build and deploy to Pages on merge.
2. **Repository skeleton**: `README.md`, `CLAUDE.md` (from this package), `docs/` (PLAN, DESIGN), `design/`, `LICENSE` (MIT, code), `data/LICENSE` (CC0, data), `.github/workflows/`, issue forms for "Suggest a result (link or DOI)" and "Report an error".
3. **Schema draft → review with Serge.** Entities: problem (canonical definition, version, aliases, parameters with meanings, category, related problems), paper (versions with venue/year/link, open-access link), algorithm (bound as stated, notation, parameter(s), properties/tags, version proved for, paper + exact statement per version), reduction (from, to, type, own time, number of calls, parameter map, randomized, variants, formal status, paper + statement), hypothesis (status, sources). Stable IDs and citable URLs for every entry. A rough illustration is below; it is **not** agreed.
4. **Specs session with Serge**: turn the drafts in PLAN.md into `docs/specs/bounds.md` (expression language, normalisation to O*, comparison incl. (2 − ε)^n rules and incomparability) and `docs/specs/rulebook.md` (transfer rules per reduction type: poly-time deterministic, poly-time randomized, SERF first; substitution; calls; randomness; Turing call sizes; versioning). Ask, don't assume.
5. **Implement and test** the bound parser/comparator and the derivation engine against those specs, with unit tests for every rule (including chains of length > 3 getting a label, and dropping derived bounds that are neither better nor incomparable).
6. **Vertical slice: Vertex Cover end to end.** Enter its data from opened, open-access sources with exact statements; build its page to match `design/preview/`; get Serge's review. Then the other 11 problems.
7. **Site**: problem pages per DESIGN.md (bounds first, Overview/Details, version tabs, derived-bound chains, dark mode), a simple starting page listing the pilot problems with their best classical bound (randomized and non-constructive allowed, no quantum), How to cite page, JSON output per entry. Deploy to GitHub Pages.

## Schema illustration (not agreed; for discussion only)

```yaml
# data/problems/vertex-cover.yaml
id: vertex-cover
name: Vertex Cover
aliases: [Node Cover]
category: graph
versions:
  decision:
    input: "a graph G = (V, E) and an integer k"
    question: "is there S ⊆ V with |S| ≤ k such that every edge has an endpoint in S?"
  optimisation: { goal: "minimum |S| such that every edge has an endpoint in S" }
  search: { goal: "find such an S of size at most k, if one exists" }
equivalent_versions: [decision, optimisation, search]
parameters:
  n: number of vertices
  m: number of edges
  N: total input size
  k: solution size
  tw: treewidth of G

# data/algorithms/<id>.yaml
id: vc-k-<paper-id>
problem: vertex-cover
proved_for: <version>
bound: { as_stated: "O(1.2738^k + kn)", notation: O, parameters: [k, n] }
properties: { randomized: false, space: polynomial, constructive: true, algebraic: false, quantum: false }
conditional_on: []
source: { paper: <paper-id>, version: journal, statement: "Theorem X.Y" }   # TODO(verify)

# data/reductions/<id>.yaml
id: mis-to-vc-complement
from: maximum-independent-set
to: vertex-cover
type: karp-polytime-deterministic
calls: 1
time: "O(n + m)"
parameter_map: { n: n, k: "n - k" }
variants: [weighted]
formal_status: { isabelle: "https://github.com/wimmers/poly-reductions" }   # verify the exact theory
source: folklore
```

## Questions to ask Serge early

- Repo name and owner; stack preference.
- Schema: anything missing or wrong in the illustration?
- Bound language: which notations beyond O, O*, Õ (e.g. n^{o(k)}, 2^{O(√k)} log factors)? How to store results with several incomparable parameters at once (e.g. f(k)·n^c)?
- Rulebook: exact transfer rules for SERF and for parameterized reductions; how to treat reduction time that dominates.
- Optional randomized-error detail field: yes or no?
- Who gives final sign-off on the pilot data: Serge alone, or a second reviewer?

## Useful links

These two are private to Serge; this package already contains everything from them.

- Planning doc (living): https://claude.ai/artifact/FVbobRdSeXUrtp3YYdJ3Zp
- Design canvas (all explored designs): https://claude.ai/artifact/1F2VWnYcjpABPU7aomRtFt
- Sources and related projects: see "Existing work" in `docs/PLAN.md`.
