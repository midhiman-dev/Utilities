"""Deterministic robustness guards for ASR output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .asr.whisper_engine import AsrOutput, AsrSegmentQuality
from .contracts import SegmentResult
from .flags import FLAG_HALLUCINATION_SUSPECTED, FLAG_NO_SPEECH_DETECTED, FLAG_UNCERTAIN

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


@dataclass(slots=True)
class GuardEvaluation:
    segments: list[SegmentResult]
    no_speech_detected: bool = False
    flags: list[str] = field(default_factory=list)


def apply_asr_guards(asr_output: AsrOutput) -> GuardEvaluation:
    guarded_segments: list[SegmentResult] = []
    combined_flags: list[str] = []
    textful_segments = 0
    empty_no_speech_segments = 0

    for index, segment in enumerate(asr_output.segments):
        quality = _quality_for_index(asr_output.segment_qualities, index)
        guarded = _apply_segment_guards(segment, quality)
        guarded_segments.append(guarded)
        if guarded.original_text.strip():
            textful_segments += 1
        elif FLAG_NO_SPEECH_DETECTED in guarded.flags:
            empty_no_speech_segments += 1
        combined_flags = merge_flags(combined_flags, guarded.flags)

    no_speech_detected = bool(guarded_segments) and textful_segments == 0 and empty_no_speech_segments == len(guarded_segments)
    if no_speech_detected:
        combined_flags = merge_flags(combined_flags, [FLAG_NO_SPEECH_DETECTED])

    return GuardEvaluation(
        segments=guarded_segments,
        no_speech_detected=no_speech_detected,
        flags=combined_flags,
    )


def merge_flags(existing: list[str], new_flags: list[str]) -> list[str]:
    merged: list[str] = []
    for flag in [*existing, *new_flags]:
        if flag and flag not in merged:
            merged.append(flag)
    return merged


def has_repeated_ngram(text: str, *, min_repetitions: int = 3, max_ngram_tokens: int = 5) -> bool:
    tokens = TOKEN_PATTERN.findall(text.casefold())
    if len(tokens) < min_repetitions:
        return False

    max_ngram = min(max_ngram_tokens, len(tokens) // min_repetitions)
    for ngram_size in range(1, max_ngram + 1):
        limit = len(tokens) - (ngram_size * min_repetitions) + 1
        for start in range(limit):
            phrase = tokens[start : start + ngram_size]
            repetitions = 1
            cursor = start + ngram_size
            while cursor + ngram_size <= len(tokens) and tokens[cursor : cursor + ngram_size] == phrase:
                repetitions += 1
                if repetitions >= min_repetitions:
                    return True
                cursor += ngram_size
    return False


def _apply_segment_guards(segment: SegmentResult, quality: AsrSegmentQuality) -> SegmentResult:
    flags = list(segment.flags)
    text = segment.original_text.strip()

    if quality.avg_logprob is not None and quality.avg_logprob < -1.0:
        flags = merge_flags(flags, [FLAG_UNCERTAIN])

    if quality.no_speech_prob is not None and quality.no_speech_prob > 0.6:
        if text:
            flags = merge_flags(flags, [FLAG_UNCERTAIN])
        else:
            flags = merge_flags(flags, [FLAG_NO_SPEECH_DETECTED])

    if text and has_repeated_ngram(text):
        flags = merge_flags(flags, [FLAG_HALLUCINATION_SUSPECTED])

    return SegmentResult(
        start=segment.start,
        end=segment.end,
        detected_lang=segment.detected_lang,
        original_text=segment.original_text,
        english_text=segment.english_text,
        confidence=segment.confidence,
        flags=flags,
    )


def _quality_for_index(qualities: list[AsrSegmentQuality], index: int) -> AsrSegmentQuality:
    if index < len(qualities):
        return qualities[index]
    return AsrSegmentQuality()
