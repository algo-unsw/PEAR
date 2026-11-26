"""Load the data folder and check it: each file against its model, then across files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import ValidationError

from .bounds import BoundSyntaxError, Context, build_context, parse_bound, parse_expr
from .bounds.compare import ConstraintError
from .bounds.expr import _CONST_CMDS, constants, variables
from .bounds.growth import UnsupportedBound, value_growth
from .schema import (
    ATTESTATIONS,
    ENTITY_TYPES,
    Algorithm,
    FolkloreSource,
    Hypothesis,
    LowerBound,
    Model,
    NamedConstant,
    Paper,
    PaperSource,
    Problem,
    Reduction,
    SharedParameter,
    SharedParameterRef,
)

TOP_LEVEL_FILES = {"LICENSE", "README.md", "redirects.yaml"}


@dataclass(frozen=True)
class Issue:
    where: str  # e.g. "algorithms/foo.yaml" or "algorithms/foo.yaml: source"
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


@dataclass
class Dataset:
    entries: dict[str, dict[str, Model]] = field(
        default_factory=lambda: {folder: {} for folder in ENTITY_TYPES}
    )
    redirects: dict[str, dict[str, str]] = field(default_factory=dict)
    invalid: set[tuple[str, str]] = field(default_factory=set)  # entries that failed their own checks

    @property
    def problems(self) -> dict[str, Problem]:
        return self.entries["problems"]  # type: ignore[return-value]

    @property
    def papers(self) -> dict[str, Paper]:
        return self.entries["papers"]  # type: ignore[return-value]


# --- loading -----------------------------------------------------------------


def read_data_dir(data_dir: Path) -> tuple[dict[str, dict[str, Any]], Any, list[Issue]]:
    """Read every YAML file into {folder: {file stem: raw}}, plus raw redirects."""
    raw: dict[str, dict[str, Any]] = {folder: {} for folder in ENTITY_TYPES}
    issues: list[Issue] = []
    redirects: Any = None
    if not data_dir.is_dir():
        return raw, redirects, [Issue(str(data_dir), "data folder not found")]
    for path in sorted(data_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(data_dir)
        if len(rel.parts) == 1:
            if rel.name not in TOP_LEVEL_FILES:
                issues.append(Issue(str(rel), "unexpected file at the top of data/"))
            elif rel.name == "redirects.yaml":
                redirects, problem = _load_yaml(path)
                if problem:
                    issues.append(Issue(str(rel), problem))
            continue
        folder = rel.parts[0]
        if folder not in ENTITY_TYPES or len(rel.parts) != 2:
            issues.append(Issue(str(rel), "unexpected location; see docs/specs/schema.md §1"))
            continue
        if path.suffix != ".yaml":
            issues.append(Issue(str(rel), "data files use the .yaml extension"))
            continue
        content, problem = _load_yaml(path)
        if problem:
            issues.append(Issue(str(rel), problem))
        else:
            raw[folder][path.stem] = content
    return raw, redirects, issues


def _load_yaml(path: Path) -> tuple[Any, str | None]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")), None
    except yaml.YAMLError as exc:
        return None, f"not valid YAML: {exc}"


def parse(raw: dict[str, dict[str, Any]], redirects: Any = None) -> tuple[Dataset, list[Issue]]:
    """Check each file against its model; the file stem must equal the entry's id."""
    data = Dataset()
    issues: list[Issue] = []
    for folder, model in ENTITY_TYPES.items():
        for stem, content in sorted(raw.get(folder, {}).items()):
            where = f"{folder}/{stem}.yaml"
            if not isinstance(content, dict):
                issues.append(Issue(where, "expected a mapping of fields"))
                data.invalid.add((folder, stem))
                continue
            try:
                entry = model.model_validate(content)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = ".".join(str(part) for part in err["loc"])
                    issues.append(Issue(f"{where}: {loc}" if loc else where, err["msg"]))
                data.invalid.add((folder, stem))
                continue
            if entry.id != stem:  # type: ignore[attr-defined]
                issues.append(Issue(where, f"id '{entry.id}' does not match the file name"))  # type: ignore[attr-defined]
                data.invalid.add((folder, stem))
                continue
            data.entries[folder][stem] = entry
    if redirects is not None:
        issues += _parse_redirects(redirects, data)
    return data, issues


