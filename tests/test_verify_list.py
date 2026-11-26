"""docs/to-verify.md must match the data (Serge, 22 November 2026: keep a record of what
needs to be read or verified). Regenerate with `python -m pear verify-list`."""

from pathlib import Path

from pear.verify_list import build_list

ROOT = Path(__file__).resolve().parents[1]


def test_verify_list_is_current():
    committed = (ROOT / "docs" / "to-verify.md").read_text(encoding="utf-8")
    assert committed == build_list(ROOT / "data"), "run: python -m pear verify-list"


def test_abstract_records_are_listed():
    text = build_list(ROOT / "data")
    assert "`bandwidth--n--cygan-pilipczuk-2009-approximate-journal` | abstract" in text
    # read on 27 November 2026 (Pass arXiv v2; Alman et al. arXiv v3), so no longer listed
    assert "`omega`" not in text
    # read in full on 27 November 2026, so no longer listed
    assert "`exact-satisfiability--m--bjorklund-husfeldt-2006` | abstract" not in text
    assert "`directed-feedback-vertex-set--n--razgon-2007` | title" in text
