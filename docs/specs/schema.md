# PEAR data schema — DRAFT for review

> **Status: draft, not agreed.** Proposed 7 November 2026 for review with Serge (HANDOFF step 3). Open questions are marked **Q1–Q7** and collected at the end. Nothing here is implemented yet; once agreed, it becomes pydantic models in `src/pear/` and the examples become test fixtures.
>
> All bounds, theorem numbers and years in the examples are **placeholders** (`c`, `X.Y`, `YYYY`), not data.

Out of scope here: the syntax and meaning of bound expressions (`docs/specs/bounds.md`, step 4) and the transfer rules for reductions (`docs/specs/rulebook.md`, step 4). The schema stores bounds and parameter maps as strings in that language; the spec decides how they parse.

## 1. Files and identifiers

The repository is the database. Each entry is one YAML file named after its ID:

| Entity | Folder | ID pattern (proposal) | Page URL |
| --- | --- | --- | --- |
| Problem | `data/problems/` | name slug: `vertex-cover` | `/problems/vertex-cover/` |
| Parameter (shared) | `data/parameters/` | slug: `treewidth` | `/parameters/treewidth/` |
| Paper | `data/papers/` | first-author surnames (up to 3) + year of first public version: `chen-kanj-xia-YYYY` | `/papers/<id>/` |
| Algorithm | `data/algorithms/` | `<problem>--<param>--<paper>`, suffix `-2` on clashes | `/algorithms/<id>/` |
| Reduction | `data/reductions/` | `<from>--to--<to>`, suffix `--<paper>` or `-2` on clashes | `/reductions/<id>/` |
| Hypothesis | `data/hypotheses/` | slug: `seth` | `/hypotheses/seth/` |
| Lower bound | `data/lower-bounds/` | `<problem>--<param>--<paper>` | `/lower-bounds/<id>/` |

- IDs are lowercase ASCII kebab-case and **never change once published**. A rename or merge adds the old ID to `data/redirects.yaml`, and the site serves a redirect page. Every entry URL also has an `index.json` (the read API).
- The ID is a handle, not data. The site always shows names and citations, never IDs.
- Error flags and their grading (fixed, easily fixable, unrepaired, broken) get their own folder, `data/flags/`, in Phase 2. Phase 1 reserves a `status` field on results (§5) so nothing has to move later.
- Computed things are not stored: derived bounds, O* normal forms, best-bound sets and OpenAlex counts are build outputs.

**Q1.** Is this file layout and ID scheme right? In particular, should paper IDs be surname+year slugs, or DBLP keys (`journals/tcs/ChenKX10`, which are stable but not available for every paper)? I recommend slugs, with the DBLP key stored as an identifier.

## 2. Problem

```yaml
# data/problems/vertex-cover.yaml
id: vertex-cover
name: Vertex Cover
aliases: [Node Cover]                 # for search and OpenAlex matching
category: graph                       # controlled list: graph, satisfiability, sets, numbers, ...
complexity:
  class: NP-complete
  source: { paper: karp-YYYY, version: conference, statement: "TODO(verify)" }

objects:                              # rule 4: what n, m and N count, for this problem
  n: number of vertices
  m: number of edges
  N: total encoding length of the input
parameters:                           # further parameters, local or shared
  k: { meaning: "the integer k in the input (solution size)" }
  tw: { shared: treewidth }           # meaning, relations and history live in data/parameters/

versions:
  decision:
    kind: decision
    input: "A graph $G = (V, E)$ and an integer $k$."
    question: "Is there a set $S \\subseteq V$ with $|S| \\le k$ such that every edge has an endpoint in $S$?"
  optimisation:
    kind: optimisation
    input: "A graph $G = (V, E)$."
    goal: "Find the minimum size of a set $S \\subseteq V$ such that every edge has an endpoint in $S$."
  search:
    kind: search
    input: "A graph $G = (V, E)$ and an integer $k$."
    goal: "Find a set $S \\subseteq V$ with $|S| \\le k$ such that every edge has an endpoint in $S$, or report that none exists."
  weighted:
    kind: optimisation
    input: "A graph $G = (V, E)$ and vertex weights $w \\colon V \\to \\mathbb{Q}_{\\ge 0}$."
    goal: "Find the minimum weight of a set $S \\subseteq V$ such that every edge has an endpoint in $S$."
    generalises: [optimisation]       # bounds flow from here to optimisation, never back
default_version: decision

shared_bounds:                        # versions that share one set of best bounds
  - versions: [decision, optimisation, search]
    because: "binary search on k and self-reducibility"   # shown in the equivalence note

related:
  - { problem: independent-set, relation: complement }
  - { problem: connected-vertex-cover, relation: variant }
  - { problem: set-cover, relation: generalisation }

lean: { status: none }                # none | statement | proved; with link, library, library_version
review: { approved_by: null, date: null }
```

