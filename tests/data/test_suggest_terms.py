"""Grounded term-normalization: fragments/acronyms/phonetics map to approved terms."""

from __future__ import annotations

import pytest

from data.store import Store

STORE = Store()


def _top(fragment: str) -> str | None:
    hits = STORE.suggest_terms(fragment)
    return hits[0]["term"] if hits else None


@pytest.mark.parametrize("fragment,expected", [
    ("roi", "return on investment"),
    ("R O I", "return on investment"),
    ("rmd", "required minimum distribution"),
    ("r m d", "required minimum distribution"),
    ("roth", "Roth IRA"),
    ("the roth thing", "Roth IRA"),
    ("401k", "401(k)"),
    ("four oh one k", "401(k)"),
    ("tax form", "1099-R"),
    ("rollover", "rollover IRA"),
    ("my statement", "account statement"),
])
def test_fragment_maps_to_expected_term(fragment, expected):
    assert _top(fragment) == expected, f"{fragment!r} -> {STORE.suggest_terms(fragment)}"


def test_candidates_are_grounded_in_glossary():
    approved = {g["term"] for g in STORE.data["glossary"]}
    for hit in STORE.suggest_terms("r o"):
        assert hit["term"] in approved
        assert hit["plain"]


def test_empty_fragment_returns_nothing():
    assert STORE.suggest_terms("") == []
    assert STORE.suggest_terms("   ") == []


def test_ambiguous_fragment_offers_multiple():
    # "r" alone or a vague retirement word should surface several options to confirm.
    hits = STORE.suggest_terms("retirement")
    assert len(hits) >= 2
