"""Pydantic models for PEAR data files, as agreed in docs/specs/schema.md.

Each model checks one file on its own. Checks across files (references,
open-access statements, parameters used by bounds) live in validate.py.
Bound strings are stored as text; parsing them is the bound language's job
(docs/specs/bounds.md, step 4).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    StringConstraints,
    Tag,
    model_validator,
)

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-{1,2}[a-z0-9]+)*$")]
Symbol = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
Text = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

APPROVER = "Serge Gaspers"  # Q7: sole sign-off on pilot data
SIZE_SYMBOLS = ("n", "m", "N")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


# --- shared blocks -----------------------------------------------------------


class Review(Model):
    approved_by: Literal["Serge Gaspers"] | None = None
    date: dt.date | None = None

    @model_validator(mode="after")
    def _both_or_neither(self) -> Review:
        if (self.approved_by is None) != (self.date is None):
            raise ValueError("review needs both approved_by and date, or neither")
        return self


class Statement(Model):
    statement: Text  # the label only, e.g. "Theorem 3.2" (Q4: no statement text)
    page: int | Text | None = None


ATTESTATIONS = 3  # independent web sources needed for a closed paper (CLAUDE.md rule 2)


class PaperSource(Model):
    paper: Id
    statements: dict[Id, Statement] = {}  # keyed by paper version
    # For a classic result whose paper has no open-access version: independent web sources
    # (found by a web search) that confirm the paper proved it. They replace the open statement.
    attested_by: list[Text] = []
    note: Text | None = None

    @model_validator(mode="after")
    def _statement_or_attestation(self) -> PaperSource:
        if not self.statements and not self.attested_by:
            raise ValueError("a paper source needs statements, or attested_by for a closed paper")
        return self


class Reference(Model):
    paper: Id
    version: Id
    statement: Text


class FolkloreSource(Model):
    folklore: Literal[True]
    note: Text
    reference: Reference | None = None


def _source_tag(value: Any) -> str:
    if isinstance(value, dict):
        return "folklore" if "folklore" in value else "paper"
    return "folklore" if isinstance(value, FolkloreSource) else "paper"


Source = Annotated[
    Union[Annotated[PaperSource, Tag("paper")], Annotated[FolkloreSource, Tag("folklore")]],
    Discriminator(_source_tag),
]


class Formal(Model):
    status: Literal["informal", "statement", "proved"] = "informal"
    prover: Text | None = None  # e.g. lean, isabelle
    link: Text | None = None

    @model_validator(mode="after")
    def _link_when_formal(self) -> Formal:
        if self.status != "informal" and (self.prover is None or self.link is None):
            raise ValueError(f"formal status '{self.status}' needs a prover and a link")
        return self


class Bound(Model):
    as_stated: Text  # exactly as the paper states it
    notation: Literal["O", "O*", "Õ"]
    parameters: list[Symbol] = Field(min_length=1)


class RandomError(Model):
    error: Literal["las-vegas", "one-sided", "two-sided"]  # Q6: display only


class Space(Model):
    class_: Literal["polynomial", "exponential"] = Field(alias="class")
    bound: Text | None = None


ResultStatus = Literal["valid", "flagged", "fixed", "easily-fixable", "unrepaired", "broken"]


class VersionRef(Model):
    problem: Id
    version: Id


# --- problem -----------------------------------------------------------------

Category = Literal["graph", "satisfiability", "sets", "numbers"]
VersionKind = Literal["decision", "optimisation", "search", "counting", "enumeration"]
Relation = Literal[
    "complement",
    "variant",
    "generalisation",
    "special-case",
    "counting",
    "enumeration",
    "weighted",
    "directed",
    "undirected",
]


class Complexity(Model):
    class_: Text = Field(alias="class")  # e.g. NP-complete, #P-complete
    source: Source


class Objects(Model):
    """What n, m and N count for this problem (rule 4)."""

    n: Text
    m: Text | None = None
    N: Text


class LocalParameter(Model):
    meaning: Text
    poly_bounded: bool = True  # bounds B4: O* absorbs polynomial factors in it


class SharedParameterRef(Model):
    shared: Id
    of: Text | None = None  # which graph or object it is measured on, e.g. "the primal graph"


def _parameter_tag(value: Any) -> str:
    if isinstance(value, dict):
        return "shared" if "shared" in value else "local"
    return "shared" if isinstance(value, SharedParameterRef) else "local"


ParameterEntry = Annotated[
    Union[Annotated[LocalParameter, Tag("local")], Annotated[SharedParameterRef, Tag("shared")]],
    Discriminator(_parameter_tag),
]


class Version(Model):
    kind: VersionKind
    input: Text
    question: Text | None = None  # decision versions
    goal: Text | None = None  # all other versions
    generalises: list[Id] = []

    @model_validator(mode="after")
    def _question_or_goal(self) -> Version:
        if self.kind == "decision":
            if self.question is None or self.goal is not None:
                raise ValueError("a decision version has a question and no goal")
        elif self.goal is None or self.question is not None:
            raise ValueError(f"a {self.kind} version has a goal and no question")
        return self


class Constraint(Model):
    """A relation between a problem's variables (bounds B5), e.g. k \\le n."""

    constraint: Annotated[str, StringConstraints(pattern=r"^.+\\(le|ge)\b.+$|^[^=]+=[^=]+$")]
    because: Text


