# PEAR bound expression language

> **Status: agreed with Serge on 7 November 2026** (HANDOFF step 4; decisions B1–B6 at the end). Expands `docs/PLAN.md` → Bound expression language. Implementation: step 5. Changing it is the owner's decision.
>
> Examples use arithmetic only; no bound here is a research claim.

This spec says how a running time is written in a data file, what it means, how it is displayed, and when one bound beats another. How bounds move along reductions is the rulebook (`rulebook.md`).

**Design principle: the comparator is sound but incomplete.** When it cannot prove that one bound is at most another, both stay on the site. It calls them incomparable only with a witness each way, and otherwise **undecided** (21 November 2026). Errors can then only make the list of best bounds too long, never drop a correct best bound.

## 1. Syntax

A bound is written in `as_stated` **as the paper prints it, in a TeX subset** that KaTeX renders directly, so the site shows the exact form without a second copy (B1). Examples of accepted strings:

```text
O(1.5^{k} + kn)                 O^*(2^{tw})            \tilde{O}(2^{n/2})
O^*(2^{O(\sqrt{k})})            n^{O(k)}               O((2-\varepsilon)^{n})
O^*(k^{k})                      O(2^{n} n^{2})         f(k) \cdot n^{O(1)}
```

Grammar (whitespace and `\,`, `\cdot`, `\times` between factors are ignored):

```text
bound     := [ notation "(" ] sum [ ")" ] [ "\text{ for every } \delta > 0" ]
notation  := "O" | "O^*" | "\tilde{O}"
sum       := term { "+" term }
term      := factor { factor }
factor    := atom {"!"} [ "^" "{" exponent "}" ] | "\log" ... | "\sqrt{" sum "}" | "(" sum ")"
atom      := number | "\pi" | "\mathrm{e}" | variable | constant | "f(" variable ")" | "B_{" sum "}"
exponent  := sum | asymptotic
asymptotic:= ("O" | "o") "(" sum ")"
constant  := "\varepsilon" ["_" (variable | "{" variable {variable} "}")] | "\omega" | named constant from data/constants
variable  := a symbol the problem defines (objects or parameters)
```

