"""Guard the Transcribe custom-vocabulary phrases against the format rules.

Transcribe inline vocabulary phrases must be letters (and digits) joined by
single hyphens, no spaces. A malformed phrase makes create_vocabulary fail, so
catch it here instead of at deploy time.
"""

from __future__ import annotations

import re

from backend.aws.transcribe import FINANCIAL_VOCAB_PHRASES, FINANCIAL_VOCAB_NAME

_PHRASE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")


def test_vocab_name_is_set():
    assert FINANCIAL_VOCAB_NAME


def test_phrases_are_nonempty_and_unique():
    assert FINANCIAL_VOCAB_PHRASES
    assert len(FINANCIAL_VOCAB_PHRASES) == len(set(FINANCIAL_VOCAB_PHRASES))


def test_every_phrase_is_well_formed():
    bad = [p for p in FINANCIAL_VOCAB_PHRASES if not _PHRASE.fullmatch(p)]
    assert not bad, f"malformed Transcribe phrases: {bad}"
