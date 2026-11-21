# PEAR data schema

> **Status: agreed with Serge on 7 November 2026** (HANDOFF step 3; decisions Q1–Q7 at the end). Implemented as pydantic models in `src/pear/schema.py`, with the cross-entry checks in `src/pear/validate.py`. Checks that need the bound parser (variables inside bound strings and parameter maps) arrive with step 4. Changing the schema is the owner's decision.
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

**Q1 (decided).** File layout and ID scheme as above. Paper IDs are surname+year slugs; the DBLP key, where one exists, is stored under `identifiers`.

## 2. Problem

```yaml
# data/problems/vertex-cover.yaml
id: vertex-cover
name: Vertex Cover
aliases: [Node Cover]                 # for search and OpenAlex matching
category: graph                       # controlled list: graph, satisfiability, sets, numbers, scheduling, strings, geometry, social-choice, games, other (the last six approved 20 Nov 2026)
complexity:
  class: NP-complete
  source: { paper: karp-YYYY, statements: { conference: { statement: "TODO(verify)" } } }   # §4

objects:                              # rule 4: what n, m and N count, for this problem
  n: number of vertices
  m: number of edges
  N: total encoding length of the input
parameters:                           # further parameters, local or shared
  k: { meaning: "the integer k in the input (solution size)" }
  tw: { shared: treewidth }           # shared registry; add `of` only when the graph is ambiguous,
                                      # e.g. SAT: { shared: treewidth, of: "the primal graph" } (definitions F5)
  # t: { meaning: "the target number", poly_bounded: false }   # only for exceptions (bounds B4)
constraints:                          # used to compare bounds in different variables (bounds B5)
  - { constraint: "k \\le n", because: "TODO: one-line justification" }
  - { constraint: "m \\le n^{2}", because: "TODO: one-line justification" }

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
- `poly_bounded` (bounds B4): every variable counts as polynomially bounded in N unless marked `poly_bounded: false`, so O* absorbs polynomial factors in it. It applies to local and shared parameters; `n`, `m` and `N` are always polynomially bounded. Added 7 November 2026.
- `constraints` (bounds B5): relations between the problem's variables, in the bound language with one of `\le`, `\ge` or `=`, each with a one-line justification. The comparator uses them to compare bounds in different variables (bounds §5.3); the rulebook uses them for projection (rulebook §7). Added 7 November 2026.
- `generalises` lets bounds flow from a weighted version to its unweighted special case automatically, as the plan requires.
- `review.approved_by` records that a definition is approved. The Lean exception relies on this ("problem definitions already approved on the site").

**Q2 (decided).** Versions that share bounds are declared in the problem file (`shared_bounds`, with a short reason), not derived from version-to-version reductions.

**Q3 (decided).** Structural parameters (treewidth, pathwidth, …) live in a shared registry, `data/parameters/`, that problems point to. It holds their definitions and, later, the parameter relations (HOPS). Purely local parameters such as `k` stay in the problem file.

```yaml
# data/parameters/treewidth.yaml
id: treewidth
name: Treewidth
symbol: tw
aliases: []
poly_bounded: true                    # the default; may be omitted
definition: "TODO(verify)"            # Markdown with $…$ maths
```

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
    title: null                       # only when this version's title differs from the paper's
    authors: null                     # only when this version's authors differ (a merged journal version)
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

- A version is `open_access: true` only if it can be read without a paywall or bot block. Closed versions are recorded too, and statements may cite them when we have read them (rule 2, 21 November 2026).
- `unverified: true` marks a paper that is not peer reviewed or otherwise verified, such as an unrefereed technical report. A paper with no journal, conference, workshop, book or thesis version is a preprint; its results are treated like unverified ones in the Overview (left out by default, switched in all at once; decided 18 November 2026), but not tagged unverified in Details or the references. Its results, and bounds derived from them, appear in Details and are left out of the Overview by default (decided 8 November 2026); each reader can include them one by one, stored in their browser (12 November 2026). A result that relies on other results as black boxes lists them in `uses` (decided 13 November 2026), for example a theorem proved under an algorithmic assumption that another result establishes: Reverse Reductions (Kundu et al.) assume a fixed-width SAT algorithm, which the Lean-checked OpenAI and Anthropic theorems provide. Such a result is unverified if any result it uses (transitively) is, carries their hypotheses, and stays out of derivation if any of them has a status other than valid or fixed; it is then listed under Flagged results as relying on such a result. Exception: a result whose `formal` status is `proved` and whose `formal.statement_checked` records who checked the formal statement against the canonical definition and parameter mapping, and when, counts as verified (12 November 2026). The validator checks that every result cites a statement in some version, an attestation or a confirmation (rule 2).
- Version keys (`conference`, `journal`, `arxiv-v2`) are local to the paper and are what statements refer to, because numbering differs between versions.
- Books (e.g. textbooks with open-access PDFs) and theses use the same entity.
- Record every published version (journal, conference), not only the ones statements cite: a reference names the journal version, else the conference version, else a technical report or preprint (decided 17 November 2026; DESIGN.md, References), with the cited statements and their versions next to it. A version whose title differs from the paper's (journal versions are often retitled) gives its own `title`; the reference shows the title of the version it names (approved 17 November 2026). Likewise a version whose authors differ gives its own `authors`, for a journal paper that merges the paper with another one and counts as its journal version (Fomin–Gaspers–Saurabh, ISAAC 2006 → Fomin–Gaspers–Saurabh–Stepanov, Algorithmica 2009; approved 18 November 2026), or for a preliminary version by a subset of the authors (Narayanaswamy–Raman–Ramanujan–Saurabh, STACS 2012, of Lokshtanov et al., TALG 2014). A paper's conference version, technical report and journal version are one paper entry, even when they are retitled.

## 4. Statements (shared by algorithms, reductions and lower bounds)

```yaml
source:
  paper: chen-kanj-xia-YYYY
  statements:
    journal: { statement: "Theorem X.Y" }
    arxiv-v2: { statement: "Theorem X.Y", page: 12 }
  note: null                          # e.g. "space bound from Lemma X.Y"
