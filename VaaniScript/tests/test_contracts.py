import json
from pathlib import Path

from vaaniscript.contracts import PipelineStageResult, SegmentResult, VoiceNoteResult


def test_voice_note_result_matches_stable_json_shape() -> None:
    result = VoiceNoteResult(
        file="PTT-20260705-WA0001.opus",
        duration_sec=42.3,
        segments=[
            SegmentResult(
                start=0.0,
                end=6.2,
                detected_lang="bn",
                original_text="...",
                english_text="...",
                confidence=0.88,
                flags=[],
            )
        ],
        full_english_text="...",
        full_original_text="...",
    )

    assert result.to_dict() == {
        "file": "PTT-20260705-WA0001.opus",
        "duration_sec": 42.3,
        "segments": [
            {
                "start": 0.0,
                "end": 6.2,
                "detected_lang": "bn",
                "original_text": "...",
                "english_text": "...",
                "confidence": 0.88,
                "flags": [],
            }
        ],
        "full_english_text": "...",
        "full_original_text": "...",
    }


def test_pipeline_stage_result_json_is_deterministic() -> None:
    result = PipelineStageResult(
        source=Path("voice.opus"),
        stage="ingest",
        status="ready",
        message="Input validated, probed, and normalized.",
        details={"probe": {"duration_seconds": 42.3}},
        artifacts={"normalized_wav": Path("workspace/normalized/voice.opus.normalized.wav")},
        voice_note=VoiceNoteResult(file="voice.opus", duration_sec=42.3),
    )

    payload = result.to_dict()

    assert payload == {
        "source": "voice.opus",
        "stage": "ingest",
        "status": "ready",
        "message": "Input validated, probed, and normalized.",
        "code": None,
        "details": {"probe": {"duration_seconds": 42.3}},
        "artifacts": {"normalized_wav": "workspace/normalized/voice.opus.normalized.wav"},
        "voice_note": {
            "file": "voice.opus",
            "duration_sec": 42.3,
            "segments": [],
            "full_english_text": "",
            "full_original_text": "",
        },
    }
    assert json.loads(result.to_json()) == payload


def test_pipeline_stage_result_preserves_null_voice_note() -> None:
    result = PipelineStageResult(
        source=Path("voice.opus"),
        stage="watch",
        status="placeholder",
        message="watch is not implemented yet",
    )

    assert result.to_dict()["voice_note"] is None
