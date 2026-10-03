"""Deterministic text rules used as guardrails around the language model.

Nothing here replaces the model's interpretation. These rules only add
flags, detect reserved signals, and extract amounts so the backend can
compare a confirmed request with the client's own words.
"""

from __future__ import annotations

import re

# Phrases that indicate possible fraud, unauthorized access, or account takeover.
SECURITY_PATTERNS: tuple[str, ...] = (
    r"\bfraud\w*\b",
    r"\bunauthori[sz]ed\b",
    r"\bhack\w*\b",
    r"\bstolen\b",
    r"\bsteal\w*\b",
    r"\bscam\w*\b",
    r"\bphish\w*\b",
    r"\bidentity theft\b",
    r"\baccount take ?over\b",
    r"\btook over my account\b",
    r"\bsomeone (?:else )?(?:moved|took|transferred|withdrew|logged|got into|accessed|changed)\b",
    r"\bi did(?:n't| not) (?:make|do|authorize|approve|request)\b",
    r"\bdid(?:n't| not) recogni[sz]e\b",
    r"\bnot me\b",
    r"\bwasn't me\b",
    r"\bsuspicious\b",
    r"\bpassword (?:was )?changed\b",
    r"\blocked out\b",
    r"\bcompromised\b",
)

# Account type vocabulary the client might use, mapped to canonical account types.
ACCOUNT_TERM_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\broth\b", "roth_ira"),
    (r"\brollover\b", "rollover_ira"),
    (r"\brolled over\b", "rollover_ira"),
    (r"\btraditional ira\b", "traditional_ira"),
    (r"\bjoint\b", "joint_brokerage"),
    (r"\bbrokerage\b", "brokerage"),
    (r"\btrust\b", "trust"),
)

# Phrases that hint at a former-employer retirement plan (rollover IRA).
FORMER_EMPLOYER_PATTERNS: tuple[str, ...] = (
    r"\bold job\b",
    r"\bformer employer\b",
    r"\bprevious employer\b",
    r"\bold employer\b",
    r"\bfrom work\b",
    r"\bwork plan\b",
    r"\b401\s*\(?k\)?\b",
    r"\b403\s*\(?b\)?\b",
    r"\bpension\b",
    r"\bwhere i used to work\b",
    r"\bwhen i worked at\b",
)

ACCOUNT_TYPE_LABELS: dict[str, str] = {
    "roth_ira": "Roth IRA",
    "rollover_ira": "rollover IRA",
    "traditional_ira": "traditional IRA",
    "brokerage": "brokerage account",
    "joint_brokerage": "joint brokerage account",
    "trust": "trust account",
}

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALE_WORDS = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}

_DIGIT_AMOUNT = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(k|thousand|million|m)?\b|\b(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(k|thousand|million)?\s*(?:dollars|bucks)\b", re.I)
_WORD_AMOUNT = re.compile(
    r"\b((?:(?:" + "|".join(_NUMBER_WORDS) + r"|hundred|thousand|million|and|-|\s)+))\s*(?:dollars|bucks)\b",
    re.I,
)


def detect_security_concern(text: str) -> list[str]:
    """Return the matched security phrases (empty when none)."""
    lowered = (text or "").lower()
    hits: list[str] = []
    for pattern in SECURITY_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            hits.append(match.group(0))
    return hits


def mentioned_account_types(text: str) -> list[str]:
    """Return canonical account types the client named explicitly."""
    lowered = (text or "").lower()
    found: list[str] = []
    for pattern, account_type in ACCOUNT_TERM_PATTERNS:
        if re.search(pattern, lowered) and account_type not in found:
            found.append(account_type)
    return found


def mentions_former_employer(text: str) -> bool:
    lowered = (text or "").lower()
    return any(re.search(p, lowered) for p in FORMER_EMPLOYER_PATTERNS)


def _words_to_number(phrase: str) -> int | None:
    tokens = re.split(r"[\s-]+", phrase.strip().lower())
    total = 0
    current = 0
    seen = False
    for token in tokens:
        if not token or token == "and":
            continue
        if token in _NUMBER_WORDS:
            current += _NUMBER_WORDS[token]
            seen = True
        elif token in _SCALE_WORDS:
            scale = _SCALE_WORDS[token]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            seen = True
        else:
            return None
    if not seen:
        return None
    return total + current


def extract_amounts(text: str) -> list[float]:
    """Extract dollar amounts stated in digits or words. Deterministic only."""
    amounts: list[float] = []
    for match in _DIGIT_AMOUNT.finditer(text or ""):
        whole = match.group(1) or match.group(4)
        cents = match.group(2) or match.group(5)
        scale = (match.group(3) or match.group(6) or "").lower()
        if not whole:
            continue
        value = float(whole.replace(",", ""))
        if cents:
            value += float(f"0.{cents}")
        if scale in {"k", "thousand"}:
            value *= 1_000
        elif scale in {"m", "million"}:
            value *= 1_000_000
        amounts.append(value)
    for match in _WORD_AMOUNT.finditer(text or ""):
        value = _words_to_number(match.group(1))
        if value:
            amounts.append(float(value))
    # de-duplicate while preserving order
    unique: list[float] = []
    for value in amounts:
        if value not in unique:
            unique.append(value)
    return unique


def amount_matches_text(amount: float, text: str) -> bool:
    return any(abs(found - amount) < 0.005 for found in extract_amounts(text))


def slugify_flag(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return slug[:64]
