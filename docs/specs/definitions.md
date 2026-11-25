# Canonical problem definitions

> **Status: agreed with Serge on 7 November 2026** (HANDOFF step 6; decisions F1–F7 at the end). The structure of a problem file is in `schema.md` §2. This spec sets the **conventions** a definition follows. Worked example: `data/problems/vertex-cover.yaml`. Changing it is the owner's decision.

Every problem has exactly one canonical definition, because small differences quietly change bounds (PLAN.md). The conventions below make two definitions written months apart read alike, and make it clear which results apply.

## 1. Objects

- **Graphs** are finite, simple and undirected unless the definition says otherwise (directed, multigraph, with loops). $G = (V, E)$, $n = |V|$, $m = |E|$ (F1).
- **Set systems** are a finite universe $U$ and a family $\mathcal{F}$ of subsets of $U$: $n = |U|$, $m = |\mathcal{F}|$.
- **Formulas** are in conjunctive normal form over variables $x_1, \dots, x_n$, with $m$ clauses.
- **Numbers** in the input are integers given in binary (F6).
- **Weights** are nonnegative integers in binary by default, with $W$ (maximum weight) as a parameter where results need it (`poly_bounded: false`). A problem may define its weights differently (real, negative, unary, …); its definition then says so explicitly (F6).

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
- **Weights are positive integers** (Serge, 26 November 2026): a weight function is $w \colon X \to \mathbb{Z}_{\ge 1}$ unless the problem needs otherwise. Results proved for nonnegative or real weights cover it; results proved for weights $\ge 1$ need no extra step. Other quantities keep the domain the problem needs: capacities, costs, profits, penalties, demands and thresholds may be 0, and Max 2-CSP's scores are arbitrary integers. A weighted version's minimum weight or weight budget is its own parameter, $k_w$ (25 November 2026).
- **Bounded-degree versions** (Serge, 21 November 2026). A result proved only for graphs of maximum degree at most $d$ goes to a version `<version>-max-degree-<d>` of the same problem, for example `optimisation-max-degree-3`. Its input adds "of maximum degree at most $d$" and is otherwise worded identically. Versions form a chain in `generalises` (its bounds hold in the larger class too): the general version lists the largest $d$, and each bounded-degree version lists the next smaller $d$ that exists. Listing every $d$ in the general version would make the same bound reach a version along several chains (decided 21 November 2026; the chain is equivalent, since bounds flow along it transitively). If the general versions share bounds, the bounded-degree versions with one $d$ form their own `shared_bounds` group, with the same justification if it still applies (say so if self-reducibility needs larger degrees). Only versions that results need are added.
- **Restricted-input versions** (Serge, 21 November 2026). The same scheme holds for other input restrictions: a fixed input integer, `<version>-<letter>-<d>` or `<version>-<letter>-at-least-<d>` (k-Path Vertex Cover `decision-d-3`, Bounded-Degree Vertex Deletion `decision-d-at-least-3`), and a bound on thresholds, `<version>-max-threshold-<d>` (Target Set Selection). They are linked by `generalises` like the bounded-degree versions.

## 4. Parameters

- A parameter means the same thing in every version, with one exception. The **solution size** $k$ is the integer in the input for decision and search, the optimum for optimisation, and the minimum weight for a weighted version that uses it (F4; weighted case 21 November 2026, as in Multiway Cut and Vertex Cover).
- Structural parameters point to the shared registry (`data/parameters/`) and say **which graph** they are measured on only where there is a choice; with a single input graph, as in Vertex Cover, it is left out. For example, for SAT the primal graph and the incidence graph give different treewidths (F5).
- Constraints between parameters (`bounds.md` B5) may rely on **trivial polynomial-time preprocessing**, said so in their justification. For Vertex Cover, $k \le n$ holds after answering "yes" whenever $k \ge n$ (F7).

## 5. Wording

- **Input**: one sentence, ending with a full stop: "A graph $G = (V, E)$ and an integer $k$."
- **Question**: "Is there …?" **Goal**: "Find …".
- Solutions are named $S$ where possible. Maths is written in `$…$`, and Greek letters always as TeX commands (`\omega`, never a Unicode character; CLAUDE.md rule 10).
- `name` is in Title Case. `aliases` lists other common names and abbreviations ("VC").
- Exception to using the most widely used name (Serge, 21 November 2026): Travelling **Salesperson**, not Salesman, everywhere on the site and in PEAR's own text, ids included (`travelling-salesperson`). "Salesman" stays only among the aliases ("also known as", which search uses), in paper titles, and in search phrases for external counts.

## Open questions

## Decisions (7 November 2026)

- **F1** Graphs are finite, simple and undirected unless stated.
- **F2** $N$ is the length of a standard binary encoding (graphs as adjacency lists, numbers in binary).
- **F3** The optimisation version outputs the optimum value.
- **F4** $k$ is the input integer in decision and search, and the optimum in optimisation, under one symbol.
- **F5** A shared-parameter reference may say which graph or object it is measured on (`of`, schema §2).
- **F6** Weights are nonnegative integers in binary by default; a problem may define them differently.
- **F7** Constraints may rely on trivial polynomial-time preprocessing. A classic result whose paper is not open access (Karp 1972) is cited as such. It needs no reading of the paper when a web search finds independent sources that confirm it: at least three, on different sites, recorded in `attested_by` (schema §4; CLAUDE.md rule 2).
