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
category: graph                       # controlled list: graph, satisfiability, sets, numbers, ...
complexity:
  class: NP-complete
  source: { paper: karp-YYYY, statements: { conference: { statement: "TODO(verify)" } } }   # §4

objects:                              # rule 4: what n, m and N count, for this problem
  n: number of vertices
  m: number of edges
  N: total encoding length of the input
parameters:                           # further parameters, local or shared
  k: { meaning: "the integer k in the input (solution size)" }
  tw: { shared: treewidth }           # meaning, relations and history live in data/parameters/
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

**Q4 (decided).** Every paper-sourced result must give a statement for **at least one open-access version** of the paper; other versions are optional. Only the label (and optionally the page) is stored, never the statement's text.

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

**Q6 (decided).** `randomized` is `false`, `true`, or `{ error: las-vegas | one-sided | two-sided }`. The error detail is optional and display-only.

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