def _parse_redirects(redirects: Any, data: Dataset) -> list[Issue]:
    where = "redirects.yaml"
    if not isinstance(redirects, dict):
        return [Issue(where, "expected a mapping from folder to {old-id: new-id}")]
    issues: list[Issue] = []
    for folder, mapping in redirects.items():
        if folder not in ENTITY_TYPES:
            issues.append(Issue(where, f"unknown folder '{folder}'"))
            continue
        if not isinstance(mapping, dict):
            issues.append(Issue(f"{where}: {folder}", "expected {old-id: new-id}"))
            continue
        for old, new in mapping.items():
            if old in data.entries[folder]:
                issues.append(Issue(f"{where}: {folder}.{old}", "redirect shadows an existing entry"))
            if new not in data.entries[folder] and (folder, new) not in data.invalid:
                issues.append(Issue(f"{where}: {folder}.{old}", f"redirect target '{new}' does not exist"))
        data.redirects[folder] = dict(mapping)
    return issues


# --- checks across files -----------------------------------------------------


def check_references(data: Dataset) -> list[Issue]:
    issues: list[Issue] = []
    hypotheses = data.entries["hypotheses"]

    def problem_version(where: str, problem_id: str, version: str | None) -> Problem | None:
        problem = data.problems.get(problem_id)
        if problem is None:
            issues.append(Issue(where, f"unknown problem '{problem_id}'"))
            return None
        if version is not None and version not in problem.versions:
            issues.append(Issue(where, f"problem '{problem_id}' has no version '{version}'"))
        return problem

    def source(where: str, src: PaperSource | FolkloreSource | None) -> None:
        if src is None:
            return
        if isinstance(src, FolkloreSource):
            if src.reference is not None:
                paper_version(where, src.reference.paper, src.reference.version)
            return
        paper = data.papers.get(src.paper)
        if paper is None:
            issues.append(Issue(where, f"unknown paper '{src.paper}'"))
            return
        for version in src.statements:
            if version not in paper.versions:
                issues.append(Issue(where, f"paper '{src.paper}' has no version '{version}'"))
        # A statement in any version we read, open or closed, or Serge's confirmation of a
        # closed-source result, is enough (CLAUDE.md rule 2, 21 November 2026).
        if src.statements or src.confirmed_by is not None:
            return
        if any(v.open_access for v in paper.versions.values()):
            issues.append(Issue(where, f"no statement for an open-access version of paper '{src.paper}' "
                                       "(attestations replace a statement only for a paper we cannot read)"))
            return
        # A closed paper we could not read: independent web sources must confirm the result.
        hosts = {urlparse(u).netloc.lower().removeprefix("www.") for u in src.attested_by}
        hosts.discard("")
        if len(hosts) < ATTESTATIONS:
            issues.append(
                Issue(
                    where,
                    f"paper '{src.paper}' has no open-access version: give a statement for an open version, "
                    f"or attested_by with at least {ATTESTATIONS} independent web sources (found {len(hosts)})",
                )
            )

    def paper_version(where: str, paper_id: str, version: str | None) -> None:
        paper = data.papers.get(paper_id)
        if paper is None:
            issues.append(Issue(where, f"unknown paper '{paper_id}'"))
        elif version is not None and version not in paper.versions:
            issues.append(Issue(where, f"paper '{paper_id}' has no version '{version}'"))

    def known_hypotheses(where: str, ids: list[str]) -> None:
        for hid in ids:
            if hid not in hypotheses:
                issues.append(Issue(where, f"unknown hypothesis '{hid}'"))

    def bound_parameters(where: str, problem: Problem | None, params: list[str]) -> None:
        if problem is None:
            return
        for p in params:
            if p not in problem.symbols():
                issues.append(Issue(where, f"parameter '{p}' is not defined by problem '{problem.id}'"))

    shared: dict[str, SharedParameter] = data.entries["parameters"]  # type: ignore[assignment]

    for pid, problem in data.problems.items():
        where = f"problems/{pid}.yaml"
        source(f"{where}: complexity.source", problem.complexity.source)
        for symbol, entry in problem.parameters.items():
            if isinstance(entry, SharedParameterRef):
                param = shared.get(entry.shared)
                if param is None:
                    issues.append(Issue(f"{where}: parameters.{symbol}", f"unknown shared parameter '{entry.shared}'"))
                elif param.symbol != symbol:
                    issues.append(
                        Issue(f"{where}: parameters.{symbol}", f"shared parameter '{param.id}' uses the symbol '{param.symbol}'")
                    )
        for rel in problem.related:
            if rel.problem == pid:
                issues.append(Issue(f"{where}: related", "a problem cannot be related to itself"))
            elif rel.problem not in data.problems:
                issues.append(Issue(f"{where}: related", f"unknown problem '{rel.problem}'"))
        if problem.implementations is not None:
            ranked = problem.implementations.ranked
            if len(ranked) != len(set(ranked)):
                issues.append(Issue(f"{where}: implementations", "an implementation is ranked twice"))
            for iid in ranked:
                impl = data.entries["implementations"].get(iid)
                if impl is None:
                    issues.append(Issue(f"{where}: implementations", f"unknown implementation '{iid}'"))
                elif not any(s.problem == pid for s in impl.solves):  # type: ignore[attr-defined]
                    issues.append(Issue(f"{where}: implementations", f"implementation '{iid}' does not solve '{pid}'"))
                elif not any(s.problem == pid and s.exact is True for s in impl.solves):  # type: ignore[attr-defined]
                    # agreed 8 November 2026: only exact implementations are listed
                    issues.append(Issue(f"{where}: implementations", f"implementation '{iid}' is not marked exact for '{pid}'"))

    for iid, impl in data.entries["implementations"].items():
        where = f"implementations/{iid}.yaml"
        for i, s in enumerate(impl.solves):  # type: ignore[attr-defined]
            problem_version(f"{where}: solves.{i}", s.problem, None)
            for v in s.versions:
                problem_version(f"{where}: solves.{i}.versions", s.problem, v)

    for aid, alg in data.entries["algorithms"].items():
        assert isinstance(alg, Algorithm)
        where = f"algorithms/{aid}.yaml"
        problem = problem_version(f"{where}: proved_for", alg.problem, alg.proved_for)
        bound_parameters(f"{where}: bound.parameters", problem, alg.bound.parameters)
        known_hypotheses(f"{where}: conditional_on", alg.conditional_on)
        source(f"{where}: source", alg.source)
        for u in alg.uses:
            if u == aid or u not in data.entries["algorithms"]:
                issues.append(Issue(f"{where}: uses", f"unknown or self reference '{u}'"))

    # `uses` must not form a cycle (a result cannot rely on itself)
    def uses_cycle(start: str) -> bool:
        seen, todo = set(), list(getattr(data.entries["algorithms"][start], "uses", []))
        while todo:
            u = todo.pop()
            if u == start:
                return True
            if u in seen or u not in data.entries["algorithms"]:
                continue
            seen.add(u)
            todo.extend(data.entries["algorithms"][u].uses)  # type: ignore[attr-defined]
        return False

    for aid in data.entries["algorithms"]:
        if uses_cycle(aid):
            issues.append(Issue(f"algorithms/{aid}.yaml: uses", "the uses relation has a cycle through this result"))

    for tid, tech in data.entries["techniques"].items():
        where = f"techniques/{tid}.yaml"
        source(f"{where}: source", tech.source)  # type: ignore[attr-defined]
        try:
            parse_expr(tech.base, ["c"])  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            issues.append(Issue(f"{where}: base", f"not an expression in c: {exc}"))
        for i, ap in enumerate(tech.applies_to):  # type: ignore[attr-defined]
            prob = problem_version(f"{where}: applies_to[{i}]", ap.problem, ap.version)
            if prob is not None:
                # the universe is one of the problem's basic objects (n), the budget one of its
                # parameters (the solution size k): the input must be c^budget, the output is in
                # the universe size
                if ap.universe not in ({"n"} | ({"m"} if prob.objects.m is not None else set())):
                    issues.append(Issue(f"{where}: applies_to[{i}].universe",
                                        f"'{ap.universe}' is not an object count of problem '{ap.problem}'"))
                if ap.budget not in prob.parameters:
                    issues.append(Issue(f"{where}: applies_to[{i}].budget",
                                        f"'{ap.budget}' is not a parameter of problem '{ap.problem}'"))

    for rid, red in data.entries["reductions"].items():
        assert isinstance(red, Reduction)
        where = f"reductions/{rid}.yaml"
        problem_version(f"{where}: from", red.from_.problem, red.from_.version)
        target = problem_version(f"{where}: to", red.to.problem, red.to.version)
        def check_map(field_name: str, pmap: dict[str, str], tgt: Problem | None) -> None:
            if tgt is None:
                return
            for p in pmap:
                if p not in tgt.symbols():
                    issues.append(Issue(f"{where}: {field_name}", f"parameter '{p}' is not defined by problem '{tgt.id}'"))

        check_map("parameter_map", red.parameter_map, target)

        def counting_ends(field_name: str, ref) -> None:
            """A counting reduction (rulebook §2a) runs between counting versions only."""
            prob = data.problems.get(ref.problem)
            if prob is None or ref.version not in prob.versions:
                return
            if prob.versions[ref.version].kind != "counting":
                issues.append(Issue(f"{where}: {field_name}", f"a polytime-counting reduction needs counting versions, "
                                    f"but '{ref.problem}' version '{ref.version}' is {prob.versions[ref.version].kind}"))

        if red.type == "polytime-counting":
            counting_ends("from", red.from_)
            counting_ends("to", red.to)
            for i, variant in enumerate(red.variants):
                counting_ends(f"variants.{i}.from", variant.from_ or red.from_)
                counting_ends(f"variants.{i}.to", variant.to or red.to)
        for i, variant in enumerate(red.variants):
            v_target = target
            if variant.from_ is not None:
                problem_version(f"{where}: variants.{i}.from", variant.from_.problem, variant.from_.version)
            if variant.to is not None:
                v_target = problem_version(f"{where}: variants.{i}.to", variant.to.problem, variant.to.version)
            check_map(f"variants.{i}.parameter_map", variant.parameter_map, v_target)
            source(f"{where}: variants.{i}.source", variant.source)
        source(f"{where}: source", red.source)

    for hid, hyp in hypotheses.items():
        assert isinstance(hyp, Hypothesis)
        where = f"hypotheses/{hid}.yaml"
        for other in hyp.implies:
            if other == hid:
                issues.append(Issue(f"{where}: implies", "a hypothesis cannot imply itself"))
            elif other not in hypotheses:
                issues.append(Issue(f"{where}: implies", f"unknown hypothesis '{other}'"))
        for i, s in enumerate(hyp.status_sources):
            if s.paper is not None:
                paper_version(f"{where}: status_sources.{i}", s.paper, s.version)

    for lid, lb in data.entries["lower-bounds"].items():
        assert isinstance(lb, LowerBound)
        where = f"lower-bounds/{lid}.yaml"
        problem = problem_version(f"{where}: version", lb.problem, lb.version)
        bound_parameters(f"{where}: bound.parameters", problem, lb.bound.parameters)
        known_hypotheses(f"{where}: conditional_on", lb.conditional_on)
        source(f"{where}: source", lb.source)

    for cid, const in data.entries["constants"].items():
        assert isinstance(const, NamedConstant)
        where = f"constants/{cid}.yaml"
        source(f"{where}: definition_source", const.definition_source)
        for i, cb in enumerate(const.bounds):
            for j, s in enumerate(cb.sources):
                source(f"{where}: bounds.{i}.sources.{j}", s)

    # A reference to an entry that failed its own checks is already reported there.
    kinds = {"problems": "problem", "papers": "paper", "hypotheses": "hypothesis", "parameters": "shared parameter"}
    already = {f"unknown {kinds[folder]} '{eid}'" for folder, eid in data.invalid if folder in kinds}
    return [issue for issue in issues if issue.message not in already]