```

Statements may cite any version we have read, open or closed (21 November 2026). A closed-source result that Serge confirms without our reading it:

```yaml
source:
  paper: some-closed-paper-YYYY
  confirmed_by: { by: Serge Gaspers, date: YYYY-MM-DD }
  note: "…"
```

or, for a classic result whose paper we **cannot read** (decided 7 November 2026, definitions F7):

```yaml
source:
  paper: karp-1972
  attested_by:                        # independent web sources confirming the result; at least 3 sites
    - "https://…"
    - "https://…"
    - "https://…"
  note: "Vertex Cover is one of Karp's 21 NP-complete problems."
```

The validator accepts `attested_by` alone only when the paper has no open-access version, and counts distinct sites. A source needs `statements`, `attested_by` or `confirmed_by`.

or, for an unpublished argument:

```yaml
source:
  folklore: true
  note: "Complement of an independent set is a vertex cover."
  reference: { paper: some-textbook-YYYY, version: book, statement: "Section X.Y" }   # optional
```

**Q4 (decided, revised 21 November 2026).** Every paper-sourced result gives a statement for at least one version we have read, open or closed (or an attestation or confirmation, above); other versions are optional. External submissions must still point to an openly readable version. Only the label (and optionally the page) is stored, never the statement's text.

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
uses: []                              # algorithm IDs this result relies on as black boxes (13 November 2026)
source: { paper: chen-kanj-xia-YYYY, statements: { journal: { statement: "Theorem X.Y" } } }
formal: { status: informal }          # informal | statement | proved; prover, link; statement_checked (proved only)
status: valid                         # Phase 2 grading via data/flags/
status_note: "…"                     # why the status is not valid (Phase 1)
```

