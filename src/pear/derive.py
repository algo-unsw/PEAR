"""Derivation engine: the reduction rulebook (docs/specs/rulebook.md, version 2).

Starting from the algorithms in the data, bounds are transferred backwards along
reductions (an algorithm for B plus a reduction from A to B gives a bound for A),
along "special case" links between versions, and projected onto single parameters,
until nothing changes. A derived bound is kept unless another result is at least as
good both as a bound and in every filter the site offers (DESIGN.md: deterministic,
polynomial space, constructive, non-algebraic, Lean-verified, direct, classical).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Iterable

from .bounds import Bound, Relation, compare, display, ostar, parse_bound, parse_expr
from .bounds.compare import Analysed, Context, analyse, compare_ostar
from .bounds.display import simplify, substitute
from .bounds.expr import Add, Const, Log, Mul, Node, Num, Pow, Var, variables
from .bounds.growth import is_monotone
from .bounds.numeric import dominates, samples, value
from .schema import Algorithm, FolkloreSource, Hypothesis, PaperSource, Problem, Reduction, Variant
from .validate import Dataset, problem_context

RULEBOOK_VERSION = 3
LONG_CHAIN = 3  # rulebook §9: longer chains get a label (they are followed while they improve results)
FORMAL_ORDER = {"informal": 0, "statement": 1, "proved": 2}


# --- results ----------------------------------------------------------------------


# Kinds of paper version that are peer reviewed (or examined). A paper with none of them is a
# preprint: like a result from an unverified paper, a result from a preprint is left out of the
# Overview unless the reader includes it (decided 18 November 2026).
REVIEWED_KINDS = frozenset({"journal", "conference", "workshop", "book", "thesis"})


def is_preprint(paper) -> bool:
    """No peer-reviewed version (only preprints or technical reports)."""
    return not any(v.kind in REVIEWED_KINDS for v in paper.versions.values())


def at_least_as_strong(a: "Props", b: "Props") -> bool:
    """Deterministic and polynomial space wherever b is (decided 18 November 2026)."""
    return (a.deterministic or not b.deterministic) and (a.poly_space or not b.poly_space)


def stronger(a: "Props", b: "Props") -> bool:
    return at_least_as_strong(a, b) and (a.deterministic, a.poly_space) != (b.deterministic, b.poly_space)


@dataclass(frozen=True)
class Props:
    """The properties the site filters on (rulebook §8), plus hypotheses."""

    deterministic: bool
    poly_space: bool
    constructive: bool
    algebraic: bool
    fast_matrix_multiplication: bool
    quantum: bool
    formal: str  # weakest along the chain: informal | statement | proved
    lean: bool  # every step proved in Lean
    conditional_on: frozenset[str] = frozenset()
    verified: bool = True  # False if any paper along the chain is marked unverified
    reviewed: bool = True  # False if any paper along the chain is a preprint

    def at_least(self, other: Props) -> bool:
        """Does self satisfy every filter that `other` satisfies?"""
        return (
            (self.deterministic or not other.deterministic)
            and (self.poly_space or not other.poly_space)
            and (self.constructive or not other.constructive)
            and (not self.algebraic or other.algebraic)
            and (not self.quantum or other.quantum)
            and (self.lean or not other.lean)
            and FORMAL_ORDER[self.formal] >= FORMAL_ORDER[other.formal]
            and self.conditional_on <= other.conditional_on
            and (self.verified or not other.verified)
            and (self.reviewed or not other.reviewed)
        )


@dataclass(frozen=True)
class Step:
    kind: str  # reduction | special-case | projection | technique
    id: str
    from_node: str
    to_node: str
    type: str | None = None  # reduction type
    parameter_map: tuple[tuple[str, str], ...] = ()
    counted: bool = True  # counts towards the chain length (projections do not)
    note: str | None = None  # for a reduction variant: what is modified


@dataclass(frozen=True)
class Result:
    problem: str
    node: str  # the version class, e.g. "decision+optimisation+search"
    bound: Bound  # exact form, in the problem's variables
    props: Props
    origin: str  # the algorithm the chain starts from
    chain: tuple[Step, ...] = ()  # from the algorithm's node to this node
    flags: frozenset[str] = frozenset()  # adaptive-sizes, claimed-refuted-hypothesis, ...
    year: int | None = None  # when the bound became known: the latest dated ingredient
    papers: tuple[str, ...] = ()  # papers along the chain: the algorithm's, then each reduction's

    @property
    def derived(self) -> bool:
        return bool(self.chain)

    @property
    def steps(self) -> int:
        return sum(1 for s in self.chain if s.counted)

    @property
    def id(self) -> str:
        return "|".join([self.origin] + [s.id for s in self.chain])

    def nodes(self) -> set[str]:
        out = {f"{self.problem}:{self.node}"}
        for s in self.chain:
            out |= {s.from_node, s.to_node}
        return out


@dataclass
class Derivation:
    results: dict[tuple[str, str], list[Result]] = field(default_factory=dict)  # (problem, node) -> kept
    log: list[str] = field(default_factory=list)
    # comparisons with named constants (decided 18 November 2026): keeping a result uses ω
    # anywhere between its best claimed and best published value; the default Overview and
    # the browser filters use the published value; the Overview with preprints and
    # unverified results included uses the claimed value
    contexts: dict[str, Context] = field(default_factory=dict)
    published: dict[str, Context] = field(default_factory=dict)
    claimed: dict[str, Context] = field(default_factory=dict)
    beaten_by: dict[str, list[str]] = field(default_factory=dict)  # result id -> ids of strictly better bounds
    overview: dict[tuple[str, str], list[dict]] = field(default_factory=dict)  # (problem, node) -> groups
    # the Overview with preprints and unverified results included (claimed constants)
    overview_all: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    # unverified results a reader may add to the Overview (decided 12 November 2026), with the
    # Overview members each one beats in O* form
    optional: dict[tuple[str, str], list[dict]] = field(default_factory=dict)
    # direct results beaten in every filter (version 3): not in Details, kept for the bound history
    superseded: dict[tuple[str, str], list[tuple[Result, list[str]]]] = field(default_factory=dict)
    # common-sense check (18 November 2026): Overview bounds the comparator calls incomparable
    # although one is at most the other at every sample point; each needs a fact or a rule
    undecided: list[dict] = field(default_factory=list)


# --- nodes: versions that share bounds ------------------------------------------------


def version_class(problem: Problem, version: str) -> str:
    for group in problem.shared_bounds:
        if version in group.versions:
            return "+".join(sorted(group.versions))
    return version


def node_key(problem: Problem, version: str) -> tuple[str, str]:
    return problem.id, version_class(problem, version)


# --- the engine -------------------------------------------------------------------------


class Engine:
    def __init__(self, data: Dataset):
        self.data = data
        self.out = Derivation()
        self.analysed: dict[str, Analysed] = {}
        self.hypotheses: dict[str, Hypothesis] = data.entries["hypotheses"]  # type: ignore[assignment]
        for pid, problem in data.problems.items():
            self.out.contexts[pid] = problem_context(data, problem, "between")
            self.out.published[pid] = problem_context(data, problem, "published")
            self.out.claimed[pid] = problem_context(data, problem, "claimed")
        self._logged: set[str] = set()
        self.variant_of: dict[str, Variant] = {}  # effective reduction id -> its variant

    def log(self, message: str) -> None:
        if message not in self._logged:
            self._logged.add(message)
            self.out.log.append(message)

    # -- inputs ---------------------------------------------------------------------

    def usable(self, status: str) -> bool:
        return status in ("valid", "fixed")  # rulebook A3

    def hypothesis_flags(self, hyps: Iterable[str]) -> tuple[bool, frozenset[str]]:
        """(excluded, flags) for a set of hypotheses (rulebook A3)."""
        flags = set()
        for h in hyps:
            hyp = self.hypotheses.get(h)
            if hyp is None:
                continue
            if hyp.status == "refuted":
                return True, frozenset()
            if hyp.status == "claimed-refuted":
                flags.add("claimed-refuted-hypothesis")
        return False, frozenset(flags)

    def weakest(self, hyps: Iterable[str]) -> frozenset[str]:
        """Drop every hypothesis implied by another one in the set (rulebook §8)."""
        hs = set(hyps)

        def implied_by(h: str) -> set[str]:
            seen, todo = set(), [h]
            while todo:
                x = todo.pop()
                hyp = self.hypotheses.get(x)
                for y in hyp.implies if hyp else []:
                    if y not in seen:
                        seen.add(y)
                        todo.append(y)
            return seen

        return frozenset(h for h in hs if not any(h in implied_by(g) for g in hs if g != h))

    def used(self, alg: Algorithm) -> list[Algorithm]:
        """Every result alg relies on through `uses`, transitively (validated acyclic)."""
        algorithms = self.data.entries["algorithms"]
        seen: dict[str, Algorithm] = {}
        todo = list(alg.uses)
        while todo:
            u = todo.pop()
            if u not in seen and u in algorithms:
                seen[u] = algorithms[u]  # type: ignore[assignment]
                todo.extend(seen[u].uses)
        return [seen[k] for k in sorted(seen)]

    def unverified(self, alg: Algorithm) -> bool:
        papers = {alg.source.paper} if alg.source.paper else set()
        checked = alg.formal.status == "proved" and alg.formal.statement_checked is not None
        return not checked and (alg.unverified or any(
            self.data.papers[p].unverified for p in papers if p in self.data.papers))

    def preprint(self, alg: Algorithm) -> bool:
        papers = {alg.source.paper} if alg.source.paper else set()
        checked = alg.formal.status == "proved" and alg.formal.statement_checked is not None
        return not checked and any(is_preprint(self.data.papers[p]) for p in papers if p in self.data.papers)

    def direct(self, alg: Algorithm) -> Result | None:
        problem = self.data.problems[alg.problem]
        if not self.usable(alg.status):
            self.log(f"{alg.id}: status '{alg.status}', not used (rulebook A3)")
            return None
        used = self.used(alg)
        bad = [u.id for u in used if not self.usable(u.status)]
        if bad:
            self.log(f"{alg.id}: uses {', '.join(bad)}, whose status keeps it out; not used (rulebook A3)")
            return None
        hyps = set(alg.conditional_on).union(*(u.conditional_on for u in used))
        excluded, flags = self.hypothesis_flags(hyps)
        if excluded:
            self.log(f"{alg.id}: relies on a refuted hypothesis, not used (rulebook A3)")
            return None
        bound = parse_bound(alg.bound.as_stated, problem.symbols())
        p = alg.properties
        props = Props(
            deterministic=p.randomized is False,
            poly_space=p.space.class_ == "polynomial",
            constructive=p.constructive,
            algebraic=p.algebraic,
            fast_matrix_multiplication=p.fast_matrix_multiplication,
            quantum=p.quantum,
            formal=alg.formal.status,
            lean=alg.formal.status == "proved" and (alg.formal.prover or "").lower() == "lean",
            conditional_on=self.weakest(hyps),
        )
        _, node = node_key(problem, alg.proved_for)
        year, papers = self.dated(alg.source)
        flags = set(flags) | {f"given-{g}" for g in alg.given}
        checked = alg.formal.status == "proved" and alg.formal.statement_checked is not None
        if ((alg.unverified or any(self.data.papers[p].unverified for p in papers)) and not checked) or any(
                self.unverified(u) for u in used):
            props = replace(props, verified=False)
            flags.add("unverified")
        if (any(is_preprint(self.data.papers[p]) for p in papers) and not checked) or any(
                self.preprint(u) for u in used):
            props = replace(props, reviewed=False)
            flags.add("preprint")
        return Result(problem.id, node, bound, props, alg.id, (), frozenset(flags), year, papers)

    # -- keeping -----------------------------------------------------------------------

    def analyse(self, r: Result) -> Analysed:
        key = r.id
        if key not in self.analysed:
            self.analysed[key] = analyse(r.bound)
        return self.analysed[key]

    def parameters(self, r: Result) -> frozenset[str]:
        """The parameters a bound is listed under: the variables of its O* form."""
        return frozenset(variables(ostar(r.bound, self.out.contexts[r.problem]).expr))

    def dated(self, src: PaperSource | FolkloreSource) -> tuple[int | None, tuple[str, ...]]:
        """When a source's result became known, and its paper. The year is that of the earliest
        paper version the statements cite (a result may appear only in a later version);
        for a closed paper cited without statements, its earliest version."""
        if isinstance(src, PaperSource):
            paper = self.data.papers[src.paper]
            cited = [paper.versions[v] for v in src.statements if v in paper.versions]
            return min(v.year for v in cited or paper.versions.values()), (src.paper,)
        return None, ()

    def dominates(self, s: Result, r: Result, ctx: Context) -> bool:
        """s makes r redundant: at least as good a bound, at least as good in every filter,
        and listed under the same parameters or fewer (a bound "by n" competes "by n", §7)."""
        if r.derived is False and s.derived:
            return False  # the "include derived" filter: derived results never hide direct ones
        if not s.props.at_least(r.props):
            return False
        if not self.parameters(s) <= self.parameters(r):
            return False
        in_ostar = compare_ostar(self.analyse(s), self.analyse(r), ctx)
        if in_ostar == Relation.BETTER:
            return True
        if in_ostar != Relation.EQUAL:
            return False
        # Equal in O*: the Overview cites the earliest, so only an earlier
        # result (or the same algorithm by a shorter route) may replace r.
        if compare(self.analyse(s), self.analyse(r), ctx) not in (Relation.BETTER, Relation.EQUAL):
            return False
        return _earlier(s, r) or (s.year == r.year and s.origin == r.origin)

    def insert(self, r: Result) -> bool:
        key = (r.problem, r.node)
        kept = self.out.results.setdefault(key, [])
        ctx = self.out.contexts[r.problem]
        if any(s.id == r.id for s in kept):
            return False
        dominators = [s for s in kept if self.dominates(s, r, ctx)]
        if dominators:
            self.supersede(key, r, dominators)
            return False
        removed = [s for s in kept if self.dominates(r, s, ctx)]
        for s in removed:
            self.supersede(key, s, [r])
        kept[:] = [s for s in kept if s not in removed]
        kept.append(r)
        return True

    def supersede(self, key: tuple[str, str], r: Result, by: list[Result]) -> None:
        """Rulebook §9 (version 3): a beaten direct result leaves the Details list but stays
        in the bound history. Beaten derived results are simply dropped."""
        if r.derived:
            return
        entries = self.out.superseded.setdefault(key, [])
        for i, (old, ids) in enumerate(entries):
            if old.id == r.id:
                entries[i] = (old, sorted(set(ids) | {s.id for s in by}))
                return
        entries.append((r, sorted(s.id for s in by)))

    # -- transfers -------------------------------------------------------------------------

    def extend_chain(self, r: Result, step: Step) -> tuple[Step, ...] | None:
        return r.chain + (step,)

    def via_reduction(self, r: Result, red: Reduction) -> Result | None:
        source = self.data.problems[red.from_.problem]
        target = self.data.problems[red.to.problem]
        a_node = node_key(source, red.from_.version)
        from_tag = f"{a_node[0]}:{a_node[1]}"
        if from_tag in r.nodes():
            return None  # never revisit a node: cycles cannot improve a chain
        variant = self.variant_of.get(red.id)
        step = Step(
            "reduction",
            red.id,
            from_tag,
            f"{r.problem}:{r.node}",
            red.type,
            tuple(sorted(red.parameter_map.items())),
            note=variant.note if variant else None,
        )
        chain = self.extend_chain(r, step)
        if chain is None:
            return None
        if red.type == "serf":
            bound = self.serf_bound(r, red, source, target)
        else:
            bound = self.polytime_bound(r, red, source, target)
        if bound is None:
            return None
        p = r.props
        red_space = red.properties.space if red.properties else None
        red_constructive = red.properties.constructive if red.properties else None
        poly_space = p.poly_space and (
            red.type != "serf" or (red_space is not None and red_space.class_ == "polynomial")
        )
        if red_space is not None and red_space.class_ != "polynomial":
            poly_space = False
        props = replace(
            p,
            deterministic=p.deterministic and red.type != "polytime-randomized",
            poly_space=poly_space,
            constructive=p.constructive and red_constructive is not False,
            formal=min(p.formal, red.formal.status, key=FORMAL_ORDER.__getitem__),
            lean=p.lean and red.formal.status == "proved" and (red.formal.prover or "").lower() == "lean",
        )
        flags = set(r.flags)
        if red.type != "serf" and red.calls != 1 and red.call_sizes is None:
            flags.add("adaptive-sizes")  # rulebook §3: every call assumed to have the largest size
        red_year, red_papers = self.dated(red.source)
        years = [y for y in (r.year, red_year) if y is not None]
        if variant is not None:
            if variant.source is None:
                flags.add("site-written-variant")
            else:
                v_year, v_papers = self.dated(variant.source)
                years += [v_year] if v_year is not None else []
                red_papers += tuple(p for p in v_papers if p not in red_papers)
        if any(self.data.papers[p].unverified for p in red_papers):
            props = replace(props, verified=False)
            flags.add("unverified")
        if any(is_preprint(self.data.papers[p]) for p in red_papers):
            props = replace(props, reviewed=False)
            flags.add("preprint")
        return Result(
            source.id, a_node[1], bound, props, r.origin, chain, frozenset(flags),
            max(years) if years else None, r.papers + red_papers,
        )

    def polytime_bound(self, r: Result, red: Reduction, source: Problem, target: Problem) -> Bound | None:
        """Rulebook §2 and §3: T_A = T_R + calls · f_B(φ(x_A))."""
        b = r.bound
        mapping = set(red.parameter_map)
        if not variables(b.expr) <= mapping:
            # Rulebook §2 (version 2, D2): polynomial factors of B are polynomial in N_A,
            # so the O* form may transfer when only those are missing from the map.
            b = ostar(b, self.out.contexts[target.id])
            if not variables(b.expr) <= mapping:
                missing = sorted(variables(b.expr) - mapping)
                self.log(f"{red.id}: cannot transfer {r.id}, parameter map does not cover {missing} (rulebook §2)")
                return None
        if not is_monotone(b):
            self.log(f"{red.id}: cannot transfer {r.id}, bound not shown to be monotone (rulebook A2)")
            return None
        phi = {v: parse_expr(e, source.symbols()) for v, e in red.parameter_map.items()}
        f = simplify(substitute(b.expr, phi))
        calls: Node | None = None
        if red.calls != 1:
            if isinstance(red.calls, int):
                calls = Num(Fraction(red.calls), str(red.calls))
            else:
                calls = parse_expr(red.calls, source.symbols())
            if not r.props.deterministic and not isinstance(calls, Num):
                calls = Mul((calls, Log(calls)))  # rulebook §4: amplify each randomized call
        t_r = parse_bound(red.time, source.symbols())
        terms: list[Node] = [t for _, t in t_r.expr.terms] if isinstance(t_r.expr, Add) else [t_r.expr]
        f_terms = [t for _, t in f.terms] if isinstance(f, Add) else [f]
        for t in f_terms:
            terms.append(simplify(Mul((calls, t))) if calls is not None else t)
        notation = b.notation if b.notation in ("O*", "Õ") else "O"
        return Bound(notation, Add(tuple((1, t) for t in terms)), b.family)

    def serf_bound(self, r: Result, red: Reduction, source: Problem, target: Problem) -> Bound | None:
        """Rulebook §5: only subexponential statements transfer (Lemma 9 of IPZ 2001)."""
        if len(red.parameter_map) != 1:
            self.log(f"{red.id}: a SERF maps exactly one measure (rulebook §5)")
            return None
        ((q, p_text),) = red.parameter_map.items()
        p_expr = parse_expr(p_text, source.symbols())
        p_vars = variables(p_expr)
        if len(p_vars) != 1:
            self.log(f"{red.id}: SERF measure must be a single variable of {source.id} (rulebook §5)")
            return None
        family_b = _family(q)
        if compare(self.analyse(r), analyse(family_b), self.out.contexts[target.id]) not in (
            Relation.BETTER,
            Relation.EQUAL,
        ):
            return None  # B is not known to be subexponential in q
        (p,) = p_vars
        return _family(p)

    def special_cases(self, r: Result) -> list[Result]:
        """Rulebook §6: a bound for a general version holds for its special cases."""
        problem = self.data.problems[r.problem]
        out = []
        members = r.node.split("+")
        for vid, version in problem.versions.items():
            for special in version.generalises:
                if vid in members:
                    _, special_node = node_key(problem, special)
                    if special_node == r.node:
                        continue
                    from_tag = f"{problem.id}:{special_node}"
                    if from_tag in r.nodes():
                        continue
                    step = Step("special-case", f"special-case:{problem.id}:{vid}>{special}", from_tag, f"{problem.id}:{r.node}")
                    chain = self.extend_chain(r, step)
                    if chain is not None:
                        out.append(replace(r, node=special_node, chain=chain))
        return out

    def projections(self, r: Result) -> list[Result]:
        """Rulebook §7: project a bound, direct or derived, onto single parameters through
        the constraints: 1.5^{n-k} gives 1.5^n, and 1.2^k with k ≤ n gives 1.2^n."""
        if r.chain and r.chain[-1].kind == "projection":
            return []  # constraints are closed transitively, so one projection suffices
        ctx = self.out.contexts[r.problem]
        shown = ostar(r.bound, ctx)
        candidates: list[tuple[str, Node]] = []
        base = _drop_subtractions(shown.expr)
        if base != shown.expr:
            candidates.append(("drop-subtractions", base))
        base_vars = sorted(variables(base))
        for y in sorted(self.data.problems[r.problem].symbols()) if base_vars else []:
            if base_vars == [y]:
                continue
            mapping: dict[str, Node] = {}
            for x in base_vars:
                if x == y:
                    continue
                p = ctx.relation(x, y)
                if p is None:
                    break
                mapping[x] = Var(y) if p == 1 else Pow(Var(y), Num(p, _num_text(p)))
            else:
                candidates.append((y, simplify(substitute(base, mapping))))
        out = []
        for label, expr in candidates:
            proj = Bound("O*", expr, shown.family)
            if compare(analyse(r.bound), analyse(proj), ctx) not in (Relation.BETTER, Relation.EQUAL):
                continue  # only provably valid projections are kept
            step = Step("projection", f"projection:{label}", f"{r.problem}:{r.node}", f"{r.problem}:{r.node}", counted=False)
            out.append(replace(r, bound=proj, chain=r.chain + (step,)))
        return out

    # -- techniques (18 November 2026) ------------------------------------------------------

    def techniques(self, r: Result) -> list[Result]:
        """Apply generic techniques such as Monotone Local Search: a result in time c^k N^{O(1)}
        for a problem the technique applies to gives one in time f(c)^n, for each rule
        (theorem) whose requirements it meets. The output base is rounded up to four decimals,
        strictly when the theorem has a 2^{o(n)} factor, so the stated bound is an upper bound.

        A technique is applied only when every prerequisite it lists is met (rulebook §9a,
        approved 18 November 2026 on that condition); `technique_misses` says which are not."""
        out: list[Result] = []
        problem = self.data.problems[r.problem]
        for tid, tech in sorted(self.data.entries["techniques"].items()):
            listed = [ap for ap in tech.applies_to if ap.problem == r.problem]  # type: ignore[attr-defined]
            if not listed:
                continue  # subset-problem: the technique does not apply to this problem at all
            if not self.usable(tech.status):  # type: ignore[attr-defined]
                self.log(f"{tid}: status '{tech.status}', not used (rulebook A3)")  # type: ignore[attr-defined]
                continue
            if tech.review.approved_by is None:  # type: ignore[attr-defined]
                self.log(f"{tid}: technique awaits approval (rule 6), not used")
                continue
            if any(st.kind == "technique" for st in r.chain):
                continue  # applied at most once per chain
            ap = next((a for a in listed if node_key(problem, a.version)[1] == r.node), None)
            budgets = {a.budget for a in listed}
            if not budgets & variables(r.bound.expr):
                continue  # not a bound in the budget at all, so not a candidate (not logged)
            c, misses = self.technique_misses(r, ap)
            if misses:
                self.log(f"{tid}: not applied to {r.id}: {'; '.join(misses)}")
                continue
            assert ap is not None and c is not None
            exact = value(parse_expr(tech.base, ["c"]), {"c": c})  # type: ignore[attr-defined]
            if exact is None or exact <= 0:
                self.log(f"{tid}: not applied to {r.id}: the output base is undefined at c = {c:.6g}")
                continue
            paper = self.data.papers[tech.source.paper]  # type: ignore[attr-defined]
            years = [paper.versions[v].year for v in tech.source.statements if v in paper.versions]  # type: ignore[attr-defined]
            kind = self.input_kind(r)
            for rule in tech.rules:  # type: ignore[attr-defined]
                if kind not in rule.accepts:  # error: the theorem does not cover this input
                    self.log(f"{tid}: {rule.statement} not applied to {r.id}: it covers "
                             f"{', '.join(rule.accepts)} input algorithms, not {kind} ones")
                    continue
                base = math.ceil(exact * 10**4 - 1e-9) / 10**4
                if rule.subexponential_factor and base <= exact + 1e-12:
                    base += 1e-4
                text = f"{base:.4f}"
                bound = Bound("O*", Pow(Num(Fraction(text), text), Var(ap.universe)))
                props = replace(
                    r.props,
                    deterministic=r.props.deterministic and rule.output_deterministic,
                    poly_space=r.props.poly_space and rule.keeps_polynomial_space,
                )
                step = Step("technique", f"technique:{tid}:{rule.id}", f"{r.problem}:{r.node}", f"{r.problem}:{r.node}",
                            note=f"{c:.6g}")  # the input base c
                year = max([y for y in [r.year, *years] if y is not None], default=None)
                out.append(replace(r, bound=bound, props=props, chain=r.chain + (step,), year=year,
                                   papers=r.papers + (tech.source.paper,)))  # type: ignore[attr-defined]
        return out

    def technique_misses(self, r: Result, ap) -> tuple[float | None, list[str]]:  # noqa: ANN001
        """(c, the prerequisites r does not meet) for a technique entry `ap` of r's problem
        (None if no entry is for r's version class). The checks are those of TECHNIQUE_CHECKS;
        the error check depends on the rule and is made per rule."""
        misses: list[str] = []
        if ap is None:
            return None, [f"extension: the technique is listed for another version of {r.problem}, not '{r.node}'"]
        given = sorted(f.removeprefix("given-") for f in r.flags if f.startswith("given-"))
        if given:
            misses.append(f"extension: the algorithm needs a given {', '.join(given)}, beyond the instance")
        c = None
        if r.bound.family:
            misses.append("single-exponential: the bound holds for every delta > 0, not for one constant c")
        else:
            c = self.single_exponential(r, ap.budget)
            if c is None:
                misses.append(f"single-exponential: the O* form is not c^{ap.budget} for a constant c")
            elif c <= 1:
                misses.append(f"single-exponential: c = {c:.6g} is not greater than 1")
        if r.props.quantum:
            misses.append("classical: the algorithm is quantum")
        return c, misses

    def input_kind(self, r: Result) -> str:
        """deterministic, one-sided, two-sided, las-vegas, or unrecorded: the randomness of the
        algorithm a result describes, as far as the data records it (rulebook §9a)."""
        if r.props.deterministic:
            return "deterministic"
        randomized_steps = any(st.kind == "reduction" and st.type == "polytime-randomized" for st in r.chain)
        alg = self.data.entries["algorithms"].get(r.origin)
        own = getattr(getattr(alg, "properties", None), "randomized", True)
        if randomized_steps:
            return "unrecorded"  # a randomized reduction records no error type
        if own is True or own is False:  # randomized without an error type (False cannot occur here)
            return "unrecorded"
        return own.error

    def single_exponential(self, r: Result, var: str) -> float | None:
        """c if the result's O* form is c^{var} for a constant c (ω at its published value)."""
        ctx = self.out.published[r.problem]
        expr = ostar(r.bound, ctx).expr
        if not (isinstance(expr, Pow) and expr.exp == Var(var)):
            return None
        env = {f"\\{name}": lo for name, (lo, _) in ctx.constants.items()}
        return value(expr.base, env)

    # -- fixpoint ----------------------------------------------------------------------------

    def run(self) -> Derivation:
        frontier: list[Result] = []
        for aid in sorted(self.data.entries["algorithms"]):
            alg = self.data.entries["algorithms"][aid]
            assert isinstance(alg, Algorithm)
            r = self.direct(alg)
            if r is not None and self.insert(r):
                frontier.append(r)
                for proj in self.projections(r):
                    if self.insert(proj):
                        frontier.append(proj)
        reductions = [
            red for _, red in sorted(self.data.entries["reductions"].items()) if isinstance(red, Reduction)
        ]
        usable = []
        for red in reductions:
            if not self.usable(red.status):
                self.log(f"{red.id}: status '{red.status}', not used (rulebook A3)")
                continue
            usable.append(red)
            for v in red.variants:
                if v.source is None and v.review.approved_by is None:
                    self.log(f"{red.id}: variant '{v.id}' is written by the site and awaits approval (rule 6)")
                    continue
                usable.append(self.as_reduction(red, v))
        while frontier:
            new: list[Result] = []
            for r in frontier:
                if not self.still_kept(r):
                    continue
                produced: list[Result] = []
                for red in usable:
                    target = self.data.problems[red.to.problem]
                    if node_key(target, red.to.version) != (r.problem, r.node):
                        continue
                    d = self.via_reduction(r, red)
                    if d is not None:
                        produced.append(d)
                produced += self.special_cases(r)
                produced += self.techniques(r)
                for d in produced:
                    if self.insert(d):
                        new.append(d)
                        for proj in self.projections(d):
                            if self.insert(proj):
                                new.append(proj)
            frontier = new
        self.out.beaten_by = self.beaten_by()
        self.out.overview = self.overview()
        self.out.overview_all = self.overview(include_all=True)
        self.out.optional = self.optional_overview()
        self.out.undecided = self.undecided()
        return self.out

    def undecided(self) -> list[dict]:
        """Pairs among the Overview bounds (with the optional ones) that the comparator cannot
        order although one is at most the other at every sample point satisfying the
        problem's constraints. Numeric evidence decides nothing; it shows where the engine
        lacks a fact (a constraint) or a comparison rule (decided 18 November 2026)."""
        out: list[dict] = []
        views = [(key, entries, False) for key, entries in sorted(self.out.overview.items())]
        views += [(key, entries, True) for key, entries in sorted(self.out.overview_all.items())]
        for key, entries, include_all in views:
            pid, node = key
            problem = self.data.problems[pid]
            ctx = (self.out.claimed if include_all else self.out.published)[pid]
            kept = {r.id: r for r in self.out.results.get(key, [])}
            ids = [m for e in entries for m in e["members"]]
            if not include_all:
                ids += [e["id"] for e in self.out.optional.get(key, [])]
            rs = [kept[i] for i in dict.fromkeys(ids) if i in kept and not kept[i].props.quantum]
            if len(rs) < 2:
                continue
            points = samples(problem.symbols(), [c.constraint for c in problem.constraints], ctx.constants, count=200)
            exprs = {r.id: ostar(r.bound, ctx).expr for r in rs}
            for a in rs:
                for b in rs:
                    if a is b or compare_ostar(self.analyse(a), self.analyse(b), ctx) != Relation.INCOMPARABLE:
                        continue
                    if dominates(exprs[a.id], exprs[b.id], points):
                        both = dominates(exprs[b.id], exprs[a.id], points)
                        if both and a.id > b.id:
                            continue  # report an apparent equality once
                        item = {"problem": pid, "node": node, "smaller": a.id, "larger": b.id,
                                "equal": bool(both), "samples": len(points)}
                        if item not in out:
                            out.append(item)
        return out

    def beats_ostar(self, s: Result, r: Result, ctx: Context) -> bool:
        """s beats r in the Overview: a better bound in O* form, or the same bound and s is
        stronger (decided 18 November 2026): deterministic beats randomized and polynomial
        space beats exponential space, since such an algorithm is also one of the weaker kind
        (ignore the random bits; space is bounded by time)."""
        rel = compare_ostar(self.analyse(s), self.analyse(r), ctx)
        return rel == Relation.BETTER or (rel in (Relation.EQUAL, Relation.TIE) and stronger(s.props, r.props))

    def overview(self, include_all: bool = False) -> dict[tuple[str, str], list[dict]]:
        """What the Overview tab (the default view) shows: the best non-quantum bounds
        obtained by any means, compared in O* form. Bounds equal in O* form are grouped;
        the earliest by year are cited, all of them on a tie (decided 7 November 2026).
        The Details tab lists every kept result, with filters. With include_all, results
        from preprints and unverified papers count too, and named constants take their best
        claimed value instead of the best published one (18 November 2026)."""
        out: dict[tuple[str, str], list[dict]] = {}
        for key, kept in sorted(self.out.results.items()):
            ctx = (self.out.claimed if include_all else self.out.published)[key[0]]
            # the Overview leaves out quantum results and results from unverified papers or
            # preprints; readers can include those (optional_overview, overview_all)
            cands = [r for r in kept if not r.props.quantum and (include_all or (r.props.verified and r.props.reviewed))]
            best = [
                r for r in cands
                if not any(
                    s is not r and self.beats_ostar(s, r, ctx)
                    for s in cands
                )
            ]
            groups: list[list[Result]] = []
            for r in best:
                for g in groups:
                    if compare_ostar(self.analyse(g[0]), self.analyse(r), ctx) == Relation.EQUAL:
                        g.append(r)
                        break
                else:
                    groups.append([r])
            entries = []
            for g in groups:
                dated = [r.year for r in g if r.year is not None]
                first = min(dated) if dated else None
                entries.append({
                    "members": [r.id for r in g],
                    "cite": [r.id for r in g if r.year == first],
                    "year": first,
                })
            out[key] = entries
        return out

    def optional_overview(self) -> dict[tuple[str, str], list[dict]]:
        """Kept non-quantum results from unverified papers or preprints that a reader can switch
        into the Overview (browser-stored: all at once from the Overview or the front page, or
        one by one in Details for unverified results). Each lists the Overview members it beats in O*
        form; one that a verified Overview member beats or equals would change nothing and is
        left out."""
        out: dict[tuple[str, str], list[dict]] = {}
        for key, kept in sorted(self.out.results.items()):
            ctx = self.out.published[key[0]]
            members = {m for e in self.out.overview.get(key, []) for m in e["members"]}
            best = [r for r in kept if r.id in members]
            entries = []
            for u in kept:
                if (u.props.verified and u.props.reviewed) or u.props.quantum:
                    continue
                rel = [compare_ostar(self.analyse(b), self.analyse(u), ctx) for b in best]
                # including u changes nothing if an Overview member beats it, or matches it and is
                # at least as strong (deterministic, polynomial space)
                ties = [b for b, x in zip(best, rel) if x in (Relation.EQUAL, Relation.TIE)]
                if any(x == Relation.BETTER for x in rel) or any(at_least_as_strong(b.props, u.props) for b in ties):
                    continue
                beats = [b.id for b, x in zip(best, rel) if x == Relation.WORSE] + [
                    b.id for b in ties if stronger(u.props, b.props)]
                entries.append({"id": u.id, "beats": beats, "year": u.year})
            if entries:
                out[key] = entries
        return out

    def as_reduction(self, red: Reduction, v: Variant) -> Reduction:
        """A variant used as a reduction of its own (same type; problems and versions may differ)."""
        eff = red.model_copy(update={
            "id": f"{red.id}~{v.id}",
            "from_": v.from_ if v.from_ is not None else red.from_,
            "to": v.to if v.to is not None else red.to,
            "parameter_map": v.parameter_map,
            "time": v.time if v.time is not None else red.time,
            "calls": v.calls if v.calls is not None else red.calls,
            "call_sizes": red.call_sizes if v.calls is None else None,
            "formal": v.formal,
            "variants": [],
        })
        self.variant_of[eff.id] = v
        return eff

    def still_kept(self, r: Result) -> bool:
        return any(s.id == r.id for s in self.out.results.get((r.problem, r.node), []))

    def beaten_by(self) -> dict[str, list[str]]:
        """For filters in the browser: which kept results have strictly better bounds."""
        out: dict[str, list[str]] = {}
        for (pid, _), kept in self.out.results.items():
            ctx = self.out.published[pid]
            for r in kept:
                out[r.id] = [
                    s.id for s in kept if s is not r and compare(self.analyse(s), self.analyse(r), ctx) == Relation.BETTER
                ]
        return out


def _earlier(s: Result, r: Result) -> bool:
    """s became known strictly before r (undated counts as latest)."""
    return s.year is not None and (r.year is None or s.year < r.year)


def _drop_subtractions(node: Node) -> Node:
    """Remove subtracted terms (all variables are nonnegative); checked by the comparator."""
    if isinstance(node, Add):
        kept = [(s, _drop_subtractions(t)) for s, t in node.terms if s > 0]
        if not kept:
            return Num(Fraction(0), "0")
        return kept[0][1] if len(kept) == 1 else Add(tuple(kept))
    if isinstance(node, Mul):
        return Mul(tuple(_drop_subtractions(f) for f in node.factors))
    if isinstance(node, Pow):
        return Pow(_drop_subtractions(node.base), _drop_subtractions(node.exp))
    return node


def _family(var: str) -> Bound:
    """O*(2^{δ var}) for every δ > 0: the class SE of IPZ 2001 (rulebook §5)."""
    return Bound("O*", Pow(Num(Fraction(2), "2"), Mul((Const("delta"), Var(var)))), True)


def _num_text(p: Fraction) -> str:
    return str(p.numerator) if p.denominator == 1 else f"{p.numerator}/{p.denominator}"


def derive(data: Dataset) -> Derivation:
    return Engine(data).run()


# --- output ----------------------------------------------------------------------------------


def to_json(data: Dataset, d: Derivation) -> dict:
    nodes: dict[str, dict[str, list[dict]]] = {}
    for (pid, node), kept in sorted(d.results.items()):
        ctx = d.contexts[pid]
        rows = [_row(r, ctx, d.beaten_by.get(r.id, [])) for r in kept]
        nodes.setdefault(pid, {})[node] = rows
    overview: dict[str, dict[str, list[dict]]] = {}
    for (pid, node), groups in sorted(d.overview.items()):
        overview.setdefault(pid, {})[node] = groups
    overview_all: dict[str, dict[str, list[dict]]] = {}
    for (pid, node), groups in sorted(d.overview_all.items()):
        overview_all.setdefault(pid, {})[node] = groups
    superseded: dict[str, dict[str, list[dict]]] = {}
    for (pid, node), entries in sorted(d.superseded.items()):
        ctx = d.contexts[pid]
        superseded.setdefault(pid, {})[node] = [
            {**_row(r, ctx, []), "superseded_by": ids} for r, ids in entries
        ]
    return {
        "rulebook_version": RULEBOOK_VERSION,
        "problems": nodes,
        "overview": overview,
        "overview_all": overview_all,
        "overview_optional": {
            pid: {node: e for (p2, node), e in sorted(d.optional.items()) if p2 == pid}
            for pid in sorted({p for p, _ in d.optional})
        },
        "superseded": superseded,
        "undecided": d.undecided,
        "log": d.log,
    }


def _row(r: Result, ctx: Context, beaten_by: list[str]) -> dict:
    from .bounds import render_bound
    from .bounds.expr import fixed_parameters

    shown = display(r.bound, ctx, derived=r.derived)
    return {
        "id": r.id,
        "origin": "derived" if r.derived else "direct",
        "algorithm": r.origin,
        "exact": render_bound(r.bound),
        "shown": shown.tex,
        "hover": shown.hover,
        "parameters": sorted(variables(ostar(r.bound, ctx).expr)),
        "fixed": sorted(fixed_parameters(r.bound.expr)),
        "properties": {
            "deterministic": r.props.deterministic,
            "polynomial_space": r.props.poly_space,
            "constructive": r.props.constructive,
            "algebraic": r.props.algebraic,
            "fast_matrix_multiplication": r.props.fast_matrix_multiplication,
            "quantum": r.props.quantum,
            "formal": r.props.formal,
            "lean_verified": r.props.lean,
        },
        "conditional_on": sorted(r.props.conditional_on),
        "flags": sorted(r.flags | ({"long-chain"} if r.steps > LONG_CHAIN else set())),
        "steps": r.steps,
        "chain": [
            {
                "kind": s.kind,
                "id": s.id,
                "from": s.from_node,
                "to": s.to_node,
                "type": s.type,
                "parameter_map": dict(s.parameter_map),
                "note": s.note,
            }
            for s in r.chain
        ],
        "beaten_by": beaten_by,
        "year": r.year,
        "papers": list(r.papers),
    }