def check_expressions(data: Dataset) -> list[Issue]:
    """Parse every bound, time, call count, parameter map and constraint (bounds §1)."""
    issues: list[Issue] = []

    def bound(where: str, problem: Problem | None, b) -> None:
        if problem is None:
            return
        try:
            parsed = parse_bound(b.as_stated, problem.symbols())
        except BoundSyntaxError as exc:
            issues.append(Issue(f"{where}.as_stated", str(exc)))
            return
        if (parsed.notation or "O") != b.notation:
            issues.append(
                Issue(f"{where}.notation", f"'{b.notation}' does not match the notation of as_stated ('{parsed.notation or 'O'}')")
            )
        for name in sorted(constants(parsed.expr) - {"varepsilon", "delta", "e"}):  # e: the base of \ln
            if name not in data.entries["constants"]:
                issues.append(Issue(f"{where}.as_stated", f"uses \\{name}, but data/constants/{name}.yaml does not exist"))
        used = variables(parsed.expr)
        if used != set(b.parameters):
            issues.append(
                Issue(f"{where}.parameters", f"lists {sorted(b.parameters)}, but as_stated uses {sorted(used)}")
            )

    def expr(where: str, problem: Problem | None, text: str) -> None:
        if problem is None:
            return
        try:
            parse_expr(text, problem.symbols())
        except BoundSyntaxError as exc:
            issues.append(Issue(where, str(exc)))

    for pid, problem in data.problems.items():
        try:
            build_context(problem.symbols(), [c.constraint for c in problem.constraints])
        except (BoundSyntaxError, ConstraintError) as exc:
            issues.append(Issue(f"problems/{pid}.yaml: constraints", str(exc)))

    for cid, const in data.entries["constants"].items():
        assert isinstance(const, NamedConstant)
        where = f"constants/{cid}.yaml"
        if _CONST_CMDS.get(const.symbol) != cid or cid in ("varepsilon", "delta"):
            issues.append(Issue(f"{where}: symbol", f"'{const.symbol}' is not a named constant the parser knows as '{cid}'"))
        for i, cb in enumerate(const.bounds):
            if constant_value(cb.value) is None:
                issues.append(Issue(f"{where}: bounds.{i}.value", f"'{cb.value}' is not a number"))
        lo, hi = constant_range(const)
        if hi is None:
            issues.append(Issue(f"{where}: bounds", "needs at least one upper bound that is not refuted"))
        elif lo > hi:
            issues.append(Issue(f"{where}: bounds", f"lower bound {lo} exceeds upper bound {hi}"))

    for aid, alg in data.entries["algorithms"].items():
        assert isinstance(alg, Algorithm)
        bound(f"algorithms/{aid}.yaml: bound", data.problems.get(alg.problem), alg.bound)
        space, problem = alg.properties.space, data.problems.get(alg.problem)
        if space.bound is not None and problem is not None:
            # time–space frontiers (23 November 2026): in the bound language, in (some of) the
            # running time's parameters
            where = f"algorithms/{aid}.yaml: properties.space.bound"
            try:
                parsed = parse_bound(space.bound, problem.symbols())
            except BoundSyntaxError as exc:
                issues.append(Issue(where, str(exc)))
            else:
                extra = variables(parsed.expr) - set(alg.bound.parameters)
                if extra:
                    issues.append(Issue(where, f"uses {sorted(extra)}, which the running time does not"))

    for lid, lb in data.entries["lower-bounds"].items():
        assert isinstance(lb, LowerBound)
        bound(f"lower-bounds/{lid}.yaml: bound", data.problems.get(lb.problem), lb.bound)

    for rid, red in data.entries["reductions"].items():
        assert isinstance(red, Reduction)
        where = f"reductions/{rid}.yaml"
        source = data.problems.get(red.from_.problem)
        if source is not None:
            try:
                parse_bound(red.time, source.symbols())
            except BoundSyntaxError as exc:
                issues.append(Issue(f"{where}: time", str(exc)))
        if isinstance(red.calls, str):
            expr(f"{where}: calls", source, red.calls)
        for var, rhs in red.parameter_map.items():
            expr(f"{where}: parameter_map.{var}", source, rhs)
        for i, v in enumerate(red.variants):
            v_source = data.problems.get(v.from_.problem) if v.from_ is not None else source
            if v.time is not None and v_source is not None:
                try:
                    parse_bound(v.time, v_source.symbols())
                except BoundSyntaxError as exc:
                    issues.append(Issue(f"{where}: variants.{i}.time", str(exc)))
            if isinstance(v.calls, str):
                expr(f"{where}: variants.{i}.calls", v_source, v.calls)
            for var, rhs in v.parameter_map.items():
                expr(f"{where}: variants.{i}.parameter_map.{var}", v_source, rhs)
    return issues


