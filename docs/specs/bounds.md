# PEAR bound expression language — DRAFT for review

> **Status: draft, not agreed.** Proposed 7 November 2026 for the specs session with Serge (HANDOFF step 4), expanding the draft in `docs/PLAN.md` → Bound expression language. Open questions are **B1–B6**, collected at the end. Nothing is implemented until they are settled.
>
> Examples use arithmetic only; no bound here is a research claim.

This spec says how a running time is written in a data file, what it means, how it is shown in O* form, and when one bound beats another. How bounds move along reductions is the rulebook (`rulebook.md`).

**Design principle: the comparator is sound but incomplete.** When it cannot prove that one bound is at most another, it reports them as incomparable and both stay on the site. Errors can then only make the list of best bounds too long, never drop a correct best bound.

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
factor    := atom [ "^" "{" exponent "}" ] | "\log" ... | "\sqrt{" sum "}" | "(" sum ")"
atom      := number | variable | constant | "f(" variable ")"
exponent  := sum | asymptotic
asymptotic:= ("O" | "o") "(" sum ")"
constant  := "\varepsilon" | "\omega" | named constant from data/constants
variable  := a symbol the problem defines (objects or parameters)
```

The parser also checks what the schema could not: every variable in `as_stated`, `time`, `calls` and parameter-map right-hand sides is defined by the problem, and `bound.parameters` lists exactly the variables of `as_stated`. The `notation` field must match the outer notation of `as_stated` (or be `O` when there is none).

## 2. Meaning

A bound is an upper bound on the worst-case running time, as a function of the variables, for all inputs. Asymptotic notation is taken jointly in all variables.

- **Hidden factors.** `O` hides a constant. `O^*` hides a factor polynomial in the input size N. `\tilde{O}` hides a factor polylogarithmic in the bound itself.
- **Asymptotics inside exponents.** `2^{O(\sqrt{k})}` means $2^{c\sqrt{k}}$ for some unknown constant $c > 0$. `n^{O(k)}` means $n^{ck}$ for some $c$. `2^{o(n)}` means one algorithm with time $2^{g(n)}$ for some $g = o(n)$.
- **Families of algorithms.** "For every $\delta > 0$ there is an $O(2^{\delta n})$-time algorithm" is weaker than `2^{o(n)}` (the algorithm may depend on $\delta$), and is written `O(2^{\delta n}) \text{ for every } \delta > 0`. Both forms beat every $c^n$ with explicit $c > 1$; they are kept distinct because hypotheses such as ETH are stated in the family form.
- **Non-explicit constants** (plan rule). `(2-\varepsilon)^n` means "for some unknown $\varepsilon > 0$". It is treated as a positive infinitesimal: $(2-\varepsilon)^n$ beats $2^n$, but every explicit $c < 2$ beats $(2-\varepsilon)^n$.
- **`\omega`** and other named constants (B2) are kept symbolic in the stored and displayed bound. Comparisons use their best known upper bound, recorded with a source in `data/constants/`, so a bound stated in $\omega$ improves automatically when $\omega$'s bound does.
- **`f(k)`** is an unspecified computable function (B3).

## 3. Normal form

Each term is rewritten as $2^{G}$, where the **growth exponent** $G$ is a sum of monomials

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

## 4. O* form (shown by default)

The O* form drops every monomial of $G$ that is $O(\log N)$, i.e. every factor polynomial in the input size. This needs to know which variables are **polynomially bounded in N** (B4): $n$, $m$, a solution size $k$ and treewidth are; a number in the input, such as Subset Sum's target $t$, is not, so $t^2$ and $t$ stay different under O*.

A sum of terms keeps only terms not dominated by another term (§5). `O(1.5^{k} + kn)` becomes $O^*(1.5^k)$; `O(2^{k} + 1.5^{n})` stays a sum unless the problem's parameter constraints decide it.

## 5. Comparison

$A \preceq B$ ("$A$ is at least as good as $B$") means $A = O(B)$ on all inputs. The comparator proves it from the normal forms:

1. **Terms.** $A \preceq B$ if every term of $A$ is dominated by some single term of $B$ (sound; a term dominated only by a sum of terms is reported incomparable).
2. **Monomials, one variable.** Order by $\alpha$, then $\beta$, then $\gamma$, then coefficient: e.g. $2^{\sqrt{k}} \prec 1.1^k \prec 1.5^k \prec k^k$. Coefficients compare as real numbers with infinitesimal shifts. An unknown constant from `O(·)` compares only against a strictly smaller or larger shape, never against the same shape.
3. **Several variables.** Two monomials in different variables compare only through the problem's **parameter constraints** (B5), e.g. $k \le n$ gives $1.5^k \preceq 1.5^n$. Without a constraint they are incomparable.
4. **O* ties.** Bounds equal in O* form are compared on their exact forms by the same rules (the plan's "base, then polynomial degree, then log factors"). If the exact forms are incomparable, both are kept (B6).

The best bounds of a problem (under any chosen filter) are the bounds no other bound strictly beats. They are always an antichain, and all of them are shown.

## Open questions

- **B1. Syntax.** Store `as_stated` in a TeX subset, notation included (e.g. `O(1.5^{k} + kn)`), so the page renders the exact form directly? *Recommend yes.*
- **B2. Coverage.** Is the class in §3 enough for the pilot? It covers: exponential, polynomial, log and log-log factors; $x^x$; roots; `O`/`o` inside exponents; $\varepsilon$; named constants such as $\omega$. Anything you expect that it misses (e.g. towers $2^{2^k}$, Ackermann-type functions, iterated logarithms)? *Recommend this class, extended when data needs it.*
- **B3. Unspecified `f(k)`.** An FPT result with unspecified $f$ is useful (it shows FPT membership) but is not a running time. Proposal: it is beaten by every explicit bound in the same parameter and beats nothing. *Recommend yes.*
- **B4. Polynomially bounded variables.** Which variables O* may absorb polynomial factors of needs a per-parameter flag, `poly_bounded: true | false`. That is a small schema addition. *Recommend adding it, default true for `n`, `m`, `N`.*
- **B5. Parameter constraints.** Comparing across variables needs per-problem constraints such as `k <= n`, `m <= n^2`, `tw <= n`. Another schema addition: `constraints: [...]` in the problem file, each with a short justification. *Recommend adding it.*
- **B6. O* ties.** When two bounds are equal in O* form and their exact forms are incomparable, keep both? *Recommend yes; the Details table shows both and the Overview shows the earlier one.*