- `unverified: true` on a result (18 November 2026): its statement is in no peer-reviewed version of the paper, for example dropped from the journal version (Kociumaka–Pilipczuk's $O^*(3.592^k)$, arXiv v1 only). Such a result is treated like one from an unverified paper: tagged in Details, out of the Overview unless included.

- The site never states a bound that is not in `as_stated`. The O* form and comparisons are computed.
- `given: [tree-decomposition]` records that the input comes with a tree decomposition of width at most $\mathrm{tw}$, as is usual for results parameterized by treewidth. The result is stored as stated, and the site shows the note (decided 8 November 2026). Since 21 November 2026 `given` may also list `path-decomposition`, `clique-width-expression`, `linear-arrangement`, `interval-ordering` and `deletion-set` (the modulator a deletion parameter measures); a bound projected to $n$, $m$ or $N$ drops these flags, since the trivial structure (one bag, one label per vertex, any order, all vertices) is computable.
- `parameters` must match the variables in `as_stated`; the validator checks this once the bound parser exists.
- Comparisons only ever use the single `randomized` tag (constant success probability). The optional error detail is for display only.

**Q6 (decided).** `randomized` is `false`, `true`, or `{ error: las-vegas | one-sided | two-sided }`. The error detail is optional and display-only.

## 6. Reduction

```yaml
# data/reductions/independent-set--to--vertex-cover.yaml
id: independent-set--to--vertex-cover
from: { problem: independent-set, version: decision }
to: { problem: vertex-cover, version: decision }
type: polytime-deterministic          # polytime-deterministic | polytime-randomized | serf | polytime-counting (counting versions only; rulebook §2a, 21 Nov 2026)
calls: 1                              # 1 for many-one; an expression in A's parameters for Turing
call_sizes: null                      # Turing only: paper's own analysis, if it exploits different sizes
time: "O(n + m)"                      # the reduction's own running time
parameter_map:                        # each of B's parameters as an expression in A's
  n: "n"
  m: "m"
  k: "n - k"
variants:                             # slight modifications of the reduction (see below)
  - id: by-treewidth                  # local; the variant is cited as <reduction>~<id>
    note: "TODO: what is modified, e.g. a kernelization step is added first"
    from: null                        # optional { problem, version }; defaults to the reduction's
    to: null                          # optional { problem, version }; defaults to the reduction's
    parameter_map: { tw: "TODO" }     # replaces the reduction's map
    time: null                        # optional; defaults to the reduction's
    calls: null                       # optional; defaults to the reduction's
    source: null                      # a paper or folklore; null = written by the site
formal: { status: proved, prover: isabelle, link: "TODO(verify)" }
source: { folklore: true, note: "TODO(verify)" }
status: valid
```

- `type` names only the three reduction types agreed for the first phase. Adding a type is a high-risk change (rule 6), so the validator rejects unknown types.
- SERF-specific fields (how the family depends on ε) are left to the rulebook spec.
- Reductions carry the same property tags as algorithms where they apply (randomized via `type`; space, constructive).
- **Variants** (agreed 7 November 2026) are slight modifications of a reduction. Examples: a paper focused on one parameter but a slight variant works for another; a known step such as a kernelization has to be added first; or the same construction reduces between other problems or versions (weighted vs unweighted, Red-Blue Dominating Set vs Set Cover). A variant keeps the reduction's type, and may set its own `from` and `to` (default: the reduction's). It replaces the parameter map, and may override `time` and `calls`. It has its own `formal` status and `review`. A variant with no `source` is written by the site, which is a high-risk addition (rule 6): it is used for derivation only once Serge approves it (`review`), and derived bounds through it are flagged. Variant ids are unique within the reduction.

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
# data/lower-bounds/some-problem--n--some-author-YYYY.yaml
id: some-problem--n--some-author-YYYY
problem: some-problem
version: decision
bound: { as_stated: "TODO", notation: O, parameters: [n] }
conditional_on: [some-hypothesis]     # weakest hypothesis known to suffice
source: { paper: TODO, statements: { journal: { statement: "Theorem X.Y" } } }
```

How a lower bound is read ("no algorithm in time …", "no $2^{o(n)}$ algorithm", …) is settled with the bound spec in step 4.

**Q5 (decided).** Lower bounds are in the schema now; the pilot enters none. Hypotheses that are not claimed refuted remain valid bases for lower bounds (e.g. the hypothesis that CNF-SAT has no subexponential algorithm). Each lower bound shows its hypothesis's current status.

## 9. Validation (build and CI)

`python -m pear validate` (run in CI on every PR) loads everything and fails if:

- a file does not match the schema: unknown fields, missing required fields, values off a controlled list (category, version kind, reduction type, relation, status, …);
- an ID does not match its file name or the ID pattern, or a reference does not resolve (problem, version, paper, paper version, hypothesis, shared parameter, related problem);
- a bound lists a parameter the problem does not define, or a parameter map sets a parameter the target problem does not define;
- a paper-sourced result has no statement for an open-access version of its paper;
- `default_version` or a `shared_bounds` / `generalises` entry names an unknown version, `shared_bounds` groups overlap, or `generalises` forms a cycle;
- a hypothesis that is not `open` has no status source;
- `review.approved_by` is set to anyone other than Serge Gaspers, or set without a date;
- a redirect points to a missing entry or shadows an existing one.

With the bound parser (step 4): every variable inside `as_stated`, `time`, `calls` and the right-hand sides of `parameter_map` must be defined, and `bound.parameters` must match the variables in `as_stated`.

Redirects:

```yaml
# data/redirects.yaml
problems: { old-id: new-id }
```

## 10. Review record

Every entry has `review: { approved_by, date }`, both `null` until approved. Final sign-off on pilot data is Serge's alone (Q7), so the validator accepts only `approved_by: Serge Gaspers`.

## 11. Named constant (agreed 7 November 2026)

Constants that bounds use symbolically, such as $\omega$ (bounds §2). The comparator uses the best lower and upper bounds that are not refuted. Changing a constant's bounds can change best bounds, so it is high risk (CLAUDE.md rule 6).

```yaml
# data/constants/omega.yaml
id: omega                             # must match the parser's name for the symbol
name: Matrix multiplication exponent
symbol: "\\omega"
definition: "…"
definition_source: { paper: …, statements: { …: { statement: "Section 1", page: 1 } } }
bounds:
  - relation: le                      # le | ge
    value: "9/4"                      # a number in the bound language
    status: claimed                   # established | claimed | refuted
    sources: [ … ]                    # one or more, each as in §4
  - relation: ge
    value: "2"
    sources: [ { folklore: true, note: "…" } ]