def constant_value(text: str) -> float | None:
    try:
        g = value_growth(parse_expr(text, ()))
    except (BoundSyntaxError, UnsupportedBound):
        return None
    if not g.terms:
        return 0.0
    s = g.single()
    if s is None or s[0] != () or s[1].kind != "exact" or s[1].shift:
        return None
    return s[1].value


def constant_range(const: NamedConstant) -> tuple[float, float | None]:
    """Best known (lower, upper) bounds; claimed bounds count, refuted ones do not."""
    lows = [constant_value(b.value) for b in const.bounds if b.relation == "ge" and b.status != "refuted"]
    highs = [constant_value(b.value) for b in const.bounds if b.relation == "le" and b.status != "refuted"]
    lows = [v for v in lows if v is not None]
    highs = [v for v in highs if v is not None]
    return (max(lows) if lows else 0.0, min(highs) if highs else None)


def constant_best(const: NamedConstant, claimed: bool) -> float | None:
    """The current best upper bound, used as the constant's value in comparisons (decided
    18 November 2026): published (established) bounds only, or claimed ones too."""
    ok = ("established", "claimed") if claimed else ("established",)
    highs = [constant_value(b.value) for b in const.bounds if b.relation == "le" and b.status in ok]
    highs = [v for v in highs if v is not None]
    return min(highs) if highs else None


