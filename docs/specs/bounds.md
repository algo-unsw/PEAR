# PEAR bound expression language

> **Status: agreed with Serge on 7 November 2026** (HANDOFF step 4; decisions B1–B6 at the end). Expands `docs/PLAN.md` → Bound expression language. Implementation: step 5. Changing it is the owner's decision.
>
> Examples use arithmetic only; no bound here is a research claim.

This spec says how a running time is written in a data file, what it means, how it is displayed, and when one bound beats another. How bounds move along reductions is the rulebook (`rulebook.md`).

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
- **`\omega`** and other named constants are kept symbolic in the stored and displayed bound. Comparisons use their best known upper bound, recorded with a source in `data/constants/`, so a bound stated in $\omega$ improves automatically when $\omega$'s bound does.
- **`f(k)`** is an unspecified computable function (B3).

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

**Polynomially bounded variables (B4).** By default every variable is treated as polynomially bounded in N, silently, with no declaration and no note on the page. Only exceptions are marked `poly_bounded: false` in the schema: for example, a number in the input such as Subset Sum's target $t$, so that $t^2$ and $t$ stay different under O*.

**Derived bounds.** Substitution (rulebook §2) produces new expressions, which are simplified only within the natural form:

- folding constants, so $1.2^{2k}$ becomes $1.44^{k}$;
- collecting like factors.

A computed base is **rounded up**, never down, to four decimal places, so the shown bound is still an upper bound. The unrounded value is kept in the build output. A substituted expression with no simpler natural form stays as it is: $1.5^{\,n-k}$, $(2k)^{2k}$.

## 5. Comparison

$A \preceq B$ ("$A$ is at least as good as $B$") means $A = O(B)$ on all inputs. The comparator proves it from the normal forms:

1. **Terms.** $A \preceq B$ if every term of $A$ is dominated by some single term of $B$ (sound; a term dominated only by a sum of terms is reported incomparable).
2. **Monomials, one variable.** Order by $\alpha$, then $\beta$, then $\gamma$, then coefficient: e.g. $2^{\sqrt{k}} \prec 1.1^k \prec 1.5^k \prec k^k$. Coefficients compare as real numbers with infinitesimal shifts. An unknown constant from `O(·)` compares only against a strictly smaller or larger shape, never against the same shape.
3. **Several variables.** Two monomials in different variables compare only through the problem's **parameter constraints** (B5), e.g. $k \le n$ gives $1.5^k \preceq 1.5^n$. Without a constraint they are incomparable. Constraints live in the problem file (`schema.md` §2), each with a short justification.
4. **O* ties.** Bounds equal in O* form are compared on their exact forms by the same rules (the plan's "base, then polynomial degree, then log factors"). If the exact forms are incomparable, both are kept (B6).
5. **Unspecified functions (B3).** An $f(k)$ term is beaten by every explicit bound in the same parameter and beats nothing.

The best bounds of a problem (under any chosen filter) are the bounds no other bound strictly beats. They are always an antichain, and all of them are shown.

## Decisions (7 November 2026)

- **B1** `as_stated` is a TeX subset, notation included, rendered directly.
- **B2** The coverage of §3 is accepted, and the normal form is internal only. Bounds are always displayed in their natural form ($k^k$, not $2^{k\log k}$). Derived bases are folded and rounded up.
- **B3** Unspecified $f(k)$ is beaten by every explicit bound in the same parameter and beats nothing.
- **B4** Every variable is polynomially bounded in N by default, silently. Exceptions are marked `poly_bounded: false`.
- **B5** Problems declare parameter constraints, each with a justification.
- **B6** Bounds equal in O* with incomparable exact forms are both kept. The Details view shows both, and the Overview shows the earlier one.

## Implementation notes (step 5)

Code: `src/pear/bounds/` (`expr.py` parser and renderer, `growth.py` normal form, `compare.py` comparator, `display.py` O* form and folding). Tests: `tests/test_bounds.py`, one group per section above. These choices follow from the agreed rules; none changes them.

- **Supported class.** Inside exponents: sums, products, constant powers, roots, logarithms of single monomials, `O(·)`, `o(·)`, $\varepsilon$, $\delta$. As factors: numbers, variables, powers, logarithms, `\mathrm{poly}(x)`, `O(·)`, sums of positive terms (estimated safely: $a + b \le 2ab$ for an upper bound, $a$ for a lower bound) and $c - \varepsilon$ as a base. Anything else, such as the logarithm of a sum, is outside the class: such a bound is **kept and treated as incomparable**, never rejected and never compared wrongly.
- **$\omega$.** No `data/constants/` file exists yet, so a bound using $\omega$ is incomparable until one does.
- **Constraints** use a single variable on the smaller side; the larger side may be $y$, $y^p$, $y - c$ or $y / c$. They are closed transitively ($a \le b$, $b \le c^2$ give $a \le c^2$).
- **Mixed monomials.** $c\,k\log n$ is compared with a monomial in $k$ alone by lower-bounding $\log n \ge \log k$ through $k \le n$. This is how $2^k$ beats $n^{O(k)}$.
- **Hidden factors.** Two bounds that are both $O^*$ (or both $\tilde O$) compare their stated parts in exact form. If only one hides a factor, that factor is unknown, which usually gives a tie (B6).
- **Folding.** $c^{a x}$ is folded when $a$ is an integer (any $c$), or when $c$ is not an integer. So $1.2^{2k}$ becomes $1.44^k$ and $1.5^{n/2}$ becomes $1.2248^n$, while $2^{n/2}$ keeps its natural form. Folded bases are rounded **up** to four decimals. The unrounded expression is kept as the derived bound's exact form.
