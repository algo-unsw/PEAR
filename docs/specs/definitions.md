# Canonical problem definitions — DRAFT for review

> **Status: draft, not agreed.** Proposed 7 November 2026 (HANDOFF step 6, "refine the definition format with the owner" in PLAN.md). The structure of a problem file is already agreed (`schema.md` §2). This spec proposes the **conventions** a definition follows. Worked example: `data/problems/vertex-cover.yaml`. Open questions are **F1–F7**, collected at the end.

Every problem has exactly one canonical definition, because small differences quietly change bounds (PLAN.md). The conventions below make two definitions written months apart read alike, and make it clear which results apply.

## 1. Objects

- **Graphs** are finite, simple and undirected unless the definition says otherwise (directed, multigraph, with loops). $G = (V, E)$, $n = |V|$, $m = |E|$ (F1).
- **Set systems** are a finite universe $U$ and a family $\mathcal{F}$ of subsets of $U$: $n = |U|$, $m = |\mathcal{F}|$.
- **Formulas** are in conjunctive normal form over variables $x_1, \dots, x_n$, with $m$ clauses.
- **Numbers** in the input are integers given in binary (F6).

## 2. Sizes

- `objects` states exactly what $n$ and $m$ count (CLAUDE.md rule 4).
- $N$ is the length of a standard binary encoding: graphs and set systems as adjacency or incidence lists, numbers in binary (F2). Bounds are stored as stated, so this only matters where a bound states an explicit factor in $N$.

## 3. Versions

| Kind | Fields | Output |
| --- | --- | --- |
| decision | `input`, `question` | yes or no |
| optimisation | `input`, `goal` | the optimum value (F3) |
| search | `input`, `goal` | a solution meeting the bound in the input, or "none" |
| counting | `input`, `goal` | the number of solutions |

- The property that defines a solution is worded **identically** in every version, so the versions visibly differ only in what is asked.
- Weighted and other genuinely different versions are versions of the same problem with `generalises`. Distinct problems (Connected Vertex Cover) get their own file (PLAN.md).

## 4. Parameters

- A parameter means the same thing in every version, with one exception. The **solution size** $k$ is the integer in the input for decision and search, and the optimum for optimisation (F4).
- Structural parameters point to the shared registry (`data/parameters/`) and say **which graph** they are measured on, where there is a choice. For example, for SAT the primal graph and the incidence graph give different treewidths (F5).
- Constraints between parameters (`bounds.md` B5) may rely on **trivial polynomial-time preprocessing**, said so in their justification. For Vertex Cover, $k \le n$ holds after answering "yes" whenever $k \ge n$ (F7).

## 5. Wording

- **Input**: one sentence, ending with a full stop: "A graph $G = (V, E)$ and an integer $k$."
- **Question**: "Is there …?" **Goal**: "Find …".
- Solutions are named $S$ where possible. Maths is written in `$…$`, and Greek letters always as TeX commands (`\omega`, never a Unicode character; CLAUDE.md rule 10).
- `name` is in Title Case. `aliases` lists other common names and abbreviations ("VC").

## Open questions

- **F1. Graph default.** Finite, simple, undirected unless stated? *Recommend yes.*
- **F2. Input size.** $N$ is the length of a standard binary encoding, with graphs as adjacency lists and numbers in binary? *Recommend yes.*
- **F3. Optimisation output.** The optimum *value*, with "find an optimal solution" left to the search version or the *constructive* tag? *Recommend the value.* For self-reducible problems such as Vertex Cover, value and solution are equivalent anyway, as `shared_bounds` records.
- **F4. Meaning of $k$.** The input integer in decision and search, the optimum in optimisation, under one symbol? *Recommend yes.* Papers' "parameterized by the solution size" results then attach to all three versions, which share bounds.
- **F5. Shared parameters on a chosen graph.** Add an optional `of` to a shared-parameter reference, such as `tw: { shared: treewidth, of: "the primal graph" }`? *Recommend yes.* This is a small schema addition.
- **F6. Weights.** Nonnegative integers in binary, with $W$ (maximum weight) as a parameter where results need it (`poly_bounded: false`)? *Recommend yes.*
- **F7. Preprocessing in constraints,** and **a source for classic NP-completeness results.** Karp's 1972 chapter is not open access (checked on SpringerLink on 7 November 2026), so `complexity.source` for Vertex Cover is `TODO(verify)`. Options: an open-access textbook with a numbered statement, or a Lean formalisation where one exists. Which do you prefer?