# How comparisons treat a named constant such as ω (decided 18 November 2026): at its best
# published value (the default Overview), at its best claimed value (the Overview with
# preprints and unverified results included), or anywhere between the two (keeping results,
# so that a result is dropped only if it is beaten at both values).
CONSTANT_MODES = ("published", "claimed", "between")


def problem_context(data: Dataset, problem: Problem, constants: str = "between") -> Context:
    """Everything the comparator needs about one problem (bounds B4, B5, §2). Named
    constants take their best published or claimed value, or the range between the two
    (CONSTANT_MODES)."""
    shared = data.entries["parameters"]
    not_poly = []
    for symbol, entry in problem.parameters.items():
        if isinstance(entry, SharedParameterRef):
            param = shared.get(entry.shared)
            if param is not None and not param.poly_bounded:  # type: ignore[attr-defined]
                not_poly.append(symbol)
        elif not entry.poly_bounded:
            not_poly.append(symbol)
    consts = {}
    for cid, const in data.entries["constants"].items():
        published = constant_best(const, claimed=False)  # type: ignore[arg-type]
        claimed = constant_best(const, claimed=True)  # type: ignore[arg-type]
        if constants == "published" and published is not None:
            consts[cid] = (published, published)
        elif constants == "claimed" and claimed is not None:
            consts[cid] = (claimed, claimed)
        elif constants == "between" and claimed is not None:
            consts[cid] = (claimed, published if published is not None else claimed)
    # parameter-map expressions of reductions from this problem are nonnegative: each bounds
    # a parameter of the produced instance (18 November 2026)
    nonneg = []
    for red in data.entries["reductions"].values():
        maps = [(red.from_, red.parameter_map)] + [  # type: ignore[attr-defined]
            (v.from_ or red.from_, v.parameter_map) for v in red.variants]  # type: ignore[attr-defined]
        for frm, pmap in maps:
            if frm.problem == problem.id:
                nonneg += [e for e in pmap.values() if e not in problem.symbols()]
    return build_context(problem.symbols(), [c.constraint for c in problem.constraints], not_poly, consts,
                         sorted(set(nonneg)))


def validate_raw(raw: dict[str, dict[str, Any]], redirects: Any = None) -> tuple[Dataset, list[Issue]]:
    data, issues = parse(raw, redirects)
    return data, issues + check_references(data) + check_expressions(data)


def validate_dir(data_dir: Path) -> tuple[Dataset, list[Issue]]:
    raw, redirects, issues = read_data_dir(data_dir)
    data, more = validate_raw(raw, redirects)
    return data, issues + more
