"""Load the data folder and check it: each file against its model, then across files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .bounds import BoundSyntaxError, Context, build_context, parse_bound, parse_expr
from .bounds.compare import ConstraintError
from .bounds.expr import _CONST_CMDS, constants, variables
from .bounds.growth import UnsupportedBound, value_growth
from .schema import (
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
        if not any(paper.versions[v].open_access for v in src.statements if v in paper.versions):
            issues.append(
                Issue(where, f"no statement for an open-access version of paper '{src.paper}'")
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

    for aid, alg in data.entries["algorithms"].items():
        assert isinstance(alg, Algorithm)
        where = f"algorithms/{aid}.yaml"
        problem = problem_version(f"{where}: proved_for", alg.problem, alg.proved_for)
        bound_parameters(f"{where}: bound.parameters", problem, alg.bound.parameters)
        known_hypotheses(f"{where}: conditional_on", alg.conditional_on)
        source(f"{where}: source", alg.source)

    for rid, red in data.entries["reductions"].items():
        assert isinstance(red, Reduction)
        where = f"reductions/{rid}.yaml"
        problem_version(f"{where}: from", red.from_.problem, red.from_.version)
        target = problem_version(f"{where}: to", red.to.problem, red.to.version)
        maps = [("parameter_map", red.parameter_map)] + [
            (f"variants.{i}.parameter_map", v.parameter_map) for i, v in enumerate(red.variants)
        ]
        if target is not None:
            for field_name, pmap in maps:
                for p in pmap:
                    if p not in target.symbols():
                        issues.append(
                            Issue(f"{where}: {field_name}", f"parameter '{p}' is not defined by problem '{target.id}'")
                        )
        for i, variant in enumerate(red.variants):
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
        for name in sorted(constants(parsed.expr) - {"varepsilon", "delta"}):
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
            if v.time is not None and source is not None:
                try:
                    parse_bound(v.time, source.symbols())
                except BoundSyntaxError as exc:
                    issues.append(Issue(f"{where}: variants.{i}.time", str(exc)))
            if isinstance(v.calls, str):
                expr(f"{where}: variants.{i}.calls", source, v.calls)
            for var, rhs in v.parameter_map.items():
                expr(f"{where}: variants.{i}.parameter_map.{var}", source, rhs)
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


def problem_context(data: Dataset, problem: Problem) -> Context:
    """Everything the comparator needs about one problem (bounds B4, B5, §2)."""
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
        lo, hi = constant_range(const)  # type: ignore[arg-type]
        if hi is not None:
            consts[cid] = (lo, hi)
    return build_context(problem.symbols(), [c.constraint for c in problem.constraints], not_poly, consts)


def validate_raw(raw: dict[str, dict[str, Any]], redirects: Any = None) -> tuple[Dataset, list[Issue]]:
    data, issues = parse(raw, redirects)
    return data, issues + check_references(data) + check_expressions(data)


def validate_dir(data_dir: Path) -> tuple[Dataset, list[Issue]]:
    raw, redirects, issues = read_data_dir(data_dir)
    data, more = validate_raw(raw, redirects)
    return data, issues + more