class SharedBounds(Model):
    versions: list[Id] = Field(min_length=2)
    because: Text


class Related(Model):
    problem: Id
    relation: Relation


class Lean(Model):
    status: Literal["none", "statement", "proved"] = "none"
    link: Text | None = None
    library: Text | None = None
    library_version: Text | None = None

    @model_validator(mode="after")
    def _link_when_formalised(self) -> Lean:
        if self.status != "none" and self.link is None:
            raise ValueError(f"lean status '{self.status}' needs a link")
        return self


class Problem(Model):
    id: Id
    name: Text
    aliases: list[Text] = []
    category: Category
    complexity: Complexity
    objects: Objects
    parameters: dict[Symbol, ParameterEntry] = {}
    versions: dict[Id, Version] = Field(min_length=1)
    default_version: Id
    constraints: list[Constraint] = []
    shared_bounds: list[SharedBounds] = []
    related: list[Related] = []
    lean: Lean = Lean()
    review: Review = Review()

    @model_validator(mode="after")
    def _versions_consistent(self) -> Problem:
        clash = set(self.parameters) & set(SIZE_SYMBOLS)
        if clash:
            raise ValueError(f"parameters must not redefine {sorted(clash)}; use objects")
        if self.default_version not in self.versions:
            raise ValueError(f"default_version '{self.default_version}' is not a version")
        seen: set[str] = set()
        for group in self.shared_bounds:
            for v in group.versions:
                if v not in self.versions:
                    raise ValueError(f"shared_bounds names unknown version '{v}'")
                if v in seen:
                    raise ValueError(f"version '{v}' is in more than one shared_bounds group")
                seen.add(v)
        for key, version in self.versions.items():
            for target in version.generalises:
                if target not in self.versions:
                    raise ValueError(f"version '{key}' generalises unknown version '{target}'")
        if _has_cycle({k: v.generalises for k, v in self.versions.items()}):
            raise ValueError("generalises forms a cycle")
        return self

    def symbols(self) -> set[str]:
        """Every variable a bound for this problem may use."""
        base = {"n", "N"} | ({"m"} if self.objects.m is not None else set())
        return base | set(self.parameters)


def _has_cycle(edges: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}  # 1 = on the stack, 2 = done

    def visit(node: str) -> bool:
        state[node] = 1
        for nxt in edges.get(node, []):
            if state.get(nxt) == 1 or (nxt not in state and visit(nxt)):
                return True
        state[node] = 2
        return False

    return any(node not in state and visit(node) for node in edges)


# --- other entities ----------------------------------------------------------


class SharedParameter(Model):
    id: Id
    name: Text
    symbol: Symbol
    aliases: list[Text] = []
    definition: Text
    poly_bounded: bool = True
    review: Review = Review()


class PaperVersion(Model):
    kind: Literal[
        "preprint", "technical-report", "workshop", "conference", "journal", "book", "thesis"
    ]
    venue: Text | None = None
    year: int = Field(ge=1800, le=2100)
    doi: Text | None = None
    arxiv: Text | None = None
    url: Text | None = None
    open_access: bool

    @model_validator(mode="after")
    def _open_needs_link(self) -> PaperVersion:
        if self.open_access and not (self.url or self.arxiv or self.doi):
            raise ValueError("an open-access version needs a url, arxiv id or doi")
        return self


class Identifiers(Model):
    dblp: Text | None = None
    openalex: Text | None = None


class Paper(Model):
    id: Id
    title: Text
    authors: list[Text] = Field(min_length=1)
    identifiers: Identifiers = Identifiers()
    versions: dict[Id, PaperVersion] = Field(min_length=1)
    # Not peer reviewed or otherwise verified (e.g. an unrefereed technical report): its
    # results, and bounds derived from them, appear in Details but never in the Overview.
    unverified: bool = False
    review: Review = Review()


class Properties(Model):
    randomized: bool | RandomError
    space: Space
    algebraic: bool  # curator-assigned
    fast_matrix_multiplication: bool
    constructive: bool
    impractical_constants: Text | None = None
    quantum: bool

    @model_validator(mode="after")
    def _fmm_is_algebraic(self) -> Properties:
        if self.fast_matrix_multiplication and not self.algebraic:
            raise ValueError("fast_matrix_multiplication is a sub-tag of algebraic")
        return self