- Text fields are Markdown with `$…$` maths, rendered with KaTeX at build time. **Input** and **Question/Goal** are separate fields, so the page can put them on separate lines.
- `objects` always has `n` and `N`, and `m` where the problem has a natural relation count. A parameter used in any bound must be defined in `objects` or `parameters`; the validator checks this.
- The problem names its own versions, so a counting problem such as #3-SAT is a separate problem with `kind: counting`, as the pilot list implies.
- `generalises` lets bounds flow from a weighted version to its unweighted special case automatically, as the plan requires.
- `review.approved_by` records that a definition is approved. The Lean exception relies on this ("problem definitions already approved on the site").

**Q2.** For versions that share bounds, should the schema simply declare them (`shared_bounds` with a short reason, as above), or should it express the equivalence as reductions between versions so the derivation engine works it out? Declaring is simpler and enough for the pilot; reductions are more principled but drag the version-to-version reductions (and their polynomial overheads) into the rulebook. I recommend declaring them for now.

**Q3.** Should structural parameters (treewidth, pathwidth, …) live in a shared registry (`data/parameters/`) that problems point to? This gives one place for definitions, the bound history per parameter, and the later parameter relations (treewidth ≤ pathwidth ≤ …, HOPS). Purely local parameters such as `k` stay in the problem file. I recommend yes.

## 3. Paper

```yaml
# data/papers/chen-kanj-xia-YYYY.yaml
id: chen-kanj-xia-YYYY
title: "TODO(verify)"
authors: ["TODO(verify)"]             # display names, in paper order
identifiers: { dblp: null, openalex: null }
versions:
  conference:
    kind: conference                  # preprint | technical-report | workshop | conference | journal | book | thesis
    venue: "TODO(verify)"
    year: YYYY
    doi: null
    url: null
    open_access: false
  journal:
    kind: journal
    venue: "TODO(verify)"
    year: YYYY
    doi: "TODO(verify)"
    open_access: false
  arxiv-v2:                           # each arXiv version that statements cite gets its own entry
    kind: preprint
    arxiv: "TODO(verify)"
    year: YYYY
    open_access: true
```

- A version is `open_access: true` only if it can be read without a paywall or bot block (rule 2). The validator checks that every result cites at least one open-access version.
- Version keys (`conference`, `journal`, `arxiv-v2`) are local to the paper and are what statements refer to, because numbering differs between versions.
- Books (e.g. textbooks with open-access PDFs) and theses use the same entity.

## 4. Statements (shared by algorithms, reductions and lower bounds)

```yaml
source:
  paper: chen-kanj-xia-YYYY
  statements:
    journal: { statement: "Theorem X.Y" }
    arxiv-v2: { statement: "Theorem X.Y", page: 12 }
  note: null                          # e.g. "space bound from Lemma X.Y"
```

or, for an unpublished argument:

```yaml
source:
  folklore: true
  note: "Complement of an independent set is a vertex cover."
  reference: { paper: some-textbook-YYYY, version: book, statement: "Section X.Y" }   # optional
```

**Q4.** Rule 2 asks for the exact statement per paper version. Should the validator require a statement for **at least one open-access version** (so a reviewer can always check it without a paywall), with other versions optional? And should we store only the label ("Theorem 3.2", page), rather than the statement's text? I recommend yes to both: storing text adds copyright questions and goes stale between versions.

## 5. Algorithm

```yaml
# data/algorithms/vertex-cover--k--chen-kanj-xia-YYYY.yaml
id: vertex-cover--k--chen-kanj-xia-YYYY
problem: vertex-cover
proved_for: decision                  # the version the paper proved; shown as a badge
bound:
  as_stated: "O(c^k + k n)"           # exactly as in the paper, in the bound language (step 4)
  notation: O                         # O | O* | Õ; more if the bound spec adds them
  parameters: [k, n]
properties:
  randomized: false                   # or { error: one-sided }; see Q6
  space: { class: polynomial }        # polynomial | exponential; optional bound: "O*(...)"
  algebraic: false                    # curator-assigned
  fast_matrix_multiplication: false
  constructive: true
  impractical_constants: null         # optional note
  quantum: false
conditional_on: []                    # hypothesis IDs; the weakest known to suffice
source: { paper: chen-kanj-xia-YYYY, statements: { journal: { statement: "Theorem X.Y" } } }
formal: { status: informal }          # informal | statement | proved; prover, link
status: valid                         # Phase 2 grading via data/flags/
```

