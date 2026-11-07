# Implementations: where to look

Each problem page lists publicly available implementations, best first (schema §12). This is the checklist for finding them and the facts that back the ranking. Re-check rankings when a new competition or benchmark appears; date every changing fact (`as_of`).

## Competitions (the strongest evidence for a ranking)

- **PACE Challenge** (pacechallenge.org): one or two problems a year, with exact and heuristic tracks; the website lists past challenges. Use the final ranking in the PACE report (LIPIcs, IPEC proceedings), not the "preliminary results" on the website. Solvers are usually archived on Zenodo or GitHub.
- **SAT Competition**, **MaxSAT Evaluation**, **Pseudo-Boolean Competition**, **Model Counting Competition**, **QBF Evaluation**: for SAT, MaxSAT, #SAT and problems encoded into them.
- **DIMACS Implementation Challenges** (dimacs.rutgers.edu lists the past challenges and their topics).
- **MiniZinc Challenge**, **XCSP competition**: constraint solvers.
- **ROADEF/EURO challenges**, **CVRP/VRP competitions**: routing and scheduling.

## Libraries and systems

- **SageMath** (graph methods such as `vertex_cover`, `independent_set`, `clique_number`, `chromatic_number`, `treewidth`, `dominating_set`, `hamiltonian_cycle`, …; documentation states the algorithm and whether the result is exact).
- **NetworkX** (`networkx.algorithms`; many functions are approximations: read the docstring before marking `exact`).
- **igraph** (exact clique and independent-set routines).
- **Google OR-Tools** (CP-SAT, routing, MIP).
- **Concorde** (TSP), **LKH** (TSP heuristic).
- **KaHIP / KaMIS / KaGen** (Karlsruhe: partitioning, independent sets).
- **Boost Graph Library**, **LEMON**, **OGDF**, **JGraphT**.
- MIP and CP solvers that come with a problem model: **SCIP**, **HiGHS**, **CBC**, **Gecode**, **Chuffed**.
- SAT/MaxSAT solvers (**CaDiCaL**, **Kissat**, **MiniSat**, **RC2**/PySAT) when the problem is usually solved by encoding.

## Code hosts and archives

- **GitHub** (search the problem name with "solver", "exact"), **Zenodo** (PACE submissions, artefacts), **Software Heritage** (for dead links), **Code Ocean**, **ACM artefact badges** (papers in JEA, ALENEX, SEA).
- Papers with code: the experimental papers in **ALENEX**, **SEA**, **ESA Track B**, **JEA** usually link their code.

## Evidence for facts

- **Citations**: OpenAlex (api.openalex.org/works/doi:…), with `as_of`.
- **Competition placings**: the official report (final ranking), not a leaderboard snapshot.
- **Wide use**: a source naming the field and the use (a survey, a package's dependents page, a field's standard pipeline).
- **Licence and language**: the repository's licence file, not a third-party listing.

## Exclusions

- Links that no longer resolve are left out, with a line here. As of 8 November 2026: the third-place PACE 2019 Vertex Cover solver (bogdan, Szabó and Zaválnij) linked from pacechallenge.org/2019 (`github.com/zbogdan/pace-2019`) does not resolve.
- Heuristics that are not marked as such: `exact` is left unset until the documentation says.
