from vaaniscript.asr import AsrOutput, AsrSegmentQuality
from vaaniscript.contracts import SegmentResult
from vaaniscript.quality import apply_asr_guards, has_repeated_ngram


def _segment(*, text: str, flags: list[str] | None = None) -> SegmentResult:
    return SegmentResult(
        start=0.0,
        end=1.0,
        detected_lang="hi",
        original_text=text,
        english_text="",
        confidence=0.8,
        flags=flags or [],
    )


def test_low_avg_logprob_adds_uncertain_flag() -> None:
    evaluation = apply_asr_guards(
        AsrOutput(
            segments=[_segment(text="नमस्ते")],
            segment_qualities=[AsrSegmentQuality(avg_logprob=-1.2)],
        )
    )

    assert evaluation.no_speech_detected is False
    assert evaluation.segments[0].flags == ["uncertain"]


def test_high_no_speech_prob_with_text_adds_uncertain_flag() -> None:
    evaluation = apply_asr_guards(
        AsrOutput(
            segments=[_segment(text="নমস্কার")],
            segment_qualities=[AsrSegmentQuality(no_speech_prob=0.75)],
        )
    )

    assert evaluation.no_speech_detected is False
    assert evaluation.segments[0].flags == ["uncertain"]


def test_high_no_speech_prob_without_text_marks_no_speech() -> None:
    evaluation = apply_asr_guards(
        AsrOutput(
            segments=[_segment(text="   ")],
            segment_qualities=[AsrSegmentQuality(no_speech_prob=0.9)],
        )
    )

    assert evaluation.no_speech_detected is True
    assert evaluation.flags == ["no_speech_detected"]
    assert evaluation.segments[0].flags == ["no_speech_detected"]


def test_repeated_ngram_text_adds_hallucination_flag() -> None:
    evaluation = apply_asr_guards(
        AsrOutput(segments=[_segment(text="hello world hello world hello world")])
    )

    assert evaluation.segments[0].flags == ["hallucination_suspected"]


def test_clean_asr_text_does_not_add_hallucination_flag() -> None:
    evaluation = apply_asr_guards(
        AsrOutput(segments=[_segment(text="নমস্কার সবাই কেমন আছেন")])
    )

    assert evaluation.segments[0].flags == []


def test_repeated_ngram_detector_is_deterministic() -> None:
    assert has_repeated_ngram("hello hello hello") is True
    assert has_repeated_ngram("hello there hello again") is False
