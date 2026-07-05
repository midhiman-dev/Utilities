from pathlib import Path
from types import SimpleNamespace

from vaaniscript.asr.whisper_engine import AsrOutput, FakeAsrEngine, FasterWhisperEngine
from vaaniscript.contracts import SegmentResult


def test_faster_whisper_engine_is_lazy_on_init(monkeypatch) -> None:
    def fail_import(name: str):
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr("vaaniscript.asr.whisper_engine.import_module", fail_import)

    engine = FasterWhisperEngine(model_size="small")

    assert engine.model_size == "small"


def test_faster_whisper_engine_maps_segments_without_real_dependency(monkeypatch) -> None:
    fake_segments = [
        SimpleNamespace(start=0.0, end=1.2, text="नमस्ते", avg_logprob=-0.5),
        SimpleNamespace(start=1.2, end=2.5, text="দুনিয়া", avg_logprob=-1.0),
    ]
    fake_info = SimpleNamespace(language="hi")

    class FakeModel:
        def transcribe(self, audio_path: str, **kwargs):
            assert audio_path.endswith("normalized.wav")
            assert kwargs["condition_on_previous_text"] is False
            assert kwargs["vad_filter"] is False
            return fake_segments, fake_info

    class FakeWhisperModule:
        class WhisperModel:
            def __init__(self, model_size: str, compute_type: str) -> None:
                assert model_size == "small"
                assert compute_type == "int8"

            def transcribe(self, *args, **kwargs):
                return FakeModel().transcribe(*args, **kwargs)

    monkeypatch.setattr(
        "vaaniscript.asr.whisper_engine.import_module",
        lambda name: FakeWhisperModule,
    )

    output = FasterWhisperEngine().transcribe(Path("voice.normalized.wav"))

    assert output.detected_language == "hi"
    assert output.segments == [
        SegmentResult(
            start=0.0,
            end=1.2,
            detected_lang="hi",
            original_text="नमस्ते",
            english_text="",
            confidence=0.9,
            flags=[],
        ),
        SegmentResult(
            start=1.2,
            end=2.5,
            detected_lang="hi",
            original_text="দুনিয়া",
            english_text="",
            confidence=0.8,
            flags=[],
        ),
    ]


def test_fake_asr_engine_records_calls() -> None:
    engine = FakeAsrEngine(output=AsrOutput(segments=[]))
    audio_path = Path("voice.normalized.wav")

    output = engine.transcribe(audio_path)

    assert output.segments == []
    assert engine.calls == [audio_path]
