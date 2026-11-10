# PEAR reduction rulebook

> **Status: agreed with Serge on 7 November 2026** (HANDOFF step 4; decisions R1–R7 at the end). Expands `docs/PLAN.md` → Rules for chaining reductions. The SERF definition in §5 was checked against the original paper on 7 November 2026.
>
> **Rulebook version: 3** (version 1: 7 November 2026; version 2, the same day: long chains are followed while they improve results, and polynomial factors transfer in O\* form; version 3, 10 November 2026: beaten direct results leave the Details list and stay in the bound history). Every derived bound records the rulebook version it was computed under. Changing an agreed rule is high risk (CLAUDE.md rule 6) and bumps the version, which recomputes all derived bounds.

The rulebook decides when an algorithm for a problem B, together with a reduction from A to B, gives a **derived bound** for A. Bounds use the language in `bounds.md`; reductions use the fields in `schema.md` §6.

## 1. Standing assumptions

- **A1. Parameter maps are upper bounds.** `parameter_map: { k: "2k" }` on a reduction from A to B means every produced instance of B has $k_B \le 2k_A$. Equalities are a special case.
- **A2. Bounds are monotone.** A stated bound is nondecreasing in each of its variables (for the large values that asymptotic statements are about). A1 and A2 together make substitution sound. The comparator refuses to substitute into a bound it cannot show to be monotone, such as one with a variable in a denominator.
- **A3. Only valid inputs count.** Results whose `status` is not `valid` or `fixed`, or whose hypothesis is `refuted`, are excluded from derivation. A result relying on a hypothesis that is `claimed-refuted` is still derived but carries that status (rule 7 of CLAUDE.md).

## 2. Polynomial-time many-one reductions (`calls: 1`)

For a reduction $R$ from A to B with own time $T_R$ and parameter map $\varphi$, and an algorithm for B with bound $f_B$:

$$T_A \;=\; T_R + f_B(\varphi(x_A)).$$

Under O* (the default display) $T_R$ disappears. The stored derived bound keeps the exact form, so it can still be compared on exact forms later (`bounds.md` §5.4). Example from the plan: $f_B = O^*(1.2^{k})$ and $k \mapsto 2k$ give $O^*(1.2^{2k}) = O^*(1.44^{k})$.

**Transfer condition** (from the plan): every variable of $f_B$ must be expressible through $\varphi$. If $f_B$ uses a parameter of B that the map does not cover, nothing transfers, with one exception (version 2): if the uncovered variables only occur in factors polynomial in N (e.g. the $n^3$ in $1.2^k n^3$), the O\* form of $f_B$ ($1.2^k$) transfers. This is sound because a polynomial-time reduction produces instances of polynomial size.

## 3. Polynomial-time Turing reductions (`calls` > 1)

$$T_A \;=\; T_R + \text{calls}(x_A) \cdot f_B(\varphi(x_A)).$$

- `calls` is an expression in A's variables (it may be polynomial; see R2 for more).
- **Call sizes.** If the paper's analysis exploits different call sizes (e.g. a recurrence), the reduction's `call_sizes` records it and that analysis is used instead. Otherwise every call is assumed to have the largest size, and the derived bound carries an *adaptive-sizes* flag: different sizes might give an improvement. These flags are listed on a page of open questions.

## 4. Randomness

- One randomized step (a `polytime-randomized` reduction or a randomized algorithm) makes the derived bound randomized.
- Error probabilities are handled by amplification: with $q$ calls, each randomized call is repeated $O(\log q)$ times, so the total error stays below a constant. This costs a factor polynomial in N, hidden in O*. The exact form records the factor as `\log(\text{calls})`.
- The optional error detail (Las Vegas / one-sided / two-sided) is not propagated. A derived bound shows only *randomized*.

## 5. SERF (subexponential reduction families)

