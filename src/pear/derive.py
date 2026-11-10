"""Derivation engine: the reduction rulebook (docs/specs/rulebook.md, version 2).

Starting from the algorithms in the data, bounds are transferred backwards along
reductions (an algorithm for B plus a reduction from A to B gives a bound for A),
along "special case" links between versions, and projected onto single parameters,
until nothing changes. A derived bound is kept unless another result is at least as
good both as a bound and in every filter the site offers (DESIGN.md: deterministic,
polynomial space, constructive, non-algebraic, Lean-verified, direct, classical).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Iterable

from .bounds import Bound, Relation, compare, display, ostar, parse_bound, parse_expr
from .bounds.compare import Analysed, Context, analyse, compare_ostar
from .bounds.display import simplify, substitute
from .bounds.expr import Add, Const, Log, Mul, Node, Num, Pow, Var, variables
from .bounds.growth import is_monotone
from .schema import Algorithm, FolkloreSource, Hypothesis, PaperSource, Problem, Reduction, Variant
from .validate import Dataset, problem_context

RULEBOOK_VERSION = 3
LONG_CHAIN = 3  # rulebook §9: longer chains get a label (they are followed while they improve results)
FORMAL_ORDER = {"informal": 0, "statement": 1, "proved": 2}


# --- results ----------------------------------------------------------------------


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
        )


@dataclass(frozen=True)
class Step:
    kind: str  # reduction | special-case | projection
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
    contexts: dict[str, Context] = field(default_factory=dict)
    beaten_by: dict[str, list[str]] = field(default_factory=dict)  # result id -> ids of strictly better bounds
    overview: dict[tuple[str, str], list[dict]] = field(default_factory=dict)  # (problem, node) -> groups
    # direct results beaten in every filter (version 3): not in Details, kept for the bound history
    superseded: dict[tuple[str, str], list[tuple[Result, list[str]]]] = field(default_factory=dict)


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
            self.out.contexts[pid] = problem_context(data, problem)
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

    def direct(self, alg: Algorithm) -> Result | None:
        problem = self.data.problems[alg.problem]
        if not self.usable(alg.status):
            self.log(f"{alg.id}: status '{alg.status}', not used (rulebook A3)")
            return None
        excluded, flags = self.hypothesis_flags(alg.conditional_on)
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
            conditional_on=self.weakest(alg.conditional_on),
        )
        _, node = node_key(problem, alg.proved_for)
        year, papers = self.dated(alg.source)
        flags = set(flags) | {f"given-{g}" for g in alg.given}
        if any(self.data.papers[p].unverified for p in papers):
            props = replace(props, verified=False)
            flags.add("unverified")
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
                for d in produced:
                    if self.insert(d):
                        new.append(d)
                        for proj in self.projections(d):
                            if self.insert(proj):
                                new.append(proj)
            frontier = new
        self.out.beaten_by = self.beaten_by()
        self.out.overview = self.overview()
        return self.out

    def overview(self) -> dict[tuple[str, str], list[dict]]:
        """What the Overview tab (the default view) shows: the best non-quantum bounds
        obtained by any means, compared in O* form. Bounds equal in O* form are grouped;
        the earliest by year are cited, all of them on a tie (decided 7 November 2026).
        The Details tab lists every kept result, with filters."""
        out: dict[tuple[str, str], list[dict]] = {}
        for key, kept in sorted(self.out.results.items()):
            ctx = self.out.contexts[key[0]]
            # the Overview leaves out quantum results and results from unverified papers
            cands = [r for r in kept if not r.props.quantum and r.props.verified]
            best = [
                r for r in cands
                if not any(
                    s is not r and compare_ostar(self.analyse(s), self.analyse(r), ctx) == Relation.BETTER
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
            ctx = self.out.contexts[pid]
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
        "superseded": superseded,
        "log": d.log,
    }


def _row(r: Result, ctx: Context, beaten_by: list[str]) -> dict:
    from .bounds import render_bound

    shown = display(r.bound, ctx, derived=r.derived)
    return {
        "id": r.id,
        "origin": "derived" if r.derived else "direct",
        "algorithm": r.origin,
        "exact": render_bound(r.bound),
        "shown": shown.tex,
        "hover": shown.hover,
        "parameters": sorted(variables(ostar(r.bound, ctx).expr)),
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
