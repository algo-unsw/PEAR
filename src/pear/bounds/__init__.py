"""The bound expression language (docs/specs/bounds.md)."""

from .compare import Context, Relation, best, build_context, compare
from .display import Display, display, fold, ostar, ostar_tex, substitute, substitute_bound
from .expr import Bound, BoundSyntaxError, parse_bound, parse_expr, render, render_bound
from .growth import UnsupportedBound, is_monotone

__all__ = [
    "Bound",
    "BoundSyntaxError",
    "Context",
    "Relation",
    "UnsupportedBound",
    "best",
    "build_context",
    "compare",
    "Display",
    "display",
    "fold",
    "is_monotone",
    "ostar",
    "ostar_tex",
    "parse_bound",
    "parse_expr",
    "render",
    "render_bound",
    "substitute",
    "substitute_bound",
]