**Definition** (Impagliazzo, Paturi, Zane, *Which problems have strongly exponential complexity?*, J. Comput. Syst. Sci. 63 (2001) 512–530, doi:[10.1006/jcss.2001.1774](https://doi.org/10.1006/jcss.2001.1774), §1.1.4, p. 515; [open copy](https://khoury.northeastern.edu/~viola/classes/papers/ImpagliazzoPaturiZane01Which.pdf)). A SERF from $(A, p)$ to $(B, q)$ is a family $\{R_\delta\}_{\delta > 0}$ of **Turing** reductions from A to B such that, for each $\delta > 0$:

- $R_\delta(x)$ runs in time $\mathrm{poly}(|x|)\, 2^{\delta p(x)}$;
- every query $x'$ to B has $q(x') = O(p(x))$ and $|x'| = |x|^{O(1)}$.

Our paraphrase, not the paper's wording. The paper writes $\varepsilon$; we write $\delta$, because $\varepsilon$ is reserved for non-explicit constants (`bounds.md` §2). The definition does not mention $\delta$ in the $O(\cdot)$. Its proof of Lemma 8 fixes one constant per member of the family, so we read the constant as possibly depending on $\delta$, written $C_\delta$ below. The measures $p$ and $q$ are *complexity parameters*: polynomial-time computable and polynomially bounded in $|x|$ (§1.1.2).

The paper's class SE contains the problems solvable in time $\mathrm{poly}(|x|)\, 2^{\delta m(x)}$ for every fixed $\delta > 0$ (§1.1.2). That is exactly the family form `O(2^{\delta m}) \text{ for every } \delta > 0` of `bounds.md` §2. SERFs compose (Lemma 8, p. 523), and SE is closed under them: if A SERF-reduces to B and B is in SE, then A is in SE (Lemma 9, p. 523). The transfer rule below is Lemma 9.

**Transfer (R3):** a SERF transfers only **subexponential** statements:

- if B has `O(2^{\delta q}) for every δ > 0`, then A has `O(2^{\delta p}) for every δ > 0`;
- concrete bases ($c^q \Rightarrow c'^p$) do **not** transfer, since $C_\delta$ is unknown and may grow as $\delta \to 0$;
- a SERF chain counts one step per SERF; composition is sound by Lemma 8.

For a SERF, `parameter_map` records only *which* measure maps to which ($q \mapsto p$, linearly); `time` and `calls` are implied by the definition.

## 6. Versions of one problem

- **Shared groups** (`shared_bounds`, schema Q2): a bound proved for one version in the group holds for all of them. This is not a chain step; the badge "proved for the … version" says where it comes from.
- **`generalises`** (e.g. weighted → unweighted): a bound for the general version transfers to the special case unchanged. A parameter that only exists in the general version (e.g. a maximum weight $W$) is set to its value in the special case ($W = 1$). This *is* a step, shown in the chain as "special case" (R5).

## 7. Composite parameters and projection

Substitution produces bounds in A's own variables, sometimes in combinations. For example, a map $k_B \mapsto n_A - k_A$ turns $1.5^{k_B}$ into $1.5^{\,n - k}$ for A.

- The derived bound is stored in that form and appears under the parameter combination it uses (here $n - k$).
- It is also **projected** onto single parameters using the problem's constraints (`bounds.md` B5) and A2: from $0 \le k \le n$, $1.5^{\,n-k} \le 1.5^n$. The projection competes in "by $n$" and is kept only if it is best or incomparable there (R4).
- **Every bound is projected** (version 2), direct or derived and in one parameter or several: $1.2^k$ with $k \le n$ gives $1.2^n$, and $1.1^m$ with $m \le n^2$ gives $1.1^{n^2}$. A projection is a derived bound.

## 8. Property inheritance

A derived bound is:

| Property | Rule |
| --- | --- |
| deterministic | only if every reduction and the final algorithm are deterministic |
| polynomial space | only if the algorithm is, every reduction runs in polynomial space, and calls are made one after another (their space is reused) |
| constructive | only if every step is |
| algebraic / uses fast matrix multiplication | if the algorithm is |
| quantum | if the algorithm is (quantum bounds are filtered out of the start page anyway) |
| conditional on | all hypotheses along the chain, dropping any that another one in the set implies (via `implies`) |
| Lean status | the weakest status along the chain |

## 9. Chaining and keeping bounds

- Derivation is a fixpoint computation over (problem, version) nodes. Starting from direct results, repeatedly apply every reduction to every currently best bound of its target, and keep a new bound only if no existing bound for that node and filter set strictly beats it. Stop when nothing changes.
- Each derived bound stores its full chain: direct result → reduction → … → result, with each step's type and parameter map.
- Chains longer than three steps get a small label so readers check more closely. Chains of any length are followed as long as they improve results (version 2): a chain is only extended from a result that is kept, and it never revisits a node, so the computation ends.
- Worse bounds are dropped, direct or derived (version 3). Best and incomparable ones are kept, under every filter combination the site offers (so the fastest deterministic polynomial-space bound is kept even when a faster randomized one exists). A dropped direct result leaves the Details list but stays in the bound history; a derived bound never drops a direct one, because "include derived" can be unticked.
- **Overview tab** (the default view, decided 7 November 2026): shows the best non-quantum bounds obtained by any means, direct or derived, compared in O* form; the Details tab lists every kept result with filters. Bounds equal in O* form are equivalent; the earlier one is cited, by year, and all of them in case of a tie. A derived bound dates from its latest dated ingredient (the algorithm's paper and each reduction's paper). Undated (folklore) results count as latest.

## 10. Not covered yet

- Transferring **lower bounds** (from A to B along a reduction from A to B). No lower bounds are entered in the pilot (schema Q5). Proposal: add this rule before the first lower bound is entered.
- **FPT-time parameterized reductions** and other reduction types: adding a type is high risk and needs Serge's approval.
- **Relations between parameters** (treewidth ≤ pathwidth, …) from HOPS: they will enter as constraints (§7) once agreed.

## Decisions (7 November 2026)

All seven were agreed as recommended:

- **R1** A1–A3 hold.
- **R2** `polytime-*` types need polynomial own time and polynomially many calls.
- **R3** A SERF transfers only subexponential statements.
- **R4** Composite parameters are kept and projected.
- **R5** Shared groups are free; "special case" is a counted step.
- **R6** Property inheritance as in §8.
- **R7** $T_R$ is kept in the stored exact form and simplified only for display.

Later the same day:

- **Overview tab**: shows the best non-quantum bound obtained by any means; equivalent bounds cite the earlier (by year), all on a tie (§9).
- **Long chains** (version 2): followed as long as they improve results; the ten-step limit is dropped (§9).
- **D2** (version 2): polynomial factors transfer in O\* form when the parameter map does not cover them (§2).
- **Projections** (version 2): every bound is projected through the constraints, not just composite derived ones (§7).
- **Beaten direct results** (version 3, 10 November 2026): dropped from the Details list like derived ones; they stay in the bound history (§9).
- **D1**: bounds compete within their parameters (implementation notes).

The questions as asked:

- **R1. Assumptions A1–A3.** Are parameter maps upper bounds, are stated bounds treated as monotone, and are results excluded or carried as in A3? *Recommend yes to all three.*
- **R2. Many calls.** Do `polytime-*` types require both polynomial own time **and** polynomially many calls? Reductions with exponentially many calls (branching into many instances of B) would then wait for a new, separately approved type. *Recommend yes (strict), adding an "exponential-time Turing" type when the first such reduction is needed.*
- **R3. SERF transfer.** Should a SERF transfer only subexponential statements, as in §5, never concrete bases? And can you confirm or correct the paraphrased SERF definition? *Recommend subexponential only.*
- **R4. Composite parameters.** Should derived bounds be kept in composite parameters (e.g. $n - k$), plus projected onto single parameters through the constraints? *Recommend yes.*
- **R5. Versions.** Shared groups are free (no chain step); "special case" via `generalises` is a step, shown in the chain and counted towards the three-step label. *Recommend this.*
- **R6. Property inheritance.** Is the table in §8 right? In particular: polynomial space through many sequential calls; and conditional hypotheses collected along the chain, dropping any implied by another. *Recommend the table as is.*
- **R7. Reduction time that dominates.** For the three agreed types this cannot happen under O*, since own time is polynomial. In the exact form, $T_R$ is kept as a term of the sum. Is that the treatment you want, or should the exact form drop $T_R$ when $f_B$'s exact form already dominates it? *Recommend keeping $T_R$ in the stored exact form and letting the comparator simplify for display.*

## Implementation notes (step 5b)

Code: `src/pear/derive.py`, run as `python -m pear derive` (writes `build/derived.json`: every kept result for the Details tab, and under `overview` what the Overview tab shows, per problem and node; CI runs it). Tests: `tests/test_derive.py`, one group per section above, on fictional data.

**Two choices agreed with Serge on 7 November 2026** (they change which bounds are derived or kept):

- **D1. Bounds compete within their parameters.** A derived bound is dropped only by a result whose parameters (the variables of its O* form) are a subset of its own. This is how §7 ("the projection competes in 'by $n$'") and §9 fit together: without it, every projection would be dropped by the bound it was projected from. Since every bound is projected (§7), the bounds kept "by $n$" are the best bounds expressible in $n$. For example, with $k \le n$, $1.2^k$ gives $1.2^n$, which drops a derived $1.5^n$. The Overview still shows only $1.2^k$, which beats $1.2^n$. Each result's `beaten_by` list names every strictly better bound. **Decided 7 November 2026: yes.**
- **D2. Polynomial factors transfer in O\* form.** If the parameter map misses a variable of B's bound that only occurs in factors polynomial in N (e.g. the $n^3$ in $1.2^k n^3$), the O\* form ($1.2^k$) is transferred instead of nothing. This is sound because a polynomial-time reduction produces instances of polynomial size. A strict reading of §2 would transfer nothing. **Decided 7 November 2026: yes**; now part of §2.

**Choices that follow from the rules:**

- **Nodes** are version classes: the versions in a `shared_bounds` group form one node (§6). A result's chain never revisits a node, so cycles terminate.
- **Exact form** of a polynomial-time transfer: the terms of $T_R$, then $\text{calls} \cdot t$ for each term $t$ of $f_B(\varphi)$ (R7), under $O^*$ or $\tilde O$ if B's bound uses it, otherwise $O$.
- **Amplification** (§4): only calls to a randomized algorithm for B are amplified, by a factor $\log(\text{calls})$, and only when the number of calls is an expression, not a constant.
- **SERF** (§5): B's bound transfers when the comparator shows it is at least as good as $O^*(2^{\delta q})$ for every $\delta > 0$. This includes $2^{o(q)}$ and $2^{\sqrt q}$, not $1.01^q$. A derived SERF bound has polynomial space only if the reduction records polynomial space.
- **Keeping** (§9): the filters are those in DESIGN.md (deterministic, polynomial space, constructive, non-algebraic, Lean-verified, include derived) plus classical vs quantum and the set of hypotheses. A result, direct or derived (version 3), is dropped when another is at least as good in every filter, listed under the same parameters or fewer (D1), and either strictly better in O* form, or equal in O* form, at least as good in exact form, and *earlier*. Equal in O* form and the same year counts as earlier only for the same algorithm by a shorter route, so different papers from the same year are all kept for citation. A derived result never drops a direct one. Dropped direct results are listed under `superseded` in `build/derived.json`, with the results that beat them, for the bound history (version 3, 10 November 2026; until then direct results were never dropped).
- **Projections** (§7) apply to every bound, direct or derived. They remove subtracted terms (all variables are nonnegative), then substitute every variable through the constraints onto any single parameter they reach. A projection is kept only if the comparator proves it is implied by the original. It is a chain step of kind `projection` that does not count towards the chain length. Projections are not projected again, because constraints are closed transitively.
- **Unverified papers and given inputs** (8 November 2026): a result whose chain cites a paper marked `unverified` is tagged and left out of the Overview, and it never drops a verified result (it counts as a filter dimension). A `given` input (a tree decomposition) is carried along the chain as a flag.
- **Lean-verified** means every step is `proved` with prover Lean. The `formal` status is the weakest along the chain.
- **Variants** (schema §6) are used as reductions of their own, between the variant's problems and versions, cited as `<reduction>~<variant>`, with the variant's note shown in the chain. A derived bound through a variant dates from the later of the reduction's and the variant's papers. Variants written by the site are used only once approved, and flagged.
- **Not covered:** parameters that exist only in a general version (e.g. a maximum weight set to 1 in the special case) are not substituted, because parameters are defined per problem, not per version.
