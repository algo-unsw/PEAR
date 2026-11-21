# PEAR: Parameterized and Exact Algorithms and Reductions — site plan

Owner: Serge Gaspers. Exported from the planning doc on 6 November 2026. This is the agreed plan; `HANDOFF.md` says what to build first.

## Goal

PEAR is a research website cataloguing NP-hard problems, the reductions between them, and the fastest known exact algorithms for each problem. Some best-known bounds come directly from papers; others are derived automatically by chaining reductions.

Out of scope: approximation algorithms. Only exact algorithms are tracked.

## Core concepts

- **Problem**: a computational problem with one canonical definition, a list of alternative names (also used for search and OpenAlex matching), its parameters (e.g. n, m, k = solution size, treewidth), and its best known algorithms.
- **Algorithm**: a running-time bound expressed in the problem's parameters (e.g. 2^k · poly(n)), with source paper and whether it is conditional or unconditional.
- **Reduction**: a directed link from problem A to problem B, with:
  - its **type** (e.g. Karp / many-one, Turing, parameterized, fine-grained, SERF),
  - a **parameter mapping** describing how each variable grows during the reduction (e.g. k ↦ k, n ↦ n·k),
  - the reduction's own running time and number of calls to B,
  - source paper (exact statement, per paper version).
- **Hypothesis**: ETH, SETH, Set Cover Conjecture, etc., each with a status (see below).
- **Paper**: one entry with several versions (technical report, workshop, conference, journal).

## Algorithm and reduction properties

Every algorithm and reduction is tagged with its model and resource properties, and derived bounds inherit them.

- Deterministic or randomized. Comparisons use a single "randomized" tag (constant success probability, amplified as needed). An optional, information-only field records Las Vegas / one-sided / two-sided error (decided 7 November 2026).
- Space: polynomial or exponential, with the space bound where known.
- Algebraic or combinatorial (curator-assigned, since "combinatorial" has no formal definition), with an objective sub-tag "uses fast matrix multiplication" (matches conditional lower bounds stated for algorithms that avoid it).
- Constructive: the algorithm or reduction can actually be written down. It is non-constructive when a paper proves that it exists but gives no way to write it down, even taking known results into account (e.g. results relying on Robertson–Seymour well-quasi-ordering). An algorithm that decides, optimises or counts without outputting a solution is still constructive: `proved_for` records which version it solves. Optional note on impractical constants.
- Classical or quantum.
- Unconditional or conditional on a hypothesis.
- Reductions carry the same tags; e.g. a randomized reduction yields only a randomized derived bound.
- Users can filter best bounds by these properties, e.g. fastest deterministic polynomial-space algorithm.

## Derived bounds

- Problems and reductions form a graph computed behind the scenes. **It is not displayed as a diagram** (owner decision: too busy as the site grows). Each derived bound shows its own chain instead.
- The site combines a reduction's parameter mapping and type with the target problem's best algorithm to compute derived bounds for the source problem, only where the reduction type justifies the transfer.
- Running times in several parameters are often incomparable (e.g. 2^k · n vs k^k · log n), so **all incomparable best results are kept and shown**, rather than a single winner.
- Each problem page shows its best bounds and where each came from (direct paper or reduction chain).

## Bound expression language (agreed 7 November 2026; full spec in `specs/bounds.md`)

Bounds are stored exactly as the paper states them (TeX subset), and shown in O* notation by default, always in their natural form (e.g. $k^k$, never rewritten as $2^{k \log k}$). Bases computed for derived bounds are rounded up.

- A bound is a sum of terms, e.g. 1.2738^k + kn.
- Each term is a product of an exponential (e.g. 1.2738^k, 2^tw, 2^√k, n^k), powers (e.g. n², m) and log factors.
- Each bound carries its notation: O, O* (hides polynomial factors) or Õ (hides log factors).
- Within one parameter, bounds are compared by exponential base first, then polynomial degree, then log factors.
- Non-explicit constants are kept in comparisons and written as in papers, e.g. (2 − ε)^n for some ε > 0. With no proven size for ε, it is treated as arbitrarily small: (2 − ε)^n beats 2^n, but any explicit base below 2, such as 1.99^n, beats (2 − ε)^n.

## Rules for chaining reductions (agreed 7 November 2026; full spec in `specs/rulebook.md`, now version 2)

A precise, written, versioned rulebook decides when and how a bound transfers along a reduction. Changing it recomputes all derived bounds and is high risk.