**Factorials, Bell numbers, π and e** (20–21 November 2026): `k!` and `(tw + 1)!` are factorials, `B_{k}` (or `B_k`) is the $k$-th Bell number, the number of partitions of a $k$-element set (so `B` cannot be a problem's symbol), `\pi` is π, and `\mathrm{e}` is Euler's number e (added 21 November 2026; written `\mathrm{e}` so that `e` stays free as a symbol). Bounds stated with them are stored as stated.

**Comparator rules of 21 November 2026** (approved by Serge, rule 6): (1) an exponent with subtracted parts over a base whose logarithm needs no estimate, such as $n^{n-k}$, is analysed exactly; (2) a monomial in several variables is dominated by one in fewer variables through the constraints, $k \log n \le n \log n$ for $k \le n$; (3) a monomial cancels against a larger one whose coefficient is a positive multiple of minus its own, so $(1 - \omega/3)(n \log n - k \log n) \ge 0$ is seen whatever $\omega$ is; (4) O* comparisons are also made on the O* forms, after polynomial factors such as $(n-k)^2$ are dropped; (5) equal exponents over bases that compare pointwise, and sums and products matched part by part, compare pointwise: $(d+1)^k \le (d+2)^k$. (6) An unknown constant from $O(\cdot)$ in the smaller bound cancels through a constraint $x \le c\,y + c'$ with any positive constants, whose other terms then carry unknown constants too: with $p \le 2k$, $2^{O(p)}$ beats $2^{O(k \log k)}$ but never $2^k$ or $3^k$ (21 November 2026, for the Steiner Forest parameter $p$; approved by Serge the same day). Since the certificate engine (`decide.py`), such constraints enter only its log-domain linear programs, as rows $u_x - p\,u_y \le \log_2 c$ (an additive constant is folded in, as every variable is at least 2: $t \le k + 1$ gives $t \le 1.5k$); they stay out of `le`, whose rules need $c \le 1$ (22 November 2026).

The parser also checks what the schema could not: every variable in `as_stated`, `time`, `calls` and parameter-map right-hand sides is defined by the problem, and `bound.parameters` lists exactly the variables of `as_stated`. The `notation` field must match the outer notation of `as_stated` (or be `O` when there is none).

## 2. Meaning

A bound is an upper bound on the worst-case running time, as a function of the variables, for all inputs. Asymptotic notation is taken uniformly over all inputs, in all variables at once (precise definition at the end of this section).

- **Hidden factors.** `O` hides a constant. `O^*` hides a factor polynomial in the input size N. `\tilde{O}` hides a factor polylogarithmic in the bound itself.
- **Asymptotics inside exponents.** `2^{O(\sqrt{k})}` means $2^{c\sqrt{k}}$ for some unknown constant $c > 0$. `n^{O(k)}` means $n^{ck}$ for some $c$. `2^{o(n)}` means one algorithm with time $2^{g(n)}$ for some $g = o(n)$.
- **Families of algorithms.** "For every $\delta > 0$ there is an $O(2^{\delta n})$-time algorithm" is weaker than `2^{o(n)}` (the algorithm may depend on $\delta$), and is written `O(2^{\delta n}) \text{ for every } \delta > 0`. Both forms beat every $c^n$ with explicit $c > 1$; they are kept distinct because hypotheses such as ETH are stated in the family form. A base $c + \delta$, as in `O((1.75 + \delta)^{n}) \text{ for every } \delta > 0`, is read as the family $c^n 2^{\delta n}$: it beats every $c'^n$ with $c' > c$ and is beaten by $c^n$ (18 November 2026).
- **Non-explicit constants** (plan rule). `(2-\varepsilon)^n` means "for some unknown $\varepsilon > 0$". It is treated as a positive infinitesimal: $(2-\varepsilon)^n$ beats $2^n$, but every explicit $c < 2$ beats $(2-\varepsilon)^n$.
- **Constants depending on parameters** (17 November 2026). `(2-\varepsilon_{k})^n` means "for every fixed $k$ there is an unknown $\varepsilon_k > 0$": the bound holds for every fixed value of the subscripted parameters, and every hidden constant (in $O(\cdot)$, $O^*$, $\varepsilon$) may depend on them. Example: $k$-Coloring in $O((2-\varepsilon_k)^n)$ (Pratt; Zamir, 2026). The subscript lists parameters, written `\varepsilon_k` or `\varepsilon_{k}`. Such a bound is listed under its subscripted parameters too, and the site says "for every fixed $k$". It is compared only with bounds fixed in the same parameters (as with plain $\varepsilon$ among them); against any other bound it is incomparable, since a uniform bound and a bound for every fixed $k$ do not imply each other in general.
- **`\omega`** and other named constants are kept symbolic in the stored and displayed bound. Comparisons cancel them symbolically ($n^\omega$ equals $n^\omega$) and otherwise use the best known lower and upper bounds recorded with sources in `data/constants/` (schema §11). So a bound stated in $\omega$ improves automatically when $\omega$'s bound does. Claimed bounds count; refuted ones do not. Currently: $2 \le \omega \le 9/4$, the upper bound claimed (decided 7 November 2026).
- **`f(k)`** is an unspecified computable function (B3).

### Definition (agreed with Serge, 21 November 2026)

With several variables and constraints between them, the usual definitions of $O$ do not agree, and the obvious one ("for all sufficiently large values of every variable") breaks rules that algorithm analysis uses all the time, such as bounding the cost of a loop by summing the bound of each iteration (Howell, Theorem 2.1), while the alternative "for all sufficiently large values of some variable" fails to absorb lower-order terms when variables may be 0: $mn + 1 \notin O(mn)$, since $mn = 0$ at infinitely many points (Howell, Section 2; see also Rutanen et al. 2013 on the summation rule). That example does not arise on PEAR's domain, which excludes 0 (item 1): there $mn \ge 4$, so $mn + 1 \le \tfrac54 mn$. PEAR uses the following definition, chosen because it is how parameterized results are meant: $f(k) \cdot n^{O(1)}$ holds for **all** $k$ and $n$, not only for large ones.

1. **Domain.** A problem's variables $x = (n, m, k, \mathit{tw}, \ldots)$ range over $D$: the points with integer coordinates **at least 2** that satisfy the problem's declared constraints (B5). Logarithms are base 2, so $\log x \ge 1$. Values 0 and 1 are left out on purpose, as $\log x$ is usually read as $\max(1, \log x)$: otherwise $k^n$ at $k = 1$ would make $2^n$ worse than $k^n$ for $k$-Coloring. (The comparator before 21 November 2026 assumed this implicitly.) Larger lower bounds are **individual constraints of a problem**, with a reason, typically that the smaller values are solvable in polynomial time, so that they cannot separate two bounds in O\* form: $k \ge 3$ for Chromatic Number, since $k \le 2$ is polynomial (Serge, 21 November 2026). The rule: a parameter gets a lower bound $c$ when the problem is polynomial for every value below $c$ and NP-hard for some fixed value; a parameter for which every fixed value is polynomial (a solution size, a width) gets none (PLAN.md decisions log lists the bounds added). Without it, $k^{0.793 n}$ would survive next to $2^n$ only because of $k = 2$. "Sufficiently large" is otherwise not used: for all instances of size $N \ge N_0$ would be equivalent (finitely many points of $D$ have $N < N_0$, and $C$ absorbs them), and for every variable sufficiently large would drop bounds that are best for small values of a parameter and break substitution along reductions such as $k \mapsto m - k$.
2. **Big-O.** For positive functions on $D$: $f = O(g)$ on $D$ iff there is a constant $C$ with $f(x) \le C\, g(x)$ for **every** $x \in D$. There is no "sufficiently large": small values of one variable with large values of another count.
3. **$O^*$.** $f = O^*(g)$ iff $f = O(g \cdot p(N))$ for a polynomial $p$ of the input size $N$; variables are polynomially bounded in $N$ unless marked (B4), so $p(N)$ also absorbs polynomials in them. **$\tilde O(g)$** hides a factor $(\log g)^{O(1)}$ in the same way.
4. **Inside exponents.** $h = o(\varphi)$ on $D$ iff for every $\varepsilon > 0$ there is $C$ with $h \le \varepsilon \varphi + C$ on $D$; $h = O(\varphi)$ iff $h \le c\,\varphi + C$ for constants $c, C$. So $2^{o(n)}$ is $2^{h}$ for one such $h$.
5. **Statements.** A bound with unknowns (constants of $O$, $O^*$ and $\tilde O$, functions of $o$, $\varepsilon$) states that **some** choice of the unknowns makes it an upper bound on $D$. A family ("for every $\delta > 0$") states it for every $\delta$, possibly with a different algorithm each time; $\varepsilon_k$ and constants depending on $k$ are chosen for each fixed $k$ (as above).
6. **At least as good.** $A \preceq B$ iff $A$'s statement implies $B$'s: for **every** choice of $A$'s unknowns there is a choice of $B$'s unknowns with $A = O(B)$ on $D$ (in O\* form: $A = O^*(B)$). Equivalently, $g = \log_2 B - \log_2 A$ is **bounded below on $D$**, for every choice of $A$'s unknowns and a suitable choice of $B$'s. Named constants take their current best value (§5 item 7).
7. **Verdicts.** $A$ is **better** than $B$ if $A \preceq B$ and $B \not\preceq A$; **equal** if both hold; **incomparable** if neither holds; and **undecided** if the comparator can show neither $A \preceq B$ nor its failure (no certificate, no witness, §5). Undecided pairs are kept like incomparable ones and listed under `open_comparisons` in `build/derived.json`.

Consequences used throughout: $\preceq$ is transitive; a sum is $O$ of its largest term; substituting a reduction's parameter map ($k \mapsto m - k$) into a bound that holds on the target's domain gives one that holds on the source's domain, if the map sends the source's domain into the target's. Integer points are not needed for proofs: the comparator proves inequalities on the real points satisfying the constraints, a larger set.

References: Rodney R. Howell, *On Asymptotic Notation with Multiple Variables*, Technical Report 2007-4, Kansas State University, dated 18 January 2008, <https://people.cs.ksu.edu/~rhowell/asymptotic.pdf>. Kalle Rutanen, Germán Gómez-Herrero, Sirkka-Liisa Eriksson, Karen Egiazarian, *A general definition of the big-oh notation for algorithm analysis*, arXiv:1309.3210v1, 2013, <https://arxiv.org/abs/1309.3210v1> (the abstract: the prevailing definition "fails to satisfy properties that are commonly assumed from it"; Definition 4.60 is the summation rule $O(f + g) = O(\max(f, g))$). Later versions are by Kalle Rutanen alone, retitled *O-notation in algorithm analysis* (v32, 29 October 2016).

## 3. Internal normal form (for comparison only)

**Nothing is ever displayed in this form (B2).** Pages show bounds in their most natural form, as papers write them: $k^k$, not $2^{k \log k}$ (§4).

For comparison, the comparator rewrites each term internally as $2^{G}$, where the **growth exponent** $G$ is a sum of monomials

$$c \cdot x^{\alpha} (\log x)^{\beta} (\log\log x)^{\gamma}$$

with one variable $x$ per monomial; real $\alpha, \beta, \gamma \ge 0$; and a coefficient $c$ that is a real number, a real number shifted by an infinitesimal ($2-\varepsilon$ gives $\log_2(2-\varepsilon) = 1 - \varepsilon'$), or the unknown positive constant of an inner `O(·)`. For example:

| Stated | Growth exponent $G$ |
| --- | --- |
| $1.5^k$ | $(\log_2 1.5)\, k$ |
| $k^k$ | $k \log k$ |
| $2^{\sqrt{k}}$ | $k^{1/2}$ |
| $n^2$ | $2 \log n$ |
| $n^{O(k)}$ | $c\, k \log n$ with $c$ unknown: a product of two variables, kept as one mixed monomial |

Mixed monomials (several variables, as in $k \log n$) are allowed and compared only when every variable matches.

## 4. Display

Bounds are displayed in their **natural form** (B2): the stated factors, as written.

**O* form (shown by default).** Start from the stated form, then:

- drop every factor polynomial in the input size N: polynomial and logarithmic factors in variables that are polynomially bounded in N;
- drop every term dominated by another term (§5). `O(1.5^{k} + kn)` becomes $O^*(1.5^k)$. `O(2^{k} + 1.5^{n})` stays a sum unless the problem's parameter constraints decide it.
- hide the constants that $O(\cdot)$ and $O^*$ hide (20 November 2026). Inside $O(\cdot)$ and $o(\cdot)$ the argument takes its simplest form up to a constant factor: constant factors, constant terms, log bases, constant powers inside logs and dominated summands go, so $2^{O(2n (\log\log(2n))^2/\sqrt{\log(2n)})}$ becomes $2^{O(n (\log\log n)^2/\sqrt{\log n})}$ and $2^{O((2\mathit{tw}+1)\log(2\mathit{tw}+1))}$ becomes $2^{O(\mathit{tw}\log\mathit{tw})}$. A sum that subtracts a term with variables, such as $n(n-1)/2 - m$, keeps its form, unless it has one variable and the subtracted terms are of smaller order: $o(k 2^k - k)$ is $o(k 2^k)$. Next to an $O(g)$ or $o(g)$ summand, a summand of order $O(g)$, respectively $o(g)$ in one variable, is absorbed, added or subtracted: $(2\mathrm{e})^{k 2^k - k + o(k 2^k - k)}$ is shown as $(2\mathrm{e})^{k 2^k + o(k 2^k)}$, while $2^{nk - n + o(nk)}$ keeps $-n$, which is not $o(nk)$ when $k$ stays bounded (21 November 2026). For a numeric base, a constant shift in the exponent is a constant factor: $2^{t-1}$ becomes $2^t$. For a variable base the exponent stays as stated: $n^{k+o(1)}$ and $n^{\mathit{tw}+1}$ are what the result is about. A derived bound's exact form, which the engine wrote, hides constants the same way term by term under its outer $O$, $O^*$ or $\tilde O$ (each term stays, such as a reduction's time, R7, but repeated terms are merged); a stated bound's exact form is the paper's. The comparator reads bounds the same way, since $O(2n/\log(2n))$ and $O(n/\log n)$ are the same statement.
- **XP and pseudo-polynomial bounds are shown exactly** (Serge, 20 November 2026), since $O^*$ hides what they are about: a power of an input size ($n$, $m$, $N$) whose exponent has a parameter ($n^{k+o(1)}$ and $n^{k+1}$ are the same in $O^*$, as are $2^{O(k)} n^{tw+1}$ and $2^{O(k)} n^{tw}$), or a bound polynomial in values that are not polynomially bounded (Subset Sum's $\sqrt{n}\,t\log^{5/2} t$, $\tilde O(n+t)$ and $\tilde O(n^3 t \log t)$ all read $O^*(t)$). A stated one is shown as stated, in its notation; a derived one in its exact form with constants hidden and dominated terms (such as a reduction's time) dropped. Exact exponential algorithms ($k^n$, $n^n$) keep $O^*$.

**Polynomially bounded variables (B4).** By default every variable is treated as polynomially bounded in N, silently, with no declaration and no note on the page. Only exceptions are marked `poly_bounded: false` in the schema: for example, a number in the input such as Subset Sum's target $t$, so that $t^2$ and $t$ stay different under O*.

**Derived bounds.** Substitution (rulebook §2) produces new expressions, which are simplified only within the natural form:

- folding constants **only when the result is exact**, with at most four decimals: $1.2^{2k}$ becomes $1.44^{k}$, and $2.25^{n/2}$ becomes $1.5^n$;
- collecting like factors.

A fold that would need rounding is **not** made, because a rounded-up base is a weaker bound. The exact form is shown, and the fold, with its base rounded up to four decimals, appears on **hover**: $1.5^{n/2}$ shows $1.2248^n$ on hover, and $1.2738^{2k}$ shows $1.6226^k$ (decided 7 November 2026). The same hover is offered for stated bounds such as $2^{n/2}$ (hover $1.4143^n$); stated bounds themselves are never folded. A substituted expression with no simpler natural form stays as it is: $1.5^{\,n-k}$, $(2k)^{2k}$.

## 5. Comparison

$A \preceq B$ ("$A$ is at least as good as $B$") means **$A$'s statement implies $B$'s**: whatever the unknowns in $A$ are (constants hidden by $O(\cdot)$, the polynomial hidden by $O^*$, an $o(\cdot)$ function, $\varepsilon$), $B$'s unknowns can be chosen so that $A = O(B)$ on all inputs. So **a more precise bound beats a less precise one** (decided 7 November 2026):

- $k^k$ beats $n^{O(k)}$ under $k \le n$;
- $O(1.5^k + kn)$ beats $O^*(1.5^k)$, and $O(2^n n)$ beats $\tilde O(2^n)$;
- $2^{\sqrt{k}}$ beats $2^{O(\sqrt{k})}$, and $2^{\sqrt{n}}$ beats $2^{o(n)}$;
- identical statements, such as two copies of $2^{O(\sqrt{k})}$, are equal.

**Procedure** (21 November 2026). After the normal form (§3), a comparison of two terms is the question of definition item 6: is a sum $g = \sum_K c_K K(x)$ of monomials $K = \prod x^\alpha (\log x)^\beta (\log\log x)^\gamma$ bounded below on $D$? The comparator answers it in tiers, each tried only when the one before fails (`decide.py`, `disprove.py`):

1. **A certificate from linear programming.** Monomials with a negative part ("demands") are paid for by monomials with a positive part ("supplies") along **edges**: $K \le \kappa K' + C$ on $D$ (weak) or $K = o(K')$ on $D$ (strict). A strict edge between tiers, such as exponential ($2^{cn}$) over subexponential ($2^{c\sqrt n}$) over polynomial ($n^c$), lets any positive leftover pay any amount; within a tier, payment is at rate $\kappa$. Expressions known to be nonnegative (item 6 below) may be subtracted with multipliers $\lambda \ge 0$. Whether all leftovers can be made nonnegative is a linear program, solved exactly over the rationals (`lp.py`); its solution is the **certificate**, checked again by an independent routine (`verify`) before it is accepted. Edges come from the per-variable rules below (items 2, 3, 9) and from linear programs in log coordinates: with $u = \log_2 x$ the constraints $x \le c\,y^p$ are linear, so whether one power monomial is at most a constant times another, or of lower order, is itself a linear program. The unknowns of the statements enter as rules for who pays: an $O(\cdot)$ constant of $B$ pays for anything it dominates, one of $A$ needs a strict edge from a positive leftover; an $o(\cdot)$ or a family's $\delta$ of $A$ needs any positive leftover at a monomial at least as large.
2. **Z3** (MIT licence). If the linear program fails, $g$ is a polynomial in the variables with exact coefficients, and no witness (tier 3) shows it unbounded, Z3's nonlinear real arithmetic is asked whether $g < -10^9$ is possible under the constraints and the nonnegative expressions. "unsat" is a proof. Z3 runs with a resource limit, not a time limit, so the answer does not depend on the machine.
3. **Witnesses.** Otherwise the comparator looks for a reason that $A \preceq B$ fails: a rule (B3, $\varepsilon_k$ against a uniform bound), or a **slice** of $D$, every variable a polynomial in one variable $t$ ($t$, $t/2$, $t - 3$, $3$, $2$, $\sqrt t$, $t(t-1)/2$, ...) with every constraint holding for all large $t$ (checked exactly), along which some term of $A$ outgrows every term of $B$ by more than any polynomial (in O\* form). Polynomial monomials are expanded exactly along the slice, others by their leading terms, so a cancellation is trusted only when it is exact.
4. **Undecided** when there is neither a certificate nor a witness: both bounds are kept, and the pair is reported.