```

The validator checks that every constant used in a bound has an entry, that values are numbers, that at least one upper bound is not refuted, and that the bounds do not cross.

## 12. Implementation (agreed 8 November 2026)

Publicly available code that solves a problem. One file per implementation in `data/implementations/<id>.yaml`; one implementation can solve several problems.

```yaml
id: wegotyoucovered
name: WeGotYouCovered
url: "https://github.com/sebalamm/pace-2019"   # code or download page
language: C++
licence: GPL-2.0
solves:
  - problem: vertex-cover
    versions: [decision, optimisation, search]   # empty: the default version
    exact: true          # true: exact; false: heuristic; omitted: not stated
    note: "…"           # e.g. "via the complement"
facts:                   # positive, sourced facts only
  - fact: "Winner of the PACE 2019 Vertex Cover exact track (87 instances solved)."
    source: "https://drops.dagstuhl.de/… (Table 4)"
    as_of: 2026-11-08    # for facts that change: citation counts, stars
review: { approved_by: …, date: … }
```

The ranking lives in the problem file, best first, because "best" depends on the problem:

```yaml
implementations:
  as_of: 2026-11-08
  ranked: [wegotyoucovered, peaty, …]
```

Only exact implementations are listed (agreed 8 November 2026): a ranked implementation must have `exact: true` for the problem; heuristics are out of scope. One ranking per problem, not per version; support for a version (e.g. weights) is shown through `solves.versions` and the facts. An implementation for a closely related problem may be listed when the problem is solved through a trivial transformation, such as a vertex cover solver for Independent Set through the complement, with a `note` saying so.

The order is subjective but informed by data (competition results, published benchmarks). The site shows the list in this order without calling it a ranking and without saying how the order was chosen (decided 10 November 2026), so problem files carry no ranking note. Facts are positive and sourced: competition placings, citation counts (OpenAlex, with `as_of`), wide use in a named field. Where to look for implementations: `docs/implementations.md`.

The validator checks that ranked ids exist, appear once and solve the problem exactly, and that every `solves` entry names a known problem and version.

## 13. Technique (approved 18 November 2026)

A generic method that the engine combines with every result meeting all its prerequisites (rulebook §9a). One file per technique in `data/techniques/<id>.yaml`.

```yaml
id: monotone-local-search
name: Monotone Local Search
source: { paper: fomin-gaspers-lokshtanov-saurabh-2015, statements: { arxiv-v1: { statement: "Theorems 1 and 2" } } }
input_parameter: k          # the theorem's symbols: input c^{k}, output in n
output_parameter: n
base: "2 - 1/c"             # the output base, an expression in c
prerequisites:              # every check the engine makes, once each, with where the paper states it
  - { check: subset-problem, statement: "Section 1 of arXiv v1", text: "…" }
  - { check: extension, statement: "Theorems 1 and 2 of arXiv v1", text: "…" }
  - { check: single-exponential, statement: "Theorems 1 and 2 of arXiv v1", text: "…" }
  - { check: error, statement: "Remark 1 and Theorem 2 of arXiv v1", text: "…" }
  - { check: classical, statement: "Theorems 1 and 2 of arXiv v1", text: "…" }