- A reduction from A to B records its own running time, how each of B's parameters depends on A's, the number of calls to B (one for Karp, possibly many for Turing), and whether it is randomized.
- Derived bound for A = reduction time + number of calls × B's best bound with parameters substituted. Example: B in 1.2^k, k ↦ 2k, one call → A in 1.44^k.
- Chains of any length are allowed and applied step by step (a shortest-path-like search, so it stays cheap). Every derived bound shows its full chain; chains longer than three steps get a small label so readers check more closely.
- Turing reductions with calls of different sizes: if a paper's analysis exploits the different sizes (e.g. via a recurrence), the site stores and uses that analysis. Otherwise it assumes every call has the largest size and adds a flag that adaptive sizes might give an improvement (these flags double as a list of research questions).
- One randomized step makes the whole chain randomized; with many calls, each call's error is amplified so the total stays small, a cost hidden in O*.
- A bound transfers only if every parameter in B's bound can be written in terms of A's parameters through the reduction.
- Only derived bounds that are new best or incomparable results are kept; worse derived bounds are discarded.
- Reduction types to support first (owner decision): polynomial-time deterministic, polynomial-time randomized, and SERF (subexponential reduction families).
- To do: relations between parameters, so bounds transfer across them, e.g. treewidth ≤ pathwidth ≤ treewidth · O(log n). HOPS is a possible source.

## Canonical problem definitions

Every problem has exactly one canonical definition, because small differences quietly change bounds.

