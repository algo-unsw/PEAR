# Reading list

Papers Claude wants to read for PEAR but has not (fully) read yet, with why. Remove an entry once it has been read and entered (or ruled out). Newest first within each section.

## Could not open or not fully read

| Paper | Link | Why it matters | Status |
|---|---|---|---|
| OpenAI. *The Exponential Time Hypothesis is False.* Preprint, 26 October 2026. | [paper.pdf](https://github.com/openai/math/blob/main/preprints/The-Exponential-Time-Hypothesis-is-False-October-25-2026/paper.pdf) | Subexponential 3-SAT / #3-SAT algorithm (ETH refutation, Lean-checked). | Not read yet. |
| Claude and Anthropic. *A $2^{o(n)}$ Time Algorithm for 3-SAT.* Hexagon preprint 2610.00577v1, 26 October 2026. | [hexagon:2610.00577v1](https://hexagonmath.org/2610.00577v1) · [PDF](https://hexagonmath.org/pdf/2610.00577v1) | Deterministic $2^{o(n)}$ algorithm that also counts (#3-SAT); Theorem 1 gives $2^{O(\min\{k^2 n \log\log n/\sqrt{\log n},\ km/\sqrt{\log m}\})}$, Theorem 2 $O(2^{\delta n})$ for every $\delta > 0$. | First half read; the Theorem 1 formula was garbled in the text extraction and must be checked in the PDF. |
| *Reverse Reductions.* STOC 2027 submission. | Not found yet; candidates are tracked in [cslib-frontier issue #2527](https://github.com/cslib-community/cslib-frontier/issues/2527). | Subexponential #3-SAT algorithms (per Serge). | Need a link. |
| *Faster Exact Algorithms for 3- and 4-Coloring: Deterministic Improvements and Further Randomized Speedups.* arXiv:2611.03115v1, November 2026. | [arXiv:2611.03115](https://arxiv.org/abs/2611.03115v1) | May beat Meijer's $O^*(1.3217^n)$ for 3-Coloring. | arXiv rate-limited the page every time. |
| Faisal N. Abu-Khzam, Amer E. Mouawad, Mathieu Liedloff. *An exact algorithm for connected red-blue dominating set.* Journal of Discrete Algorithms, 2011. | [HAL hal-00607125](https://hal.archives-ouvertes.fr/hal-00607125) | Connected Dominating Set in $O(1.8619^n)$ (best known per arXiv:2205.00086). | HAL blocks Claude's fetcher; too few attestations. |
| Magnus Wahlström. *A tighter bound for counting max-weight solutions to 2SAT instances.* IWPEC 2008. | [dblp search](https://dblp.org/search?q=A+tighter+bound+for+counting+max-weight+solutions+to+2SAT+instances) | $O^*(1.2377^n)$; cited as applying to weighted Independent Set. | No open copy found. |
| S. Kohn, A. Gottlieb, M. Kohn. *A generating function approach to the traveling salesman problem.* ACM Annual Conference 1977. | [dblp search](https://dblp.org/search?q=A+generating+function+approach+to+the+traveling+salesman+problem) | Polynomial-space $O^*(2^n)$ Hamiltonian Cycle (inclusion–exclusion). | Two of three attestations found. |
| Richard M. Karp. *Dynamic programming meets the principle of inclusion and exclusion.* Operations Research Letters, 1982. | [dblp search](https://dblp.org/search?q=Dynamic+programming+meets+the+principle+of+inclusion+and+exclusion) | Same algorithm as above, rediscovered. | Not read. |
| Eric T. Bax. *Inclusion and exclusion algorithm for the Hamiltonian path problem.* Information Processing Letters, 1993. | [dblp search](https://dblp.org/search?q=Inclusion+and+exclusion+algorithm+for+the+Hamiltonian+path+problem) | Same algorithm, rediscovered. | Not read. |
| Yoichi Iwata. *A Faster Algorithm for Dominating Set Analyzed by the Potential Method.* IPEC 2011, LNCS 7112, pp. 41–54. | [doi:10.1007/978-3-642-28050-4_4](https://doi.org/10.1007/978-3-642-28050-4_4) | Entered from the abstract and two attesting papers; exact statement numbers unknown. | Closed. |
| Fedor V. Fomin, Fabrizio Grandoni, Dieter Kratsch. *Solving Connected Dominating Set Faster than $2^n$.* Algorithmica, 2008 (journal version). | [dblp search](https://dblp.org/search?q=Solving+Connected+Dominating+Set+Faster+than) | The conference version is entered from an undated copy; check the journal version's statement. | Not read. |
| Ellis Horowitz, Sartaj Sahni. *Computing Partitions with Applications to the Knapsack Problem.* J. ACM 21(2), pp. 277–292, 1974. | [doi:10.1145/321812.321823](https://doi.org/10.1145/321812.321823) | Subset Sum in $O^*(2^{n/2})$; entered as attested. | Closed (may be open now that the ACM Digital Library is open access). |
| Richard Bellman. *Dynamic Programming Treatment of the Travelling Salesman Problem.* J. ACM 9(1), pp. 61–63, 1962. | [doi:10.1145/321105.321111](https://doi.org/10.1145/321105.321111) | Hamiltonian Cycle in $O(n^2 2^n)$; entered as attested. | As above. |
| Michael Held, Richard M. Karp. *A Dynamic Programming Approach to Sequencing Problems.* J. SIAM 10(1), pp. 196–210, 1962. | [doi:10.1137/0110015](https://doi.org/10.1137/0110015) | Same bound, found independently. | Closed. |

## Still to search

- A broader sweep per pilot problem for direct results missed so far (parameters $k$, $m$, $tw$, weighted versions), starting from recent surveys and the papers' related-work sections.