The ingredients:

1. **Terms.** $A \preceq B$ if every term of $A$ is dominated by some single term of $B$ (sound; a term dominated only by a sum of terms is reported incomparable).
2. **Monomials, one variable.** Order by $\alpha$, then $\beta$, then $\gamma$, then coefficient: e.g. $2^{\sqrt{k}} \prec 1.1^k \prec 1.5^k \prec k^k$. Coefficients compare as real numbers with infinitesimal shifts. An unknown constant from `O(·)` compares only against a strictly smaller or larger shape, never against the same shape.
3. **Several variables.** Two monomials in different variables compare only through the problem's **parameter constraints** (B5), e.g. $k \le n$ gives $1.5^k \preceq 1.5^n$. Without a constraint they are incomparable. Constraints live in the problem file (`schema.md` §2), each with a short justification.
4. **O* ties.** Bounds equal in O* form are compared on their exact forms by the same rules (the plan's "base, then polynomial degree, then log factors"). If the exact forms are incomparable, both are kept (B6).
5. **Unspecified functions (B3).** An $f(k)$ term is beaten by every explicit bound in the same parameter and beats nothing.
6. **Nonnegative expressions** (18 November 2026). For every constraint small $\le$ large, large $-$ small is known to be nonnegative, and so is every parameter-map expression of a reduction from the problem (it bounds a parameter of the produced instance). A difference of exponents is bounded below if it is after subtracting a nonnegative multiple of such an expression: $1.1996^{X}$ beats $2^{X}$ for $X = n(n-1)/2 - m$, because $m \le n(n-1)/2$. Graph problems therefore state the exact edge bound $m \le n(n-1)/2$, which still gives $m \le n^2$ for polynomial boundedness.
7. **Named constants take their current best value** (18 November 2026; confirmed 21 November 2026: a value, not a range). In comparisons, $\omega$ is its best upper bound: the best **published** one (`status: established` in `data/constants/omega.yaml`, now $2.371339$) for the default Overview, the browser filters and the bound history, and the best **claimed** one (now $9/4$) for the Overview with preprints and unverified results included. Keeping a result serves both Overviews, so a result is dropped only if it is beaten at **both** of these values: the comparison is made at each of the two values in turn (since 21 November 2026; before, each term took the safer of the two, which proved less).
8. **Constant bases** (18 November 2026). A base without variables is evaluated: $(2 + (1+\sqrt5)/2)^k$ is compared as $3.618\ldots^k$. If it contains named constants, its value is bounded by interval arithmetic over the values in use (item 7): $(1 + 3 \cdot 2^{\omega - 1})^{tw}$ has base at least 7, so $3^{tw}$ beats it.
9. **Raising variables** (20 November 2026). If $A$ is nondecreasing in every variable (as in A2, with $x!$ and $B_x$ counted like $x^x$) and uses variables that $B$ does not, each such $x$ may be replaced by $y^p$ for a variable $y$ of $B$ with $x \le y^p$ (the constraints, closed transitively): $A \preceq B$ if the raised $A$ is. So $k!\,2^{o(k)} \preceq n!\,2^{o(n)}$ and $n^k \preceq n^n$ for $k \le n$, which the monomial check alone cannot show. Identical statements are equal even where a factor's upper and lower estimates differ (Bell numbers), except that $f(k)$ still beats nothing (B3). Two further monomial rules (same day): a multiple of $\omega$ cancels against the same multiple on a monomial at least as large ($\omega x \le \omega y$ for $x \le y$, whatever $\omega$ is), and a monomial is at most another pointwise when, variable by variable, its logarithmic factors are the same and its powers no larger ($n_G \log n_H \le n_G n_H \log n_H$).

The best bounds of a problem (under any chosen filter) are the bounds no other bound strictly beats. They are always an antichain, and all of them are shown.

**Common-sense check** (18 November 2026). The comparator stays sound but incomplete, so `derive` also evaluates the O* forms of the Overview bounds (and the optional ones) at about 200 points that satisfy the problem's constraints, including extreme points ($k$ close to $n$, $m$ close to $n(n-1)/2$, variables at 1), with named constants at both ends of their ranges. A pair the comparator calls incomparable although one bound is at most the other at every point is reported as **undecided** (printed by `derive`, listed under `undecided` in `build/derived.json`). Numeric evidence never decides a comparison by itself: each undecided pair needs a missing fact (a constraint, with its justification) or a comparator rule. Claude proposes these when the check fires, and they are reviewed like any other change; a test keeps the list empty for the data in the repository, so whatever common sense decides, the engine decides too.

**External cross-check (21 November 2026).** The comparator stays in-house. When running times are added or changed, `tools/sage_crosscheck.py` checks the comparator's verdicts against SageMath's asymptotic expansions (Hackl, Heuberger, Krenn), run by hand, not in CI. Sage has no constraints between variables, so the check works on one-variable slices that satisfy the problem's constraints (every variable a simple function of $t$, such as $t$, $t - 3$, $3$, $\sqrt{t}$, $t^2/4$), comparing O\* forms up to a factor $t^{50}$. A claimed "at most" that fails on a slice is an error to fix (a comparator bug or a missing constraint). Pairs Sage cannot express are skipped: $o(\cdot)$ and $O(\cdot)$ in exponents, $\varepsilon$- and $\delta$-families, $f(k)$, factorials, Bell numbers, $n^k$ with both varying, and exponents growing faster or slower than linearly in $t$. Named constants are checked at both ends of their range and irrational bases at two roundings; a verdict that changes is skipped.

## Decisions (7 November 2026)

- **B1** `as_stated` is a TeX subset, notation included, rendered directly.
- **B2** The coverage of §3 is accepted, and the normal form is internal only. Bounds are always displayed in their natural form ($k^k$, not $2^{k\log k}$). Derived bases are folded only when exact; a fold that needs rounding is shown on hover, rounded up (amended 7 November 2026).
- **B3** Unspecified $f(k)$ is beaten by every explicit bound in the same parameter and beats nothing.
- **B4** Every variable is polynomially bounded in N by default, silently. Exceptions are marked `poly_bounded: false`.
- **B5** Problems declare parameter constraints, each with a justification.
- **B6** Bounds equal in O* with incomparable exact forms are both kept. The Details view shows both, and the Overview shows the earlier one.
- **Precision** (7 November 2026). A more precise bound beats a less precise one: comparison is implication between statements (§5).
- **$\omega$** (7 November 2026). $\omega \le 9/4$ is recorded as claimed and used in comparisons.

## Implementation notes (step 5)

Code: `src/pear/bounds/` (`expr.py` parser and renderer, `growth.py` normal form, `compare.py` comparator, `display.py` O* form and folding). Tests: `tests/test_bounds.py`, one group per section above. These choices follow from the agreed rules; none changes them.

- **Supported class.** Inside exponents: sums, products, constant powers, roots, logarithms of single monomials, `O(·)`, `o(·)`, $\varepsilon$, $\delta$. As factors: numbers, variables, powers, logarithms, `\mathrm{poly}(x)`, `O(·)`, sums of positive terms (estimated safely: $a + b \le 2ab$ for an upper bound, $a$ for a lower bound) and $c - \varepsilon$ as a base. Anything else, such as the logarithm of a sum, is outside the class: such a bound is **kept and undecided** against others (no proof; witnesses only from rules such as B3), never rejected and never compared wrongly.
- **Factorials and Bell numbers** (20 November 2026). By Robbins' form of Stirling's formula, $\sqrt{2\pi}\, x^{x+1/2} e^{-x} \le x! \le e\, x^{x+1/2} e^{-x}$ for $x \ge 1$, so $x!$ is compared as $\sqrt{x}\,(x/e)^x$ (the constant factor is irrelevant). For Bell numbers the comparator uses two elementary bounds: $B_x \le x^x$ (map each element to the least element of its block) and $B_x \ge (x/8)^{x/4}$ for $x \ge 8$ (partitions into pairs). Both are safe; tighter ones (e.g. Berend and Tassa's upper bound) can be added once checked. A bound with $x!$ or $B_x$ is monotone when the same bound with $x^x$ in their place is. π is a number (double precision).
- **Named constants.** A coefficient involving $\omega$ stays symbolic in the normal form. A comparison uses $\omega$'s current best value (published or claimed, item 7); for keeping a result, it is made at both values (21 November 2026). A constant base with $\omega$ inside, such as $1 + 3 \cdot 2^{\omega - 1}$, takes the end of its interval that is safe for its side when the two values differ. Without a `data/constants/` entry, such a comparison is undecided.
- **Lower bounds of variables.** Every variable is at least 2; a constraint `k \ge 3` raises this (`Context.lower`). The linear programs in log coordinates start at $\log_2$ of the lower bound, a factor $(\log k)^b$ of a monomial counts as at least $(\log_2 3)^b$, and witness slices respect the constraint.
- **Comparison code** (21 November 2026): `decide.py` (certificates: linear program, Z3), `lp.py` (exact simplex over `Fraction`, Bland's rule), `disprove.py` (slices and witnesses), `compare.py` (terms, raising, verdicts; `refuted` returns the witness). Each certificate can be inspected with `decide.bounded_below(g, ctx).certificates`. Tests: `tests/test_decide.py`.
- **Constraints** use a single variable on the smaller side; the larger side may be $y$, $y^p$, $y - c$ or $y / c$. They are closed transitively ($a \le b$, $b \le c^2$ give $a \le c^2$).
- **Mixed monomials.** $c\,k\log n$ is compared with a monomial in $k$ alone by lower-bounding $\log n \ge \log k$ through $k \le n$. This is how $2^k$ beats $n^{O(k)}$.
- **Hidden factors.** Two bounds that are both $O^*$ (or both $\tilde O$) compare their stated parts in exact form. If only one hides a factor, that factor is unknown, which usually gives a tie (B6).
- **Folding.** $c^{ax}$ is folded only when $c^a$ is exactly a number with at most four decimals. The hover folds every $c^{ax}$ with the base rounded up. `display()` returns both the shown form and the hover (`None` when they agree).
- **Precision.** In the normal form, unknowns of the bound that should be larger may be chosen: an $O(\cdot)$ constant absorbs anything of the same shape, an $o(\cdot)$ absorbs an $o(\cdot)$, and any positive coefficient wins against a smaller shape, provided it stays positive after cancelling monomials of its own shape (20 November 2026: with $tw \le k$, $k \log n$ cancels $tw \log n$ but then has nothing left against $2^{O(k)}$, so Alon, Yuster and Zwick's $2^{O(k)} n^{tw+1} \log n$ does not beat $O(n^k k^2 + n^2)$). Unknowns of the other bound are arbitrary. The polynomial that $O^*$ hides absorbs every polynomial factor.