- State decision, optimisation or search version explicitly; versions link to each other.
- Natural sizes: n is the number of basic objects (vertices, variables, elements, …) and m the number of relations between them (edges, clauses, constraints, sets, …); each problem states exactly what n and m count. Capital N is the total input size (encoding length). Other parameters such as k or treewidth are defined per problem.
- Definitions are the basis for Lean statements and for matching results from papers.
- The definition format was agreed on 7 November 2026: `specs/definitions.md`. Defaults: graphs are finite, simple and undirected; $N$ is a binary encoding length; the optimisation version outputs the optimum value; $k$ is the input integer (decision, search) or the optimum (optimisation); weights are nonnegative integers unless a problem says otherwise.
- Classic results in closed papers (e.g. Karp 1972) are cited as such, confirmed by at least three independent web sources instead of an open statement. As a general rule, citations of classic results mirror Wikipedia's choice (decided 8 November 2026).
- A result is dated by the earliest paper version that states it, not by the paper's first version (decided 8 November 2026).
- Unrefereed reports (e.g. Robson 2001) are tagged unverified: shown in Details, not in the Overview. Each reader can include individual unverified results in the Overview with a checkbox in Details, stored in that browser only; an included result shows in its group and hides the results it beats (decided 12 November 2026). Preprints such as the 2026 ETH refutations are unverified; a Lean-checked statement is entered as its own result, and counts as verified once its Lean statement has been checked against our definition and parameter mapping (`formal.statement_checked`; decided 12 November 2026: the OpenAI and Anthropic #3-SAT results). Results that rely on other results as black boxes list them in `uses` and inherit their verification, hypotheses and flags (decided 13 November 2026, for Reverse Reductions). Treewidth results are stored as stated, with a note that a tree decomposition is given. For historical results, best guesses about properties are fine without human verification (decided 8 November 2026).

### Presenting versions of a problem

A problem such as Vertex Cover is one family page with a version switcher: Decision (default), Optimisation, Search, Weighted.

- Versions equivalent up to polynomial factors (for Vertex Cover: decision, optimisation and search, via binary search on k and self-reducibility) are linked by those reductions and share one set of best bounds.
- Each result carries a badge naming the version the paper actually proved, e.g. "proved for the optimisation version".
- Versions with genuinely different bounds (e.g. Weighted Vertex Cover) get their own tab and bounds. Bounds flow from general to special cases automatically: a weighted algorithm appears as a derived bound for the unweighted version, never the reverse.
- Distinct problems (Connected Vertex Cover, Independent Set, …) are separate pages listed under related problems, not tabs.

## Related problems and reduction variants

- Related problems: enumeration, counting, weighted, search vs decision, directed vs undirected and similar versions, each linked with the type of relationship.
- Problems tightly coupled by parameter-preserving reductions in both directions are grouped, since they share the same best bounds (e.g. a fine-grained equivalence class).
- Reduction variants: a reduction records which problem variants it also works for (e.g. the weighted version), with a note on how the referenced construction is modified.
- A variant keeps the original's citation and adds its own source where the adaptation is published; unpublished adaptations are marked as folklore and reviewed like any submission.

## Implementations (agreed 8 November 2026; schema in `specs/schema.md` §12)

- Each problem page has a section listing publicly available implementations, ranked from best performing to worst. The ranking is subjective but informed by data (competition results, published benchmarks); a note says which places rest on data.
- Each implementation shows positive, sourced facts: competition placings (e.g. winner of PACE 2019), citation counts above a threshold worth mentioning (OpenAlex, dated), wide use in a named field.
- Exact implementations only; heuristics are out of scope.
- One ranking per problem (not per version).
- Solvers for a closely related problem may be listed when a trivial transformation solves this one (e.g. vertex cover solvers for Independent Set via the complement), with a note.
- Shown in an Implementations section of the Details view only (not in the Overview).
- Decided 10 November 2026: the page shows the implementations in the stored order without calling it a ranking: no "best first", no note on how the order was chosen, no ranking date.
- `docs/implementations.md` keeps the list of places to look (PACE and other competitions, SageMath, NetworkX, igraph, OR-Tools, KaMIS, Zenodo, GitHub, …) and the exclusions (dead links).

## Hypotheses and conditional results

- Each hypothesis has a status: open, claimed refuted (under review), or refuted, with sources.
- Conditional lower bounds and algorithms link to the hypothesis they assume and show its current status.
- When a hypothesis is refuted, every dependent result is marked automatically; the status change itself is high risk and needs human approval.
- Each result records the weakest hypothesis known to suffice, e.g. the CNF-SAT hypothesis with unbounded clause width rather than SETH.
- Current case: OpenAI and Anthropic posted Lean-checked refutations of ETH and SETH on 26 October 2026, under external review. Lower bounds based on ETH/SETH are therefore not shown prominently in the designs.

## Papers and versions

- Versions tracked per paper: technical report, workshop, conference, journal; each with its own venue, year and link (DOI, arXiv, …).
- Each algorithm or reduction points to the exact statement used, e.g. Theorem 3.2 in the journal version. Numbering differs between versions, so the reference is stored per version.

## Error flagging and fallback

- Anyone can flag a result, with a reason and, where available, a link to evidence (erratum, counterexample). The evidence link is never required, not even for wrong-result reports (decided 7 November 2026).
- Once a flag is confirmed (always by a human), the result is excluded from bound derivation and affected bounds are recomputed, falling back to the next best valid algorithm or chain.
- Flagged results stay visible with their status.
- Confirmed errors are graded:
  - **Fixed**: a correction exists (erratum, later version, published or accepted fix); the result counts again, citing the fix.
  - **Easily fixable**: minor gap with a known fix, often unpublishable on its own (e.g. authors left academia). The site writes up the fix, shown in a pop-up next to the result; the result counts in best and derived bounds, marked as relying on a site-written fix. A new site-written fix is high risk and needs human approval unless proved in Lean.
  - **Unrepaired**: no fix known, but the claim might still hold.
  - **Broken**: the claim is false; it stays only in the history.

## Contributions

- Anyone can contribute; a submission can be just a single link or DOI. Claude extracts results, exact statements and paper versions itself.
- At least one reference for every result must be openly readable (not paywalled or bot-blocked; e.g. arXiv, ECCC, an open-access version). If the submitted link is closed, Claude first looks for an open version (e.g. via OpenAlex) and holds the submission if none exists.
- Submissions are reviewed by the automated curator.

## Automated curation

Claude curates on a schedule and asks a human only about high-risk changes.

- A scheduled run (e.g. daily) processes new submissions, error flags, OpenAlex tracker results and newly published papers. For each item it checks the cited statement in the paper, extracts the bound, parameters and tags, and opens a pull request.
- **Low risk, auto-merge**: new paper versions, alternative names, metadata, related-problem links, new problems that pass the tracker, results that do not change any best bound.
- **High risk, human approval**: anything that changes a best known bound, confirms an error flag, introduces a new reduction type, changes a hypothesis status, a new site-written fix, or where Claude is unsure.
- **Lean exception**: Lean-proved results go live automatically, even if they change a best bound, provided the proof covers correctness and the parameter mapping and uses problem definitions already approved on the site. Only the reduction's own running time is then unproved, and Claude checks it against the paper.
- Every automated decision is logged with its reasoning; humans can revert any of them.

### Running the curator and security

- Scheduled GitHub Actions workflow, authenticated with the owner's Claude subscription through an OAuth token from `claude setup-token`, stored as a repository secret. The token lasts one year and must be renewed. Check Anthropic's current subscription terms before launch.
- The public can open issues, but issues never trigger Claude runs. The scheduled job reads open issues and processes them as a batch. If contributors later trigger Claude directly, switch to an API key.
- Public issues are untrusted input: the curator treats their text only as data and never follows instructions inside them.
- The curator's token and permissions are limited to opening pull requests and labelling issues; high-risk changes are never merged without human approval.

### Approval queue

- Each item gets a severity (e.g. how many best and derived bounds it changes, a hypothesis status change, a site-written fix) and Claude's confidence, with reasons. Ranked so high-severity, low-confidence items come first.
- Each item is a self-contained review packet (Markdown with a JSON block): the claim, the exact statement and open link, the proposed change, affected bounds, Claude's reasoning and confidence, and the specific risks to check.
- The packet can be pasted into a separate AI for independent review. It ends with instructions for the reviewer: review independently from the linked open source; reply with one JSON block containing verdict (approve, reject, needs changes, unsure), confidence 0–1, pass/fail per listed risk with a one-line reason, whether the cited statement was found and matches, errors found, and a suggested fix. A reply that does not match the format is treated as unsure.
- Optional: when Claude and an independent model both approve with high confidence and severity is below a set level, the item merges automatically; any disagreement goes to the owner.

### Human spot checks

- Each month, a random sample of automatically merged items (e.g. three to five) goes to the owner. Errors found tighten the auto-merge thresholds.

## Problem coverage and growth

- Initial set: roughly 100 well-known NP-hard problems, drafted by Claude from Garey and Johnson and the compendia under Existing work, approved by a human once.
- A tracker counts OpenAlex papers per candidate problem not yet on the site. At 50 papers (adjustable) Claude checks the candidate, resolves ambiguous names, and adds it if it is clearly NP-hard and distinct; unclear cases go to a human.

## Starting page

A short dashboard of the most referenced problems, each with its best classical running time.

- Ranked by number of papers per problem.
- Each row: problem and its best known classical running time, published or derived, linking to the problem page. Deliberately permissive: randomized and non-constructive algorithms count; quantum algorithms are excluded.
- Where a problem has several incomparable best bounds, the row shows the bound in its most studied parameter, with a link to the rest. Popularity = number of papers per problem–parameter pair (papers, not authors), combining papers on the site that give a bound in that parameter and OpenAlex papers whose title or abstract pairs a problem name with the parameter's usual wording (e.g. "parameterized by treewidth"; for n, "exact exponential algorithm"). Claude checks a sample of OpenAlex matches and scales the count by the share that fits.

## Bound history per parameter

The Details view of a problem page shows the history of the best running time in each parameter (decided 10 November 2026: Details only, not the Overview).

- A small step chart of the best bound by year (e.g. the base c of c^k for Vertex Cover in k). Polynomial factors ignored in the chart, shown in the list.
- Below it, every improvement: year, bound, paper (version and exact statement), published or derived.
- Results later flagged as wrong stay in the history, marked.
- Bounds whose shape changes (e.g. n^O(k) to c^k) are shown as separate eras.

## Lean compatibility

- Each problem can link to its Lean definition (ideally Mathlib or a shared library such as Complexitylib). Keep track of library versions; by default use the latest stable version. Look at existing work formalising problem definitions and reductions.
- Each reduction records its formalisation status: informal, statement formalised, or proved (Lean or another prover, e.g. Isabelle), with a link.
- Problem definitions and parameter mappings use a structured format that exports to Lean statement stubs.
- CI builds the linked Lean proofs (only when Lean files change; Mathlib cached).
- Correctness and parameter mappings are formalised first; running times stay informal at first.
- In the UI, Lean status is only a small label (the site targets the wide community).

## API for AI agents

- Read access: stable JSON for every problem, algorithm, reduction and paper; queries such as the best bound under chosen properties, or the chain behind a derived bound.
- A skill comes first: instructions and scripts covering the data format, citing exact statements, writing submissions, Lean conventions and the curation risk rules. It reads the static JSON directly and doubles as the playbook for the scheduled curator. An MCP server for outside agents comes later, if there is demand.
- Write access: agents submit suggestions and flags through GitHub issues/PRs into the same review queue, labelled agent-submitted.
- Bulk export of the dataset, plus an `llms.txt`.

## Hosting and implementation

- Static site on GitHub Pages; all derived bounds computed at build time. One public repository; the repository is the database (YAML/JSON files checked against a schema) and its history is the change log.
- On every merge a GitHub Actions job loads all files into a graph, validates them, chains reductions to compute derived bounds (applying parameter mappings and only allowed type combinations), drops flagged results and those resting on refuted hypotheses, keeps the incomparable best results, and writes static pages plus JSON (the JSON doubles as the read API).
- Submissions and flags use GitHub issue forms. Scheduled jobs: curator (daily), OpenAlex tracker (weekly).
- GitHub Pages limits are ample: site up to 1 GB, soft bandwidth limit 100 GB/month, no server-side code. Actions minutes on standard runners are free for public repositories. Estimated usage: build 2–5 min per merge, Lean check 10–20 min when Lean files change, curator 10–30 min/day, tracker a few minutes/week.
- Precedent: HOPS (graph parameter hierarchy) runs on GitHub Pages.

### Setup (decided 6 November 2026)

- Repository: `pear`, owned by the [algo-unsw](https://github.com/algo-unsw) organisation (moving from `serggasp/pear`).
- Domain: start on GitHub Pages (`algo-unsw.github.io/pear`). A custom domain is optional; if one is added, do it before entry URLs are announced or cited, since Pages URLs do not redirect.
- Stack: Python data pipeline (YAML data, pydantic schema, bound parser and comparator, derivation engine, pytest) writing JSON; Eleventy renders the site from that JSON, with KaTeX at build time. GitHub Actions: validate and test on every PR, build and deploy to Pages on merge to `main`.

### Repository skeleton (decided 7 November 2026)

- Code licence: MIT, "Copyright (c) 2026 the PEAR contributors". Data licence: CC0 1.0.
- The repository stays private until the site is ready to deploy (step 7); it must be public before the Pages deploy, since Pages on a private organisation repository needs a paid GitHub plan.
- Issue forms label new issues `suggestion` and `error-report`.

### Bound display and comparison (decided 7 November 2026, after the specs)

- A more precise bound beats a less precise one (comparison is implication between statements): $k^k$ beats $n^{O(k)}$, and $O(1.5^k + kn)$ beats $O^*(1.5^k)$.
- Derived bases are folded only when exact. A fold that needs rounding is shown on hover, rounded up: $1.5^{n/2}$ shows $1.2248^n$ on hover.
- $\omega$ is a named constant in `data/constants/`: $2 \le \omega \le 9/4$, the upper bound claimed (OpenAI preprint, 2 October 2026; constructive proof by Pass, arXiv:2610.28627). Claimed bounds are used in comparisons.

### Site build (step 7, 8 November 2026; in review)

- `python -m pear site` runs validation and the derivation engine and writes `build/site/site.json` (one page object per problem: overview groups, Details rows with chains, references numbered in order of first citation, reductions, related problems, implementations, bound history) and one JSON file per entry (`build/site/entries/`, served under `/data/`).
- Eleventy (`site/`) renders it; KaTeX typesets maths at build time and a TeX error fails the build. Pages: start page (pilot problems with best classical bounds), `/problems/<id>/`, `/cite/`.
- CI builds the site on every PR. `.github/workflows/pages.yml` deploys to GitHub Pages (algo-unsw.github.io/PEAR/) on merges to `main`. Public since 11 November 2026.
- Details lists only results that are best under some filter combination; beaten direct results appear only in the bound history (rulebook version 3, decided 10 November 2026).
- Bounds are displayed in O* form everywhere on the site (decided 10 November 2026); the exact form as stated stays in the data and the JSON.
- Bound history: from the results entered so far, verified and non-quantum, single-parameter bounds of the form $c^{a x}$; a step chart when there are at least two improvements.

### Overview tab and long chains (decided 7 November 2026)

- The Overview tab (the default view) shows the best non-quantum bound obtained by any means (direct or derived); it is not a separate section. The Details tab keeps the filters. If two bounds are equivalent (equal in O* form), the earlier is cited, by year; all are cited in case of a tie.
- Chains of reductions are followed as long as they improve results (rulebook version 2).
- When a reduction's parameter map misses a variable that only occurs in a polynomial factor, the O* form transfers (rulebook version 2, D2).
- Every bound, direct or derived, is projected onto single parameters through the constraints, and bounds compete within their parameters (rulebook version 2, D1): the bounds kept "by n" are the best expressible in n.
- Reduction variants are slight modifications of a reduction: another parameter map, an added known step such as a kernelization, or the same construction between other problems or versions. Site-written variants need Serge's approval (schema §6).

### Data schema (decided 7 November 2026)

The agreed schema is `docs/specs/schema.md`. Decisions:

- Paper IDs are surname+year slugs; DBLP keys are stored as identifiers.
- Versions that share bounds are declared in the problem file, not derived from reductions between versions.
- Structural parameters (treewidth, …) live in a shared registry, `data/parameters/`.
- A statement label is required for at least one open-access version of the cited paper; statement text is not stored.
- Lower bounds are in the schema; the pilot enters none. Hypotheses not claimed refuted (e.g. that CNF-SAT has no subexponential algorithm) remain valid bases.
- The randomized-error detail (Las Vegas / one-sided / two-sided) is an optional, display-only field.
- Serge alone gives final sign-off on pilot data.

## Usability at scale

- Search is the main entry point: alternative names, typos, shorthand like "vc k". Informal descriptions too ("fewest vertices touching every edge"): at build time a small open-source embedding model embeds each problem's definition and names (free, on Actions); in the browser the same model (about 20–30 MB, cached) embeds the query. No paid API, so bot traffic costs nothing. Google Programmable Search is only a fallback if this proves unfriendly; no Google link for now.
- Every page stays the same length: best bounds up front; older results, full history and long reduction lists behind a click.
- Consistent notation and tags, each with a short hover explanation.
- Links never break: merged or renamed problems redirect.
- Follow changes: "recently improved bounds" page, RSS feed or watch button per problem.
- Browse by category (graph problems, satisfiability, numbers, …).

## Design (decided)

Encyclopedia look, for desktop and mobile. See `DESIGN.md` and `../design/`.

- Best bounds first, right under the title; definition after, compact and collapsible.
- Overview view by default (prose-style results); Details view one click away (filters, tables with "proved for", origin, formal status).
- Version switcher tabs; the bound history is in the Details view; derived bounds expand to their chain.
- Dropped: Lean-first layout (too technical) and the reduction-map diagram (too busy).

## Licensing and citation

- Data: CC0. Code (site, scripts, curator skill): MIT.
- A "How to cite" page, and a stable, citable link for every entry.

## Phased build

1. **Pilot**: 12 problems (Vertex Cover, Independent Set, Clique, Set Cover, Hitting Set, SAT, #3-SAT, 3-Coloring, Hamiltonian Cycle, Dominating Set, Connected Dominating Set, Subset Sum), the bound expression language, derived bounds, and the chosen design.
2. **Launch**: about 100 problems, automated curation, error flagging and the approval queue.
3. **Growth**: OpenAlex tracker, bound history charts, Lean integration and the agent skill.

## Existing work

None of the resources found combines parameterized and exact bounds with bounds derived through reductions.

| Resource | What it covers | Relevance |
| --- | --- | --- |
| [Compendium of Parameterized Problems](https://betti.sprg.uniroma2.it/home/cesati/research/compendium) (Cesati) | 312 problems, 376 parameterized versions; last updated 2006 | Seed for problems and results |
| [Compendium at higher levels of PH](https://www.mdpi.com/1999-4893/12/9/188) (de Haan, Szeider 2019) | Parameterized problems above NP | Same compendium style |
| [Exact algorithms for NP-hard problems](https://mathopt.zib.de/Optima-Issues/optima68.pdf) (Woeginger) | Survey of exponential-time bounds | Early exact bounds |
| [Invitation to fine-grained complexity of NP-complete problems](https://arxiv.org/html/2601.05044) (Nederlof 2026) | Recent survey | Initial bounds and hypotheses |
| [Algorithm Wiki](https://futuretech.mit.edu/news/how-fast-do-algorithms-improve) (Sherry, Thompson, MIT) | History of best algorithms for 113 families | Closest "fastest algorithm" tracker; check overlap |
| [problem-reductions](https://github.com/CodingThrust/problem-reductions) (Rust) | 100+ NP-hard problems, 200+ executable reductions, agent-assisted contributions | No running-time bounds; model for agent workflow |
| [Karp](https://docs.racket-lang.org/karp/index.html) (PLDI 2022) | Racket DSL for writing and testing NP reductions | Possible format for checkable reductions |
| [poly-reductions](https://github.com/wimmers/poly-reductions) (Isabelle/HOL) | Formalised Karp reductions | Formal verification |
| [Descriptive Complexity in Lean](https://arxiv.org/pdf/2609.18261) (2026) | Lean catalogue of proved reductions; Karp's 21 plus 14 | Lean alignment; link per reduction |
| [Verified lattice NP-hardness](https://arxiv.org/pdf/2306.08375) (Kreuzer, Nipkow) | Isabelle proofs that found mistakes in published reductions | Supports error flagging |
| [HOPS](https://vaclavblazej.github.io/parameters/docs/about) / [Graph Parameter Hierarchy](https://manyu.pro/assets/parameter-hierarchy.pdf) (Sorge) | Graph parameters and bounds between them | Parameter relations; contribute back |
| [ISGCI](https://www.graphclasses.org) | Graph classes, inclusions, complexities | Model for automatic derivation |
| [The Karp Dataset](https://arxiv.org/pdf/2501.14705) (2025) | Natural-language NP-hardness reductions | AI-agent angle |

Garey and Johnson's *Computers and Intractability* (1979) is the natural seed for the initial 100.

## Open to-dos (from the plan)

- [x] Write the bound expression language and the reduction rulebook — **with the owner** (agreed 7 November 2026).
- [ ] Set up the GitHub repository with the data schema, then enter the 12 pilot problems.
- [ ] Add relations between parameters (e.g. treewidth ≤ pathwidth ≤ treewidth · O(log n)); HOPS is a possible source.
- [ ] Contribute improved parameter relations back to HOPS (github.com/vaclavblazej), after checking its contribution docs.
- [x] Refine the canonical definition format with the owner (agreed 7 November 2026).
- [x] Decide the optional randomized-error detail field (yes, optional and display-only).

## Decisions log

- 21 November 2026 (Serge): rebuild the comparison step. "Define the meaning of O* first", "rebuild the comparison step as a small decision procedure" (normal form with interval constants and explicit ε-families, compared tier by tier), "use a linear-programming solver first, then Z3 … anything it can't settle is reported as 'undecided' rather than guessed." Done in bounds.md §2 (Definition: uniform over the constrained domain, variables at least 2; approved by Serge the same day, "ok for the other decisions") and §5 (Procedure): exact rational LP certificates, checked again before use; Z3 (MIT, resource-limited) for polynomial growths; witnesses (slices of the domain) for failures; a new verdict **undecided**, listed under `open_comparisons`. On the current data every verdict of the old comparator is kept; one new proof changes Maximum Common Subgraph's Overview ($(n_G n_H)^{\omega k/3}$ now beats $1.1996^{n_G n_H}$ and $2^{n_G n_H/4}$, since $k \log(n_G n_H) = o(n_G n_H)$ for $k \le n_H$), approved the same day. Also on 21 November 2026 (Serge): "add individual constraints to problems. constraint k>=3 for k-Col as it is poly-time solvable for k<=2", so lower bounds beyond 2 are problem constraints with a reason: $k \ge 3$ for Chromatic Number, and with the same reason (checked by Claude, explained in each `because`) for Clique Cover, Edge Coloring and Edge Clique Cover. This drops $k^{0.793n}$ (Fomin–Heggernes–Kratsch via Graph Homomorphism) from those four Overviews. Then (Serge): "avoid parameter values where the problem is known to be polynomial time solvable, and add the corresponding explicit lower bounds per problem." Added, each with its polynomial algorithm in `because`: $k \ge 3$ for Equitable Coloring and Precoloring Extension, $h \ge 3$ for Graph Homomorphism, $p \ge 3$ for Multiway Cut. Rule applied: a parameter gets a lower bound $c$ when the problem is polynomial for every value below $c$ and NP-hard for some fixed value (so $c$ is where hardness starts); parameters for which every fixed value is polynomial (solution sizes, widths, numbers of terminals in Steiner problems, $k$ of $k$-Cut) get none, since no finite threshold follows from the rule. Edge Clique Cover's $k \ge 3$ is the exception (FPT, but $k \le 2$ is polynomial by a direct argument), kept as decided. Not added for lack of a checked source: Multicut $p \ge 3$ (two terminal pairs: two-commodity flow), Clique-Width $k \ge 4$ (recognition of clique-width at most 3), Edge Coloring with few vertices of maximum degree. "$\omega$ should be the current best value, not a range (current best unpublished/unverified 2.25 or current best published, depending on whether unverified results are displayed or not)": as decided on 18 November 2026; keeping a result checks both values.
- 21 November 2026 (Serge): no external engine for comparing running times; the comparator stays in-house ("let's keep it in-house"). SageMath's asymptotic expansions (AsymptoticRing) were evaluated: exact comparison of bases, polynomial and log factors, and products of independent variables, but no constraints between variables, no O\*, $o(\cdot)$, $\Theta$ or interval constants, no mixed growths such as $n^k$, and GPLv2+. Sage is used as a cross-check "not in CI, but as a check we run internally when adding new running times": `tools/sage_crosscheck.py` (bounds.md §5, CLAUDE.md).
- 20 November 2026 (Serge): "Max-Cut's $O^*(1.977^{m-k})$ algorithm is stated for parameter $k, m$. It should be stated for parameter $m - k$ instead. This is a general rule." A bound whose O* form depends on its variables only through one sum or difference of variables is listed under that expression (rulebook §7); competition (D1) still compares variables. Later the same day: $1.4423^{dk}$ and $2^{m-3n/5}$ keep their variables ("yes, keep their vars instead"), so products, other coefficients and higher degrees are listed under their variables. "Add the brute-force $O^*(2^n)$ algorithm for Max-Cut. Do not state running times slower than brute force (e.g. derived ones)." Brute force is entered (folklore, proved for the weighted version), which drops the derived $4^n$; folklore results now count as earliest, so brute force also drops later derived bounds equal to it and is the one cited (rulebook §9, Overview). "Resolve duplicate lines on the front page (and wherever else there are duplicate statements/bounds)": a bound is stated once per group on the front page and in the Overview (DESIGN.md, "One statement per bound"). Connected Dominating Set's deterministic $(\sqrt{5} - 1/2)^n 2^{o(n)}$ checked by Serge: correct.
- 20 November 2026 (Serge): "it should be recognized that k!·2^{o(k)} with k ≤ n gives n!·2^{o(n)}". The comparator raises variables of nondecreasing bounds along the constraints before the monomial check (bounds §5, item 9). PR #17 merged.
- 20 November 2026 (Serge): fix the comparison; add factorials, π and Bell numbers to the bound language; approve the new problem categories and shared parameters. The comparator no longer lets a positive coefficient that has beaten a smaller shape also be used up by monomials of its own shape (Subgraph Isomorphism: $2^{O(k)} n^{tw+1}\log n$ vs $O(n^k k^2 + n^2)$ is now incomparable). The language has `k!`, `B_{k}` and `\pi` (bounds §1, implementation notes).
- 20 November 2026 (Serge): approved the clarified definition of constructive (an algorithm that decides, optimises or counts without outputting a solution is constructive; `proved_for` records the version), and moving the rank-based Steiner Tree bound by treewidth of Bodlaender et al. to the bound history. PR #20.
- 20–21 November 2026 (Serge), on the independent review of all reported running times: (1) the rank-based Steiner Tree bound by treewidth is proved for the weighted version (Theorem 3.8 of arXiv 1211.1505 has edge weights); (2) yes to folklore baselines (brute force with a one-line argument) where derived bounds were worse; (3) ok to projecting only at the destination (rulebook §7, version 4); (4) drop the given-tree-decomposition flag on projections to $n$ and $m$; (5) yes to one entry per bound in Details, dropping derived rows that repeat a direct result of the same paper; (6) ok to showing XP and pseudo-polynomial bounds exactly (bounds §4); (7) no to a filter for results that rest on the claimed ETH refutation. Also merged: PR #22 (constants hidden inside O(·)) and PR #23 (Õ hides polylog(bound); ε subscripts substituted; projections keep subtracted constants; constraints keep their coefficient).
- 21 November 2026 (Serge): "Simple things like these should be decided by you, with a note on why it can be done." Claude decides simple, checkable steps (such as extending Theorem 3.8 of Bodlaender et al. to weight 0 by contracting zero-weight edges) and records the argument in the entry's note; the high-risk rules (CLAUDE.md rule 6) still apply to anything that is not simple.
- 18 November 2026: Monotone Local Search also takes inputs in time $c^{k + o(k)} N^{O(1)}$, including subexponential ones, and $\delta$-families $(c + \delta)^k$: they give $(2 - 1/c + \delta)^n$ for every $\delta > 0$ (Serge: a subexponential bound is $(1 + \epsilon)^k$ for every $\epsilon > 0$; $k \le n$ then usually gives a better bound directly). Las Vegas inputs count as one-sided error (stopped at twice the expected time); randomized inputs whose error is not recorded, and results through randomized reductions, are covered by Theorem 1 too. The comparator now reads $(c + \delta)^n$ for every $\delta > 0$ as the family $c^n 2^{\delta n}$. The reason that an algorithm for 3-Hitting Set solves its extension version is trivial and not stated.
- 18 November 2026: techniques approved, on condition that a technique is applied only when all its prerequisites are met (Serge). Monotone Local Search lists five checks with their places in arXiv v1 (rulebook §9a): the problem is $\Phi$-Subset (listed, with its universe and budget), the input solves the extension version (the problem records why, the input is for that version and needs no given structure), it runs in $c^k N^{O(1)}$ with constant $c > 1$, its randomness is covered by the theorem (Theorem 1: deterministic, one-sided or two-sided error, Remark 1; Theorem 2: deterministic), and it is classical. Candidates that fail one are logged with the reason.
- 18 November 2026: techniques (proposed): Monotone Local Search is entered once and the engine combines it with every compatible result (Feedback Vertex Set, Odd Cycle Transversal, Vertex Cover, 3-Hitting Set), so Feedback Vertex Set by $n$ gets $O^*(1.6297^n)$ randomized (Li–Nederlof) and $O^*(1.7110^n)$ deterministic (Iwata–Kobayashi). Fomin et al.'s Table 1 bound $1.7217^n$ is entered as unverified (it uses Kociumaka–Pilipczuk's $3.592^k$). The bound history follows the switch: preprints and unverified results (and $\omega$ claimed) only when included.
- 18 November 2026: comparisons use the current best value of $\omega$: published ($2.371339$, Alman et al., SODA 2025) by default, claimed ($9/4$) when preprints and unverified results are included; results are kept unless beaten at both. The bound history uses solid lines in different colours.
- 18 November 2026: whatever common sense decides, the engine should decide (bounds.md §5): nonnegative expressions from constraints and parameter maps, exact edge bound $m \le n(n-1)/2$ for graph problems, constant bases evaluated (with interval arithmetic for named constants), and a numeric cross-check that lists undecided pairs for Claude to resolve with a fact or rule; a test keeps it empty. Clique no longer lists $O^*(2^{n(n-1)/2-m})$.
- 18 November 2026: polynomial-space results are stronger than exponential-space ones, as deterministic ones are stronger than randomized ones (records and Overview ties). Kociumaka–Pilipczuk's $O^*(3.592^k)$ (arXiv v1, Theorem 1; not in the journal version) is entered as an unverified result: results can now be marked `unverified` themselves (schema.md §5).
- 18 November 2026: Vertex Cover and Independent Set get the constraint $n \le m$ without loss of generality (delete degree-0 and degree-1 vertices, with the weighted variant of the degree-1 rule), so the trivial $2^m$ is no longer a record: by $m$ they get $O^*(1.1996^m)$ from the algorithm in $n$ (Serge's suggestion).
- 18 November 2026: randomized algorithms are records only if faster than the fastest deterministic one (a deterministic algorithm is also a randomized one): bound history with deterministic and randomized records, and deterministic results preferred over randomized ones with the same bound in the Overview (DESIGN.md).
- 18 November 2026: the ESA 2009 and MFCS 2010 papers count as conference versions of van Rooij–Bodlaender–van Leeuwen–Rossmanith–Vatshelle (arXiv:1806.01667); a paper can be based on several conference papers, so a reference names all versions of the best kind (DESIGN.md, References).
- 18 November 2026: results from preprints (no journal, conference, workshop, book or thesis version) join unverified results: left out of the Overview and the front page by default, with one switch "Include preprints and unverified results" (Overview and front page), remembered in the browser across the site; Details unchanged (DESIGN.md).
- 18 November 2026: the two van Rooij–Bodlaender entries (STACS 2008, technical report 2009) are one paper, whose journal version is DAM 2011; Fomin–Gaspers–Saurabh (ISAAC 2006) was merged with another paper into Fomin–Gaspers–Saurabh–Stepanov (Algorithmica 2009), which counts as its journal version, so a version may carry its own `authors` (approved; schema.md §3); likewise STACS 2012 (Narayanaswamy, Raman, Ramanujan, Saurabh), which its authors call a preliminary version, is the conference version of Lokshtanov et al. (TALG 2014); Garey–Johnson–Stockmeyer, "Some Simplified NP-Complete Graph Problems" (Theoretical Computer Science 1976) is the journal version of their STOC 1974 paper; the deterministic Feedback Vertex Set bound of Fomin–Gaspers–Lokshtanov–Saurabh is corrected to $O(1.7237^n)$: Theorem 2 with the journal bound $(2+\phi)^k$ of Kociumaka–Pilipczuk instead of $3.592^k$.
- 17 November 2026: references name the journal version, else the conference version, else a technical report or preprint, with the cited statements and the version each is in ("Theorem 2 of arXiv v1"); a general rule (DESIGN.md, References). A version whose title differs from the paper's gives its own `title`, shown when the reference names that version (approved 17 November 2026; schema.md §3).
- 17 November 2026: Meijer's 3-Coloring bound is flagged (Yamano–Shibuya, Appendix F); for Kociumaka–Pilipczuk use the journal version, $(2+\phi)^k$; new notation $\varepsilon_k$ for bounds that hold for every fixed $k$ (bounds.md §2).
