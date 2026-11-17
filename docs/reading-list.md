# Reading list

Papers Claude wants to read for PEAR but has not (fully) read yet, with why. Remove an entry once it has been read and entered (or ruled out). Newest first within each section.

## Could not open or not fully read

| Paper | Link | Why it matters | Status |
|---|---|---|---|
| Chris Calabro, Russell Impagliazzo, Ramamohan Paturi. *A Duality between Clause Width and Clause Density for SAT.* CCC 2006. | [author PDF](https://cseweb.ucsd.edu/~paturi/myPapers/pubs/CalabroImpagliazzoPaturi_2006_ccc.pdf) | CNF-SAT with $m = cn$ clauses in $2^{n(1 - 1/O(\log c))}$ (randomized; Schuler 2005 and this paper): a bound in $n$ and $m$ for SAT. | The fetcher strips the formulas, and the shell may not download from ucsd.edu. |
| Friedrich Eisenbrand, Fabrizio Grandoni. *On the complexity of fixed parameter clique and dominating set.* TCS 326, 2004. | [SUPSI repository](https://repository.supsi.ch/4535/) | $k$-Clique with rectangular matrix multiplication (by $k$, and in $m$); $k$-Dominating Set in $n^{k+o(1)}$. | The repository's robots.txt blocks the fetcher. Dominating Set entered from Pătraşcu–Williams instead. |
| Hadas Shachnai, Meirav Zehavi. *A Multivariate Framework for Weighted FPT Algorithms.* arXiv:1407.2033v2. | [arXiv:1407.2033](https://arxiv.org/abs/1407.2033) | Weighted Vertex Cover in $O^*(1.381^s)$, $s$ the minimum size of a solution of weight at most $W$ (Corollary 2). | Read; needs a parameter "size of a minimum-weight solution" for weighted Vertex Cover, which we don't have. |
| Cygan et al. *Parameterized Algorithms* (book PDF). | [PDF](https://www.mimuw.edu.pl/~malcin/book/parameterized-algorithms.pdf) | Standard bounds with theorem numbers: $q$-Coloring by treewidth, Dominating Set $3^{tw}$, Hamiltonian Cycle $2^n$ in polynomial space, Chromatic Number $2^n$, Steiner Tree $2^k$. | Too large to read through the fetcher in one go; the shell may not download from mimuw.edu.pl. To read chapter by chapter. |
| Jesper Nederlof, Karol Węgrzycki (STOC 2021); Tatiana Belova, Nikolai Chukhin, Alexander S. Kulikov, Ivan Mihajlin (arXiv:2402.13170v3). | [arXiv:2402.13170](https://arxiv.org/abs/2402.13170) | Subset Sum in $O^*(2^{n/2})$ time with $O^*(2^{0.249999n})$, then $O^*(2^{0.246n})$ space. | Our space classes (polynomial or exponential) can't show this improvement: a decision for you. |
| Ce Jin, Hongxun Wu. *A Simple Near-Linear Pseudopolynomial Time Randomized Algorithm for Subset Sum.* SOSA 2019, arXiv:1807.11597v3. | [arXiv:1807.11597](https://arxiv.org/abs/1807.11597) | Same $\tilde O(n + t)$ as Bringmann (Theorem 6), simpler. | Not entered: same bound, later. |
| *Faster Exact Algorithms for 3- and 4-Coloring: Deterministic Improvements and Further Randomized Speedups.* arXiv:2611.03115v1, November 2026. | [arXiv:2611.03115](https://arxiv.org/abs/2611.03115v1) | May beat Meijer's $O^*(1.3217^n)$ for 3-Coloring. | arXiv rate-limited the page every time. |
| Faisal N. Abu-Khzam, Amer E. Mouawad, Mathieu Liedloff. *An exact algorithm for connected red-blue dominating set.* Journal of Discrete Algorithms, 2011. | [HAL hal-00607125](https://hal.archives-ouvertes.fr/hal-00607125) | Connected Dominating Set in $O(1.8619^n)$ (best known per arXiv:2205.00086). | HAL blocks Claude's fetcher; too few attestations. |
| Magnus Wahlström. *A tighter bound for counting max-weight solutions to 2SAT instances.* IWPEC 2008. | [dblp search](https://dblp.org/search?q=A+tighter+bound+for+counting+max-weight+solutions+to+2SAT+instances) | $O^*(1.2377^n)$; cited as applying to weighted Independent Set. | No open copy found. |
| S. Kohn, A. Gottlieb, M. Kohn. *A generating function approach to the traveling salesman problem.* ACM Annual Conference 1977. | [dblp search](https://dblp.org/search?q=A+generating+function+approach+to+the+traveling+salesman+problem) | Polynomial-space $O^*(2^n)$ Hamiltonian Cycle (inclusion–exclusion). | Two of three attestations found (Björklund FOCS 2010; Björklund–Husfeldt–Kaski–Koivisto TALG). Karp 1982 entered as attested instead. |
| Eric T. Bax. *Inclusion and exclusion algorithm for the Hamiltonian path problem.* Information Processing Letters, 1993. | [dblp search](https://dblp.org/search?q=Inclusion+and+exclusion+algorithm+for+the+Hamiltonian+path+problem) | Same algorithm, rediscovered. | Not read. |
| Yoichi Iwata. *A Faster Algorithm for Dominating Set Analyzed by the Potential Method.* IPEC 2011, LNCS 7112, pp. 41–54. | [doi:10.1007/978-3-642-28050-4_4](https://doi.org/10.1007/978-3-642-28050-4_4) | Entered from the abstract and two attesting papers; exact statement numbers unknown. | Closed. |
| Fedor V. Fomin, Fabrizio Grandoni, Dieter Kratsch. *Solving Connected Dominating Set Faster than $2^n$.* Algorithmica, 2008 (journal version). | [dblp search](https://dblp.org/search?q=Solving+Connected+Dominating+Set+Faster+than) | The conference version is entered from an undated copy; check the journal version's statement. | Not read. |
| Ellis Horowitz, Sartaj Sahni. *Computing Partitions with Applications to the Knapsack Problem.* J. ACM 21(2), pp. 277–292, 1974. | [doi:10.1145/321812.321823](https://doi.org/10.1145/321812.321823) | Subset Sum in $O^*(2^{n/2})$; entered as attested. | No open copy found. |
| Richard Bellman. *Dynamic Programming Treatment of the Travelling Salesman Problem.* J. ACM 9(1), pp. 61–63, 1962. | [doi:10.1145/321105.321111](https://doi.org/10.1145/321105.321111) | Hamiltonian Cycle in $O(n^2 2^n)$; entered as attested. | No open copy found. |
| Michael Held, Richard M. Karp. *A Dynamic Programming Approach to Sequencing Problems.* J. SIAM 10(1), pp. 196–210, 1962. | [doi:10.1137/0110015](https://doi.org/10.1137/0110015) | Same bound, found independently. | Closed. |

## Read, worth a decision (new parameters or problems)

| Paper | Link | Why it matters |
|---|---|---|
| Sanjay Jain, Tzeh Yuan Neoh, Frank Stephan. *An Improved Algorithm for Sparse Instances of SAT.* arXiv:2411.07389. | [arXiv:2411.07389](https://arxiv.org/pdf/2411.07389) | SAT in $O^*(1.1199^{(d-2)n})$, $d$ = maximum or average number of occurrences of a variable: needs a parameter $d$ for SAT. |
| Shiva Kintali. *A simplified proof of ETH is false.* 26 October 2026. | [PDF](https://shivakintali.github.io/papers/ETH.pdf) | 3-SAT (decision) in $2^{\varepsilon n}$ for every $\varepsilon > 0$: 3-SAT is not a pilot problem. |
| Ruhollah Majdoddin. *Lowered crossover points of Anthropic's subexponential 3-SAT algorithm.* arXiv:2610.41622. | [arXiv:2610.41622](https://arxiv.org/abs/2610.41622) | Practical crossover points; no new asymptotic bound for #3-SAT. |

## Still to search

- A broader sweep per pilot problem for direct results missed so far (parameters $k$, $m$, $tw$, weighted versions), starting from recent surveys and the papers' related-work sections.
