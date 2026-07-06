"""Deterministic Unicode-block language confirmation for Hindi and Bengali."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..flags import FLAG_LANG_AMBIGUOUS, FLAG_NO_INDIC_SCRIPT

DetectedLang = Literal["hi", "bn", "ambiguous", "unknown"]

DEVANAGARI_START = 0x0900
DEVANAGARI_END = 0x097F
BENGALI_START = 0x0980
BENGALI_END = 0x09FF
DOMINANCE_THRESHOLD = 0.70


@dataclass(slots=True)
class ScriptDetectionResult:
    detected_lang: DetectedLang
    devanagari_count: int
    bengali_count: int
    other_letter_count: int
    confidence: float
    flags: list[str] = field(default_factory=list)


def detect_script_language(text: str) -> ScriptDetectionResult:
    devanagari_count = 0
    bengali_count = 0
    other_letter_count = 0

    for char in text:
        codepoint = ord(char)
        if DEVANAGARI_START <= codepoint <= DEVANAGARI_END:
            devanagari_count += 1
        elif BENGALI_START <= codepoint <= BENGALI_END:
            bengali_count += 1
        elif char.isalpha():
            other_letter_count += 1

    indic_total = devanagari_count + bengali_count
    if indic_total == 0:
        return ScriptDetectionResult(
            detected_lang="unknown",
            devanagari_count=devanagari_count,
            bengali_count=bengali_count,
            other_letter_count=other_letter_count,
            confidence=0.0,
            flags=[FLAG_NO_INDIC_SCRIPT],
        )

    if devanagari_count == 0:
        return ScriptDetectionResult(
            detected_lang="bn",
            devanagari_count=devanagari_count,
            bengali_count=bengali_count,
            other_letter_count=other_letter_count,
            confidence=1.0,
            flags=[],
        )

    if bengali_count == 0:
        return ScriptDetectionResult(
            detected_lang="hi",
            devanagari_count=devanagari_count,
            bengali_count=bengali_count,
            other_letter_count=other_letter_count,
            confidence=1.0,
            flags=[],
        )

    devanagari_ratio = devanagari_count / indic_total
    bengali_ratio = bengali_count / indic_total
    dominant_ratio = max(devanagari_ratio, bengali_ratio)

    if devanagari_ratio >= DOMINANCE_THRESHOLD:
        return ScriptDetectionResult(
            detected_lang="hi",
            devanagari_count=devanagari_count,
            bengali_count=bengali_count,
            other_letter_count=other_letter_count,
            confidence=round(devanagari_ratio, 4),
            flags=[],
        )

    if bengali_ratio >= DOMINANCE_THRESHOLD:
        return ScriptDetectionResult(
            detected_lang="bn",
            devanagari_count=devanagari_count,
            bengali_count=bengali_count,
            other_letter_count=other_letter_count,
            confidence=round(bengali_ratio, 4),
            flags=[],
        )

    return ScriptDetectionResult(
        detected_lang="ambiguous",
        devanagari_count=devanagari_count,
        bengali_count=bengali_count,
        other_letter_count=other_letter_count,
        confidence=round(dominant_ratio, 4),
        flags=[FLAG_LANG_AMBIGUOUS],
    )
