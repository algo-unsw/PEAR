"""Prominence of a problem: how widely it is studied, used to order problems on the front page
and on the category pages (requested by Serge Gaspers, 21 November 2026).

The score combines five groups of signals. Each raw count is turned into a percentile rank among
PEAR's problems, so heavy-tailed counts from very different sources become comparable and one
inflated count (an ambiguous search phrase, say) moves a problem by at most one group's weight:

    group           weight  signals (raw counts, mean of their percentile ranks)
    scholarly        0.30   OpenAlex works whose title or abstract contains the phrase
    books            0.20   books whose full text contains the phrase (Open Library search
                            inside, Google Books)
    wikipedia        0.20   page views of the problem's own English Wikipedia article over the last
                            12 full months; English Wikipedia articles mentioning the phrase
    pear             0.20   results and reductions in PEAR involving the problem
    web              0.10   Stack Exchange questions containing the phrase (cs, cstheory, math,
                            MathOverflow), a proxy for web hit counts: no free web search API
                            reports hit counts (Google's Custom Search JSON API is closed to new
                            customers and ends on 1 January 2027)

    score = 100 * sum_g w_g * p_g / sum_g w_g, summed over the groups with data for the problem,
    where p_g is the mean of the group's available percentile ranks.

Percentile rank of a count x among the problems with that count known: 0 when x = 0, otherwise
(#smaller + (#equal - 1)/2) / (#known - 1), so the most studied problem gets 1.

External counts change slowly and the build must not depend on the network, so they are fetched
by `python -m pear prominence fetch` (monthly on GitHub Actions) into prominence/signals.yaml;
the PEAR count is computed from the data at build time.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

import yaml

from .validate import Dataset

GROUPS: dict[str, tuple[float, list[str]]] = {
    "scholarly": (0.30, ["openalex_works"]),
    "books": (0.20, ["openlibrary_books", "google_books"]),
    "wikipedia": (0.20, ["wikipedia_pageviews", "wikipedia_mentions"]),
    "pear": (0.20, ["pear_entries"]),
    "web": (0.10, ["stackexchange_questions"]),
}

SIGNAL_LABELS = {
    "openalex_works": "OpenAlex works (title or abstract)",
    "openlibrary_books": "Books, full text (Open Library)",
    "google_books": "Books, full text (Google Books)",
    "wikipedia_pageviews": "Wikipedia page views, last 12 months",
    "wikipedia_mentions": "Wikipedia articles mentioning it",
    "pear_entries": "Results and reductions in PEAR",
    "stackexchange_questions": "Stack Exchange questions",
}

GROUP_LABELS = {"scholarly": "Scholarly articles", "books": "Books", "wikipedia": "Wikipedia",
                "pear": "PEAR entries", "web": "Web (Stack Exchange)"}

STACKEXCHANGE_SITES = ["cs", "cstheory", "math", "mathoverflow.net"]

SPELLINGS = [("Coloring", "Colouring"), ("Colorability", "Colourability"), ("Traveling", "Travelling")]


# --- scoring ---------------------------------------------------------------------------------


def percentile_ranks(values: dict[str, float | None]) -> dict[str, float | None]:
    """Percentile rank of each known value among the known values (module docstring)."""
    known = sorted(v for v in values.values() if v is not None)
    ranks: dict[str, float | None] = {}
    for key, v in values.items():
        if v is None:
            ranks[key] = None
        elif v <= 0:
            ranks[key] = 0.0
        elif len(known) == 1:
            ranks[key] = 1.0
        else:
            smaller = sum(1 for x in known if x < v)
            equal = sum(1 for x in known if x == v)
            ranks[key] = (smaller + (equal - 1) / 2) / (len(known) - 1)
    return ranks


def pear_entries(data: Dataset) -> dict[str, int]:
    """Results (algorithms) on the problem plus reductions from or to it, variants included."""
    counts = {pid: 0 for pid in data.problems}
    for alg in data.entries["algorithms"].values():
        if alg.problem in counts:  # type: ignore[attr-defined]
            counts[alg.problem] += 1  # type: ignore[attr-defined]
    for red in data.entries["reductions"].values():
        ends = {red.from_.problem, red.to.problem}  # type: ignore[attr-defined]
        for var in red.variants:  # type: ignore[attr-defined]
            ends |= {v.problem for v in (var.from_, var.to) if v is not None}
        for pid in ends:
            if pid in counts:
                counts[pid] += 1
    return counts


def scores(data: Dataset, signals: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """{problem id: {"score", "groups": {group: rank or None}, "signals": {signal: raw}}}."""
    fetched = (signals or {}).get("problems", {}) or {}
    raw: dict[str, dict[str, float | None]] = {}
    entries = pear_entries(data)
    for pid in data.problems:
        row = fetched.get(pid, {}) or {}
        raw[pid] = {s: row.get(s) for _, (_, sigs) in GROUPS.items() for s in sigs}
        raw[pid]["pear_entries"] = entries[pid]
    ranks = {s: percentile_ranks({pid: raw[pid][s] for pid in raw})
             for _, (_, sigs) in GROUPS.items() for s in sigs}
    out: dict[str, dict[str, Any]] = {}
    for pid in data.problems:
        groups: dict[str, float | None] = {}
        total = weight = 0.0
        for g, (w, sigs) in GROUPS.items():
            got = [ranks[s][pid] for s in sigs if ranks[s][pid] is not None]
            groups[g] = sum(got) / len(got) if got else None  # type: ignore[arg-type]
            if groups[g] is not None:
                total += w * groups[g]  # type: ignore[operator]
                weight += w
        row = fetched.get(pid, {}) or {}
        out[pid] = {
            "score": round(100 * total / weight, 1) if weight else 0.0,
            "groups": {g: (round(100 * v, 1) if v is not None else None) for g, v in groups.items()},
            "signals": raw[pid],
            "phrases": row.get("phrases"),
            "wikipedia_title": row.get("wikipedia_title"),
            "wikipedia_section": row.get("wikipedia_section"),
            "complete": all(v is not None for v in groups.values()),
        }
    return out


def load_signals(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- fetching (network; run on GitHub Actions, not at build time) ---------------------------


USER_AGENT = "PEAR-prominence/1.0 (https://github.com/algo-unsw/pear)"


def phrases_for(name: str, override: dict[str, Any] | None) -> list[str]:
    """Search phrases: the override's, else the problem's name; both spellings of colour/travel."""
    base = list((override or {}).get("phrases") or [name])
    out: list[str] = []
    for p in base:
        for q in [p] + [p.replace(a, b) for a, b in SPELLINGS if a in p] + [p.replace(b, a) for a, b in SPELLINGS if b in p]:
            if q not in out:
                out.append(q)
    return out


class Fetcher:
    def __init__(self, delay: float = 0.3, opener: Callable[[str], Any] | None = None):
        self.delay = delay
        self.errors: list[str] = []
        self._open = opener or self._http
        self._se_quota_out = False

    @staticmethod
    def _http(url: str) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
        return json.loads(body)

    def get(self, url: str, tries: int = 3) -> Any:
        for attempt in range(tries):
            time.sleep(self.delay)
            try:
                return self._open(url)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt + 1 < tries:
                    time.sleep(5 * (attempt + 1))
                    continue
                self.errors.append(f"{exc.code} {url}")
                return None
            except Exception as exc:  # noqa: BLE001 (network errors of every kind become a gap)
                if attempt + 1 < tries:
                    time.sleep(3)
                    continue
                self.errors.append(f"{type(exc).__name__}: {exc} {url}")
                return None
        return None

    # each returns a count, or None when the source failed

    def openalex(self, phrase: str) -> int | None:
        q = urllib.parse.quote(f'title_and_abstract.search:"{phrase}"', safe=":")
        mailto = os.environ.get("OPENALEX_MAILTO")
        url = f"https://api.openalex.org/works?filter={q}&per-page=1" + (f"&mailto={urllib.parse.quote(mailto)}" if mailto else "")
        r = self.get(url)
        return None if r is None else int(r["meta"]["count"])

    def openlibrary(self, phrase: str) -> int | None:
        r = self.get("https://openlibrary.org/search/inside.json?" + urllib.parse.urlencode({"q": f'"{phrase}"'}))
        if r is None:
            return None
        if isinstance(r.get("num_found"), int):
            return r["num_found"]
        total = (r.get("hits") or {}).get("total")
        if isinstance(total, dict):
            total = total.get("value")
        if isinstance(total, int):
            return total
        self.errors.append(f"openlibrary: unexpected response keys {sorted(r)} for {phrase!r}")
        return None

    def google_books(self, phrase: str) -> int | None:
        params = {"q": f'"{phrase}"', "maxResults": 1}
        if os.environ.get("GOOGLE_BOOKS_API_KEY"):
            params["key"] = os.environ["GOOGLE_BOOKS_API_KEY"]
        r = self.get("https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(params))
        return None if r is None else int(r.get("totalItems", 0))

    def wikipedia_mentions(self, phrase: str) -> int | None:
        params = {"action": "query", "list": "search", "srsearch": f'"{phrase}"', "srwhat": "text",
                  "srinfo": "totalhits", "srlimit": 1, "format": "json"}
        r = self.get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))
        return None if r is None else int(r["query"]["searchinfo"]["totalhits"])

    def wikipedia_article(self, candidates: list[str]) -> tuple[str | None, str | None]:
        """The first candidate title that is (or redirects to) an article that is not a
        disambiguation page: (title whose views count, section if the redirect points into a
        section of another article). For a redirect to a section, the redirect's own views count."""
        for title in candidates:
            params = {"action": "query", "titles": title, "redirects": 1, "prop": "pageprops",
                      "ppprop": "disambiguation", "format": "json"}
            r = self.get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))
            if r is None:
                continue
            q = r.get("query", {})
            pages = list(q.get("pages", {}).values())
            if not pages or "missing" in pages[0] or pages[0].get("ns") != 0:
                continue
            if "disambiguation" in (pages[0].get("pageprops") or {}):
                continue
            redirect = (q.get("redirects") or [{}])[-1]
            if redirect.get("tofragment"):
                return redirect["from"], f"{redirect['to']}#{redirect['tofragment']}"
            return pages[0]["title"], None
        return None, None

    def wikipedia_pageviews(self, title: str, today: dt.date) -> int | None:
        end = today.replace(day=1) - dt.timedelta(days=1)  # last day of the previous month
        start = (end.replace(day=1) - dt.timedelta(days=335)).replace(day=1)
        art = urllib.parse.quote(title.replace(" ", "_"), safe="")
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
               f"{art}/monthly/{start:%Y%m%d}00/{end:%Y%m%d}00")
        r = self.get(url)
        return None if r is None else sum(int(i["views"]) for i in r.get("items", []))

    def stackexchange(self, phrase: str) -> int | None:
        if self._se_quota_out:
            return None
        total = 0
        for site in STACKEXCHANGE_SITES:
            params = {"q": f'"{phrase}"', "site": site, "filter": "total"}
            if os.environ.get("STACKEXCHANGE_KEY"):
                params["key"] = os.environ["STACKEXCHANGE_KEY"]
            r = self.get("https://api.stackexchange.com/2.3/search/advanced?" + urllib.parse.urlencode(params))
            if r is None:
                return None
            if r.get("backoff"):
                time.sleep(int(r["backoff"]))
            if r.get("quota_remaining") == 0:
                self._se_quota_out = True
            total += int(r.get("total", 0))
        return total