class Algorithm(Model):
    id: Id
    problem: Id
    proved_for: Id
    bound: Bound
    properties: Properties
    conditional_on: list[Id] = []
    # What the input comes with beyond the problem's definition, e.g. a tree decomposition
    # of width at most tw (definitions §4); shown as a note, carried along derivations.
    given: list[Literal["tree-decomposition"]] = []
    source: Source
    formal: Formal = Formal()
    status: ResultStatus = "valid"
    review: Review = Review()


class Variant(Model):
    """A slight modification of the reduction: a paper focused on one parameter but a variant
    also works for another, a known step (such as a kernelization) has to be added first, or
    the same construction works between other problems or versions (weighted vs unweighted,
    Red-Blue Dominating Set vs Set Cover). The reduction type stays the same."""

    id: Id
    note: Text  # what is modified
    from_: VersionRef | None = Field(None, alias="from")  # defaults to the reduction's
    to: VersionRef | None = None  # defaults to the reduction's
    parameter_map: dict[Symbol, Text] = Field(min_length=1)
    time: Text | None = None  # defaults to the reduction's
    calls: Annotated[int, Field(ge=1, strict=True)] | Text | None = None  # defaults to the reduction's
    source: Source | None = None  # None: written by the site, used only once approved (rule 6)
    formal: Formal = Formal()
    review: Review = Review()


class ReductionProperties(Model):
    """Tags beyond randomness (which the type carries); the rulebook decides their use."""

    space: Space | None = None
    constructive: bool | None = None


class Reduction(Model):
    id: Id
    from_: VersionRef = Field(alias="from")
    to: VersionRef
    type: Literal["polytime-deterministic", "polytime-randomized", "serf"]
    calls: Annotated[int, Field(ge=1, strict=True)] | Text = 1
    call_sizes: Text | None = None
    time: Text
    parameter_map: dict[Symbol, Text] = Field(min_length=1)
    variants: list[Variant] = []
    properties: ReductionProperties | None = None
    formal: Formal = Formal()
    source: Source
    status: ResultStatus = "valid"
    review: Review = Review()

    @model_validator(mode="after")
    def _call_sizes_for_turing(self) -> Reduction:
        if self.call_sizes is not None and self.calls == 1:
            raise ValueError("call_sizes only applies to reductions with several calls")
        ids = [v.id for v in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("variant ids must be unique within a reduction")
        return self


class StatusSource(Model):
    paper: Id | None = None
    version: Id | None = None
    statement: Text | None = None
    url: Text | None = None
    date: dt.date

    @model_validator(mode="after")
    def _where(self) -> StatusSource:
        if self.paper is None and self.url is None:
            raise ValueError("a status source needs a paper or a url")
        if self.version is not None and self.paper is None:
            raise ValueError("version given without paper")
        return self


class Hypothesis(Model):
    id: Id
    name: Text
    short: Text | None = None
    statement: Text
    status: Literal["open", "claimed-refuted", "refuted"] = "open"
    status_sources: list[StatusSource] = []
    implies: list[Id] = []
    review: Review = Review()

    @model_validator(mode="after")
    def _sourced_status(self) -> Hypothesis:
        if self.status != "open" and not self.status_sources:
            raise ValueError(f"status '{self.status}' needs at least one status source")
        return self


class ConstantBound(Model):
    """One bound on a named constant, e.g. ω ≤ 9/4."""

    relation: Literal["le", "ge"]
    value: Text  # a number in the bound language, e.g. "9/4" or "2.371339"
    status: Literal["established", "claimed", "refuted"] = "established"
    sources: list[Source] = Field(min_length=1)


class NamedConstant(Model):
    """A constant such as ω that bounds may use symbolically (bounds §2)."""

    id: Id
    name: Text
    symbol: Text  # the TeX command, e.g. "\\omega"
    definition: Text
    definition_source: Source | None = None
    bounds: list[ConstantBound] = Field(min_length=1)
    review: Review = Review()


class LowerBound(Model):
    id: Id
    problem: Id
    version: Id
    bound: Bound
    conditional_on: list[Id] = []
    source: Source
    status: ResultStatus = "valid"
    review: Review = Review()


ENTITY_TYPES: dict[str, type[Model]] = {
    "problems": Problem,
    "parameters": SharedParameter,
    "papers": Paper,
    "algorithms": Algorithm,
    "reductions": Reduction,
    "hypotheses": Hypothesis,
    "lower-bounds": LowerBound,
    "constants": NamedConstant,
}
