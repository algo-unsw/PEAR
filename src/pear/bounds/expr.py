"""Bound expressions: AST, parser for the TeX subset, and natural-form renderer.

Spec: docs/specs/bounds.md §1. The parser needs the problem's symbols, because
TeX writes products by juxtaposition: with symbols {k, n, tw}, "kn" is k·n and
"tw" is treewidth (longest match wins).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Union


class BoundSyntaxError(ValueError):
    pass


# --- AST ---------------------------------------------------------------------


@dataclass(frozen=True)
class Num:
    value: Fraction
    text: str  # as written, e.g. "1.2738"


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Const:
    name: str  # varepsilon | omega | delta


@dataclass(frozen=True)
class Add:
    terms: tuple[tuple[int, "Node"], ...]  # (sign, term), sign is +1 or -1


@dataclass(frozen=True)
class Mul:
    factors: tuple["Node", ...]


@dataclass(frozen=True)
class Div:
    num: "Node"
    den: "Node"


@dataclass(frozen=True)
class Pow:
    base: "Node"
    exp: "Node"


@dataclass(frozen=True)
class Sqrt:
    arg: "Node"


@dataclass(frozen=True)
class Log:
    arg: "Node"
    power: "Node | None" = None  # \log^{p} x
    base: "Node | None" = None  # \log_{b} x; default base 2


@dataclass(frozen=True)
class Asym:
    kind: str  # "O" or "o"
    arg: "Node"


@dataclass(frozen=True)
class Func:
    """An unspecified computable function such as f(k) (bounds B3)."""

    name: str
    arg: "Node"


@dataclass(frozen=True)
class Poly:
    """\\mathrm{poly}(x): some polynomial in x."""

    arg: "Node"


Node = Union[Num, Var, Const, Add, Mul, Div, Pow, Sqrt, Log, Asym, Func, Poly]

NOTATIONS = ("O", "O*", "Õ")


@dataclass(frozen=True)
class Bound:
    notation: str | None  # one of NOTATIONS, or None when no outer notation is written
    expr: Node
    family: bool = False  # "\text{ for every } \delta > 0"


def variables(node: Node) -> set[str]:
    if isinstance(node, Var):
        return {node.name}
    out: set[str] = set()
    for child in children(node):
        out |= variables(child)
    return out


def children(node: Node) -> Iterable[Node]:
    if isinstance(node, Add):
        return [t for _, t in node.terms]
    if isinstance(node, Mul):
        return node.factors
    if isinstance(node, Div):
        return [node.num, node.den]
    if isinstance(node, Pow):
        return [node.base, node.exp]
    if isinstance(node, Log):
        return [n for n in (node.arg, node.power, node.base) if n is not None]
    if isinstance(node, (Sqrt, Asym, Func, Poly)):
        return [node.arg]
    return []


def constants(node: Node) -> set[str]:
    if isinstance(node, Const):
        return {node.name}
    out: set[str] = set()
    for child in children(node):
        out |= constants(child)
    return out


def num(value: Fraction | int | str) -> Num:
    v = Fraction(value)
    return Num(v, format_number(v))


def format_number(v: Fraction) -> str:
    if v.denominator == 1:
        return str(v.numerator)
    text = f"{float(v):.10f}".rstrip("0").rstrip(".")
    if Fraction(text) == v:
        return text
    return f"\\frac{{{v.numerator}}}{{{v.denominator}}}"


# --- tokenizer ---------------------------------------------------------------

_TOKEN = re.compile(
    r"""(?P<space>\s+|\\[,;!:\ ])
      | (?P<named>\\(?:mathrm|mathit|operatorname)\{[A-Za-z]+\})
      | (?P<cmd>\\[A-Za-z]+|\\\{|\\\})
      | (?P<num>\d+(?:\.\d+)?|\.\d+)
      | (?P<letter>[A-Za-z])
      | (?P<sym>[{}()^_+\-*/|])""",
    re.VERBOSE,
)

_FAMILY = re.compile(r"\\text\{\s*for every\s*\}\s*\\delta\s*>\s*0\s*$")
_IGNORED_CMDS = {"\\cdot", "\\times", "\\left", "\\right", "\\big", "\\Big", "\\bigl", "\\bigr"}
_CONST_CMDS = {"\\varepsilon": "varepsilon", "\\epsilon": "varepsilon", "\\omega": "omega", "\\delta": "delta"}


@dataclass
class _Tok:
    kind: str
    text: str


def _tokenize(src: str, symbols: frozenset[str]) -> list[_Tok]:
    raw: list[_Tok] = []
    pos = 0
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise BoundSyntaxError(f"unexpected character {src[pos]!r} at position {pos}")
        pos = m.end()
        kind = m.lastgroup
        assert kind is not None
        text = m.group()
        if kind == "space":
            raw.append(_Tok("space", text))
        elif kind == "named":
            raw.append(_Tok("named", text[text.index("{") + 1 : -1]))
        elif kind == "cmd" and text in ("\\left", "\\right"):
            continue  # \left( and \right) are plain brackets
        elif kind == "cmd" and text in _IGNORED_CMDS:
            raw.append(_Tok("times", text))
        else:
            raw.append(_Tok(kind, text))
    # Merge runs of letters into symbols, longest match first.
    out: list[_Tok] = []
    i = 0
    while i < len(raw):
        if raw[i].kind != "letter":
            if raw[i].kind != "space":
                out.append(raw[i])
            i += 1
            continue
        j = i
        while j < len(raw) and raw[j].kind == "letter":
            j += 1
        word = "".join(t.text for t in raw[i:j])
        sub, after = _subscript(raw, j)
        base = next((s.split("_", 1)[0] for s in sorted(symbols, key=len, reverse=True)
                     if sub and s == f"{s.split('_', 1)[0]}_{sub}" and word.endswith(s.split("_", 1)[0])), None)
        if base is not None:
            # a subscripted symbol such as tw_p (primal treewidth), written tw_p or tw_{p}
            if len(word) > len(base):
                out.extend(_split_word(word[: -len(base)], symbols))
            out.append(_Tok("var", f"{base}_{sub}"))
            i = after
            continue
        out.extend(_split_word(word, symbols))
        i = j
    return out


def _subscript(raw: list[_Tok], j: int) -> tuple[str | None, int]:
    """The letters of a subscript starting at raw[j] ('_p' or '_{pd}'), and the index after it."""
    if j >= len(raw) or raw[j].kind != "sym" or raw[j].text != "_":
        return None, j
    k = j + 1
    if k < len(raw) and raw[k].kind == "letter":
        return raw[k].text, k + 1
    if k < len(raw) and raw[k].kind == "sym" and raw[k].text == "{":
        m = k + 1
        letters = []
        while m < len(raw) and raw[m].kind == "letter":
            letters.append(raw[m].text)
            m += 1
        if letters and m < len(raw) and raw[m].kind == "sym" and raw[m].text == "}":
            return "".join(letters), m + 1
    return None, j


_RESERVED = {"O", "o", "f", "g"}


def _split_word(word: str, symbols: frozenset[str]) -> list[_Tok]:
    out: list[_Tok] = []
    pos = 0
    while pos < len(word):
        for size in range(len(word) - pos, 0, -1):
            piece = word[pos : pos + size]
            if piece in symbols:
                out.append(_Tok("var", piece))
                pos += size
                break
        else:
            ch = word[pos]
            if ch in _RESERVED:
                out.append(_Tok("letter", ch))
                pos += 1
            else:
                raise BoundSyntaxError(f"unknown variable {word[pos:]!r} (not defined by the problem)")
    return out


# --- parser ------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[_Tok]):
        self.toks = tokens
        self.i = 0

    def peek(self, offset: int = 0) -> _Tok | None:
        j = self.i + offset
        return self.toks[j] if j < len(self.toks) else None

    def take(self) -> _Tok:
        tok = self.peek()
        if tok is None:
            raise BoundSyntaxError("unexpected end of expression")
        self.i += 1
        return tok

    def expect(self, text: str) -> None:
        tok = self.take()
        if tok.text != text:
            raise BoundSyntaxError(f"expected {text!r}, found {tok.text!r}")

    def at(self, text: str) -> bool:
        tok = self.peek()
        return tok is not None and tok.text == text

    # sum := ['-'] term {('+'|'-') term}
    def sum(self) -> Node:
        terms: list[tuple[int, Node]] = []
        sign = 1
        if self.at("-"):
            self.take()
            sign = -1
        elif self.at("+"):
            self.take()
        terms.append((sign, self.term()))
        while self.at("+") or self.at("-"):
            sign = 1 if self.take().text == "+" else -1
            terms.append((sign, self.term()))
        if len(terms) == 1 and terms[0][0] == 1:
            return terms[0][1]
        return Add(tuple(terms))

    # term := factor { ['\cdot'] factor | '/' factor }
    def term(self) -> Node:
        factors: list[Node] = [self.factor()]
        while True:
            tok = self.peek()
            if tok is None or tok.text in ("+", "-", ")", "}", "|"):
                break
            if tok.kind == "times":
                self.take()
                continue
            if tok.text == "/":
                self.take()
                den = self.factor()
                num_ = factors.pop() if len(factors) == 1 else Mul(tuple(factors))
                factors = [Div(num_, den)]
                continue
            factors.append(self.factor())
        return factors[0] if len(factors) == 1 else Mul(tuple(factors))

    # factor := primary ['^' exponent]
    def factor(self) -> Node:
        base = self.primary()
        if self.at("^"):
            self.take()
            base = Pow(base, self.exponent())
        return base

    def exponent(self) -> Node:
        if self.at("{"):
            self.take()
            e = self.sum()
            self.expect("}")
            return e
        tok = self.peek()
        if tok is not None and tok.kind == "num" and len(tok.text) > 1:
            raise BoundSyntaxError(f"write ^{{{tok.text}}} with braces")
        return self.primary()

    def group(self, open_: str, close: str) -> Node:
        self.expect(open_)
        e = self.sum()
        self.expect(close)
        return e

    def primary(self) -> Node:
        tok = self.take()
        if tok.kind == "num":
            return Num(Fraction(tok.text), tok.text)
        if tok.kind == "var":
            return Var(tok.text)
        if tok.text == "(":
            e = self.sum()
            self.expect(")")
            return e
        if tok.text == "{":
            e = self.sum()
            self.expect("}")
            return e
        if tok.kind == "letter" and tok.text in ("O", "o") and self.at("("):
            return Asym(tok.text, self.group("(", ")"))
        if tok.kind == "letter" and tok.text in ("f", "g") and self.at("("):
            return Func(tok.text, self.group("(", ")"))
        if tok.kind == "named":
            if tok.text == "poly":
                return Poly(self.group("(", ")"))
            return Var(tok.text)
        if tok.kind == "cmd":
            return self.command(tok.text)
        raise BoundSyntaxError(f"unexpected {tok.text!r}")

    def command(self, cmd: str) -> Node:
        if cmd in _CONST_CMDS:
            return Const(_CONST_CMDS[cmd])
        if cmd == "\\sqrt":
            return Sqrt(self.group("{", "}"))
        if cmd == "\\frac":
            a = self.group("{", "}")
            b = self.group("{", "}")
            return Div(a, b)
        if cmd in ("\\log", "\\lg", "\\ln"):
            power: Node | None = None
            base: Node | None = Const("e") if cmd == "\\ln" else None  # None: base 2
            if self.at("_"):
                self.take()
                base = self.exponent()
            if self.at("^"):
                self.take()
                power = self.exponent()
            return Log(self.factor(), power, base)
        raise BoundSyntaxError(f"unsupported command {cmd}")


def parse_expr(src: str, symbols: Iterable[str]) -> Node:
    """Parse an expression with no outer notation, e.g. a parameter-map value."""
    toks = _tokenize(src.strip(), frozenset(symbols))
    p = _Parser(toks)
    e = p.sum()
    if p.peek() is not None:
        raise BoundSyntaxError(f"unexpected {p.peek().text!r}")  # type: ignore[union-attr]
    _check_vars(e, frozenset(symbols))
    return e


def _check_vars(node: Node, symbols: frozenset[str]) -> None:
    unknown = variables(node) - symbols
    if unknown:
        raise BoundSyntaxError(f"unknown variable(s) {sorted(unknown)} (not defined by the problem)")


def parse_bound(src: str, symbols: Iterable[str]) -> Bound:
    """Parse a bound as stated, e.g. 'O(1.5^{k} + kn)' or 'n^{O(k)}'."""
    syms = frozenset(symbols)
    text = src.strip()
    family = False
    m = _FAMILY.search(text)
    if m:
        family = True
        text = text[: m.start()].rstrip()
    toks = _tokenize(text, syms)
    notation, body = _split_notation(toks)
    p = _Parser(body)
    e = p.sum()
    if p.peek() is not None:
        raise BoundSyntaxError(f"unexpected {p.peek().text!r}")  # type: ignore[union-attr]
    _check_vars(e, syms)
    if family and "delta" not in constants(e):
        raise BoundSyntaxError("'for every δ > 0' needs δ in the bound")
    if not family and "delta" in constants(e):
        raise BoundSyntaxError("δ used without '\\text{ for every } \\delta > 0'")
    return Bound(notation, e, family)


def _split_notation(toks: list[_Tok]) -> tuple[str | None, list[_Tok]]:
    """If the whole bound is wrapped in O(...), O^*(...) or \\tilde{O}(...), unwrap it."""
    i = 0
    notation: str | None = None
    if len(toks) >= 2 and toks[0].text == "O" and toks[0].kind == "letter":
        if toks[1].text == "(":
            notation, i = "O", 1
        elif toks[1].text == "^" and len(toks) >= 4:
            if toks[2].text == "*":
                notation, i = "O*", 3
            elif toks[2].text == "{" and toks[3].text == "*" and len(toks) >= 5 and toks[4].text == "}":
                notation, i = "O*", 5
    elif toks and toks[0].text in ("\\tilde", "\\widetilde") and len(toks) >= 4:
        if toks[1].text == "{" and toks[2].text == "O" and toks[3].text == "}":
            notation, i = "Õ", 4
    if notation is None or i >= len(toks) or toks[i].text != "(":
        return None, toks
    depth = 0
    for j in range(i, len(toks)):
        if toks[j].text == "(":
            depth += 1
        elif toks[j].text == ")":
            depth -= 1
            if depth == 0:
                if j == len(toks) - 1:
                    return notation, toks[i + 1 : j]
                return None, toks  # e.g. O(1) \cdot 2^n: not an outer notation
    raise BoundSyntaxError("unbalanced parentheses")


# --- renderer (natural form, TeX) ---------------------------------------------

_PREC_ADD, _PREC_MUL, _PREC_POW, _PREC_ATOM = 1, 2, 3, 4


def render(node: Node) -> str:
    return _render(node)


def render_bound(b: Bound) -> str:
    body = _render(b.expr)
    head = {"O": "O", "O*": "O^*", "Õ": "\\tilde{O}"}.get(b.notation or "", "")
    out = f"{head}({body})" if head else body
    return out + (" \\text{ for every } \\delta > 0" if b.family else "")


def _prec(node: Node) -> int:
    if isinstance(node, Add):
        return _PREC_ADD
    if isinstance(node, (Mul, Div)):
        return _PREC_MUL
    if isinstance(node, Pow):
        return _PREC_POW
    if isinstance(node, Num) and node.value < 0:
        return _PREC_ADD
    return _PREC_ATOM


def _wrap(node: Node, min_prec: int) -> str:
    s = _render(node)
    return f"({s})" if _prec(node) < min_prec else s


def _starts_with_digit(node: Node) -> bool:
    while isinstance(node, (Pow, Mul, Div)):
        node = node.base if isinstance(node, Pow) else node.factors[0] if isinstance(node, Mul) else node.num
    return isinstance(node, Num)


def _render(node: Node) -> str:
    if isinstance(node, Num):
        return node.text
    if isinstance(node, Var):
        base, _, sub = node.name.partition("_")
        tex = base if len(base) == 1 else f"\\mathit{{{base}}}"
        return f"{tex}_{{{sub}}}" if sub else tex
    if isinstance(node, Const):
        return "e" if node.name == "e" else f"\\{node.name}"
    if isinstance(node, Add):
        out = ""
        for k, (sign, term) in enumerate(node.terms):
            piece = _wrap(term, _PREC_MUL)
            if k == 0:
                out = ("-" if sign < 0 else "") + piece
            else:
                out += (" - " if sign < 0 else " + ") + piece
        return out
    if isinstance(node, Mul):
        parts = [_wrap(f, _PREC_MUL) for f in node.factors]
        out = parts[0]
        for prev, part, f in zip(node.factors, parts[1:], node.factors[1:]):
            # an explicit dot where juxtaposition would misread: before a digit, after a log
            sep = " \\cdot " if _starts_with_digit(f) or isinstance(prev, Log) else " "
            out += sep + part
        return out
    if isinstance(node, Div):
        return f"{_wrap(node.num, _PREC_MUL)}/{_wrap(node.den, _PREC_POW)}"
    if isinstance(node, Pow):
        return f"{_wrap(node.base, _PREC_ATOM)}^{{{_render(node.exp)}}}"
    if isinstance(node, Sqrt):
        return f"\\sqrt{{{_render(node.arg)}}}"
    if isinstance(node, Log):
        head = "\\ln" if isinstance(node.base, Const) and node.base.name == "e" else "\\log"
        if node.base is not None and not (isinstance(node.base, Const) and node.base.name == "e"):
            head += f"_{{{_render(node.base)}}}"
        if node.power is not None:
            head += f"^{{{_render(node.power)}}}"
        arg = node.arg
        inner = _render(arg)
        simple = isinstance(arg, (Var, Num)) or (isinstance(arg, Log))
        return f"{head} {inner}" if simple else f"{head}({inner})"
    if isinstance(node, Asym):
        return f"{node.kind}({_render(node.arg)})"
    if isinstance(node, Func):
        return f"{node.name}({_render(node.arg)})"
    if isinstance(node, Poly):
        return f"\\mathrm{{poly}}({_render(node.arg)})"
    raise TypeError(node)