def wikipedia_candidates(name: str, phrases: list[str], override: dict[str, Any] | None) -> list[str]:
    def sentence(s: str) -> str:
        return s[:1] + s[1:].lower()
    out: list[str] = []
    if (override or {}).get("wikipedia"):
        out.append(override["wikipedia"])  # type: ignore[index]
    for p in [name] + phrases:
        for t in (p, sentence(p), f"{p} problem", f"{sentence(p)} problem"):
            if t not in out:
                out.append(t)
    return out


def best(values: list[int | None]) -> int | None:
    """Several phrases: the largest count (a lower bound on the union, never double counted)."""
    got = [v for v in values if v is not None]
    return max(got) if got else None


def fetch(data: Dataset, overrides: dict[str, Any], today: dt.date | None = None,
          fetcher: Fetcher | None = None, only: list[str] | None = None, log: Callable[[str], None] = print) -> dict[str, Any]:
    today = today or dt.date.today()
    f = fetcher or Fetcher()
    problems: dict[str, Any] = {}
    for pid in sorted(only or data.problems):
        prob = data.problems[pid]
        ov = (overrides or {}).get(pid)
        phrases = phrases_for(prob.name, ov)
        title, section = f.wikipedia_article(wikipedia_candidates(prob.name, phrases, ov))
        row = {
            "phrases": phrases,
            "wikipedia_title": title,
            "wikipedia_section": section,
            "openalex_works": best([f.openalex(p) for p in phrases]),
            "openlibrary_books": best([f.openlibrary(p) for p in phrases]),
            "google_books": best([f.google_books(p) for p in phrases]),
            "wikipedia_pageviews": f.wikipedia_pageviews(title, today) if title else 0,
            "wikipedia_mentions": best([f.wikipedia_mentions(p) for p in phrases]),
            "stackexchange_questions": best([f.stackexchange(p) for p in phrases]),
        }
        problems[pid] = row
        log(f"{pid}: " + ", ".join(f"{k}={v}" for k, v in row.items() if k != "phrases"))
    return {"as_of": today.isoformat(), "problems": problems, "errors": f.errors}


def write_signals(snapshot: dict[str, Any], path: Path) -> None:
    head = ("# Prominence signals, fetched by `python -m pear prominence fetch` (src/pear/prominence.py).\n"
            "# Generated: edit prominence/queries.yaml instead, then refetch.\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + yaml.safe_dump(snapshot, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


__all__ = ["GROUPS", "SIGNAL_LABELS", "GROUP_LABELS", "percentile_ranks", "pear_entries", "scores",
           "load_signals", "fetch", "write_signals", "phrases_for", "wikipedia_candidates", "Fetcher"]