rules:
  - { id: randomized, statement: Theorem 1, accepts: [deterministic, one-sided, two-sided],
      accepts_statement: "Remark 1 (after Lemma 2.1)", output_deterministic: false, keeps_polynomial_space: true }
  - { id: deterministic, statement: Theorem 2, accepts: [deterministic], output_deterministic: true,
      keeps_polynomial_space: false, subexponential_factor: true }
applies_to:
  - problem: feedback-vertex-set
    version: decision       # inputs must be for this version's class
    universe: n             # an object count of the problem: the output is in it
    budget: k               # a parameter of the problem: the input must be c^{k}
    setting: { statement: "Section 1 of arXiv v1", because: "Vertex deletion into forests, a hereditary class: …" }
    extension: { statement: "Section 1 of arXiv v1", because: "… the vertices in X can simply be deleted." }
review: { approved_by: Serge Gaspers, date: 2026-11-18 }   # applied only once approved
```

## Decisions (7 November 2026)

- **Q1** Paper IDs are surname+year slugs; DBLP key stored under `identifiers`.
- **Q2** Versions that share bounds are declared (`shared_bounds`).
- **Q3** Shared registry for structural parameters in `data/parameters/`.
- **Q4** A statement is required for at least one open-access version; labels only, no statement text.
- **Q5** Lower bounds are in the schema; none entered in the pilot. Hypotheses not claimed refuted remain valid bases.
- **Q6** Optional, display-only randomized-error detail.
- **Q7** Serge alone gives final sign-off on pilot data.
- **Named constants** (§11, agreed later the same day): `data/constants/`, with sourced bounds marked established, claimed or refuted. Claimed bounds count in comparisons. The matrix multiplication exponent is always written `\omega`, never `\Omega` (`\Omega` stays available for other uses).

## Implementation notes

- Fictional fixtures in `tests/fixtures/valid/` exercise every entity; `tests/test_schema.py` has a failing case for each rule above.
- Run `python -m pear validate [DATA_DIR]` locally; CI runs it on `data/` for every PR.
- An entry that fails its own checks is reported once; references to it from other files are not reported again.