- The site never states a bound that is not in `as_stated`. The O* form and comparisons are computed.
- `parameters` must match the variables in `as_stated`; the validator checks this once the bound parser exists.
- Comparisons only ever use the single `randomized` tag (constant success probability). The optional error detail is for display only.

**Q6.** Do we want that optional, information-only error detail (Las Vegas / one-sided / two-sided)? I recommend yes: it costs one optional field, and readers often ask.

## 6. Reduction

```yaml
# data/reductions/independent-set--to--vertex-cover.yaml
id: independent-set--to--vertex-cover
from: { problem: independent-set, version: decision }
to: { problem: vertex-cover, version: decision }
type: polytime-deterministic          # polytime-deterministic | polytime-randomized | serf (owner decision)
calls: 1                              # 1 for many-one; an expression in A's parameters for Turing
call_sizes: null                      # Turing only: paper's own analysis, if it exploits different sizes
time: "O(n + m)"                      # the reduction's own running time
parameter_map:                        # each of B's parameters as an expression in A's
  n: "n"
  m: "m"
  k: "n - k"
variants:
  - { problem: vertex-cover, version: weighted, note: "TODO(verify)", source: null }
formal: { status: proved, prover: isabelle, link: "TODO(verify)" }
source: { folklore: true, note: "TODO(verify)" }
status: valid
```

- `type` names only the three reduction types agreed for the first phase. Adding a type is a high-risk change (rule 6), so the validator rejects unknown types.
- SERF-specific fields (how the family depends on ε) are left to the rulebook spec.
- Reductions carry the same property tags as algorithms where they apply (randomized via `type`; space, constructive).

## 7. Hypothesis

```yaml
# data/hypotheses/seth.yaml
id: seth
name: Strong Exponential Time Hypothesis
short: SETH
statement: "TODO(verify)"
status: claimed-refuted               # open | claimed-refuted | refuted; changes are high risk
status_sources:
  - { paper: TODO, version: TODO, statement: TODO, date: 2026-10-26 }
implies: [eth]                        # used to record the weakest sufficient hypothesis
```

## 8. Lower bound

```yaml
# data/lower-bounds/<problem>--<param>--<paper>.yaml
problem: some-problem
version: decision
bound: { as_stated: "TODO", notation: O, parameters: [n] }
kind: no-algorithm-faster-than        # wording to agree with the bound spec
conditional_on: [seth]                # weakest hypothesis known to suffice
source: { paper: TODO, statements: { journal: { statement: "Theorem X.Y" } } }
```

**Q5.** The plan mentions conditional lower bounds, but the step 3 entity list does not include them, and ETH/SETH are now claimed refuted. Should lower bounds be defined in the schema now but not entered in the pilot? I recommend that: it costs little now and avoids a schema change later.

## 9. Validation (build and CI)

The pipeline loads everything and fails the build if:

- an ID does not match its file name, or is duplicated, or a reference (problem, version, paper, paper version, hypothesis, shared parameter) does not resolve;
- a bound, time, call count or parameter map uses a variable the problem does not define;
- a result has no statement for an open-access paper version (pending Q4), and is not folklore;
- a reduction type or relation name is not on its controlled list;
- `shared_bounds` groups overlap, or `generalises` forms a cycle.

## Open questions

- **Q1** File layout and ID scheme; paper IDs as surname+year slugs or DBLP keys. *Recommend slugs, DBLP key stored.*
- **Q2** Versions sharing bounds: declared, or derived from version-to-version reductions. *Recommend declared.*
- **Q3** Shared registry for structural parameters. *Recommend yes.*
- **Q4** Statement required for at least one open-access version; labels only, no statement text. *Recommend yes to both.*
- **Q5** Lower bounds in the schema now, none entered in the pilot. *Recommend yes.*
- **Q6** Optional, information-only randomized-error field (Las Vegas / one-sided / two-sided). *Recommend yes, optional.*
- **Q7** Final sign-off on pilot data: Serge alone, or also a second reviewer? This decides what `review` records.
