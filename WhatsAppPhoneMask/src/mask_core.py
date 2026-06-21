#!/usr/bin/env python3
"""
mask_core.py - Core phone number masking logic.
"""

from __future__ import annotations

import re
from typing import TextIO, Tuple

# A "candidate" span:
#   - optional leading '+' or a word-boundary '00' (international prefix)
#   - then a digit, then 5-20 more chars drawn from digits/space/./-/()
#   - then a final digit
#   - not glued onto a preceding/following digit, '/', '-', or ':' (which
#     would mean it's actually part of a date, time, or a bigger number)
CANDIDATE_RE = re.compile(
    r'(?<![\d./:-])'
    r'(\+|\b00)?'
    r'\(?\d[\d\s.\-()]{5,20}\d'
    r'(?![\d/]|:(?!\s))'
)


def _digit_count(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def mask_phone_numbers(
    text: str,
    min_digits: int = 7,
    max_digits: int = 15,
    require_plus: bool = True,
) -> Tuple[str, int]:
    """Mask phone numbers in `text`.

    Returns (masked_text, number_of_phone_numbers_masked).

    min_digits / max_digits: how many digits a candidate must contain to be
        treated as a phone number (default 7-15, the E.164 range).
    require_plus: if True (default), only mask candidates that start with
        '+' or '00' (international format) - safest, fewest false
        positives. Set False (the --loose CLI flag) to also mask bare
        digit groups like "(123) 456-7890" or "98450 12345", at the cost
        of a higher chance of catching non-phone numeric codes.
    """
    count = 0

    def _replace(m: re.Match) -> str:
        nonlocal count
        candidate = m.group(0)
        digits = _digit_count(candidate)

        if not (min_digits <= digits <= max_digits):
            return candidate  # wrong shape to be a phone number - leave it

        looks_international = candidate.startswith('+') or candidate.startswith('00')
        if require_plus and not looks_international:
            return candidate

        count += 1
        return ''.join('X' if ch.isdigit() else ch for ch in candidate)

    masked = CANDIDATE_RE.sub(_replace, text)
    return masked, count


def process_stream(infile: TextIO, outfile: TextIO, **mask_kwargs) -> int:
    """Mask line-by-line so memory use stays flat for huge files."""
    total = 0
    for line in infile:
        masked, n = mask_phone_numbers(line, **mask_kwargs)
        outfile.write(masked)
        total += n
    return total


# ---------------------------------------------------------------------------
# Self-test: covers the edge cases this script is meant to handle correctly.
# ---------------------------------------------------------------------------
SELF_TEST_CASES = [
    # (input, expected_output_with_default_settings)
    ("+91 98450 12345", "+XX XXXXX XXXXX"),
    ("+1-555-123-4567", "+X-XXX-XXX-XXXX"),
    ("+44 20 7946 0958", "+XX XX XXXX XXXX"),
    ("0091 98450 12345", "XXXX XXXXX XXXXX"),
    ("+919845012345", "+" + "X" * 12),  # no separators at all
    ("David [+91 98450 12345]: hi", "David [+XX XXXXX XXXXX]: hi"),
    ("21/06/2026, 09:05 - David: hi", "21/06/2026, 09:05 - David: hi"),  # untouched
    ("Total: 1,23,456 rupees", "Total: 1,23,456 rupees"),  # untouched (comma sep.)
    ("v2.1.3 release notes", "v2.1.3 release notes"),  # too short / not phone-shaped
    ("Two numbers: +91 98450 12345 and +91 99000 54321",
     "Two numbers: +XX XXXXX XXXXX and +XX XXXXX XXXXX"),
]


def run_selftest() -> bool:
    ok = True
    for text, expected in SELF_TEST_CASES:
        got, _ = mask_phone_numbers(text)
        status = "PASS" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"[{status}] {text!r}\n        -> {got!r}\n        expected {expected!r}")
    print("\nAll tests passed." if ok else "\nSome tests FAILED.")
    return ok
