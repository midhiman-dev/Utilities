import json
import subprocess
from pathlib import Path

from vaaniscript.asr.whisper_engine import AsrOutput, FakeAsrEngine
from vaaniscript.config import Settings
from vaaniscript.contracts import SegmentResult
from vaaniscript.pipeline import VaaniPipeline
from vaaniscript.translate import FakeTranslator


def _completed(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_pipeline_probes_before_normalize(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"
    calls: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "9.5", "format_name": "ogg"}}')
        if command[0] == "ffmpeg":
            return _completed()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    settings = Settings(app={"workspace_dir": str(tmp_path / "work")})
    asr_engine = FakeAsrEngine()
    result = VaaniPipeline(settings, asr_engine=asr_engine).transcribe(source)

    assert result.status == "ready"
    assert result.stage == "ingest"
    assert [command[0] for command in calls] == ["ffprobe", "ffmpeg"]
    assert asr_engine.calls == [tmp_path / "work" / "normalized" / "voice.opus.normalized.wav"]
    assert result.artifacts["normalized_wav"] == tmp_path / "work" / "normalized" / "voice.opus.normalized.wav"
    assert result.voice_note is not None
    assert result.voice_note.file == "voice.opus"
    assert result.voice_note.duration_sec == 9.5
    assert result.voice_note.segments == []
    assert result.details["asr"]["segment_count"] == 0


def test_pipeline_surfaces_probe_failure(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "broken.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return _completed(returncode=1, stderr="not decodable")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)

    asr_engine = FakeAsrEngine()
    result = VaaniPipeline(Settings(), asr_engine=asr_engine).transcribe(source)

    assert result.status == "error"
    assert result.stage == "ingest"
    assert result.code == "decode_failed"
    assert result.details["stderr"] == "not decodable"
    assert asr_engine.calls == []
    assert result.voice_note is not None
    assert result.voice_note.file == "broken.opus"
    assert result.voice_note.duration_sec is None


def test_pipeline_surfaces_unsupported_format(tmp_path: Path) -> None:
    result = VaaniPipeline(Settings()).transcribe(tmp_path / "voice.wav")

    assert result.status == "error"
    assert result.code == "unsupported_format"
    assert result.voice_note is not None
    assert result.voice_note.file == "voice.wav"


def test_pipeline_result_is_json_serializable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.mp3"

    def fake_probe(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "5.0", "format_name": "mp3"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_probe)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_probe)

    asr_engine = FakeAsrEngine()
    result = VaaniPipeline(Settings(app={"workspace_dir": str(tmp_path / "work")}), asr_engine=asr_engine).transcribe(source)
    payload = result.to_dict()

    assert payload["details"]["probe"]["extension"] == ".mp3"
    assert json.loads(json.dumps(payload))["stage"] == "ingest"
    assert payload["voice_note"] == {
        "file": "voice.mp3",
        "duration_sec": 5.0,
        "segments": [],
        "full_english_text": "",
        "full_original_text": "",
    }


def test_pipeline_maps_asr_segments_into_voice_note(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "4.5", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    asr_engine = FakeAsrEngine(
        output=AsrOutput(
            detected_language="hi",
            segments=[
                SegmentResult(
                    start=0.0,
                    end=1.0,
                    detected_lang="hi",
                    original_text="\u0928\u092e\u0938\u094d\u0924\u0947",
                    english_text="",
                    confidence=0.91,
                    flags=[],
                ),
                SegmentResult(
                    start=1.0,
                    end=2.0,
                    detected_lang="hi",
                    original_text="\u0926\u0941\u0928\u093f\u092f\u093e",
                    english_text="",
                    confidence=0.83,
                    flags=[],
                ),
            ],
        )
    )

    result = VaaniPipeline(Settings(app={"workspace_dir": str(tmp_path / "work")}), asr_engine=asr_engine).transcribe(source)

    assert result.voice_note is not None
    assert result.voice_note.segments[0].original_text == "\u0928\u092e\u0938\u094d\u0924\u0947"
    assert result.voice_note.segments[0].english_text == ""
    assert result.voice_note.full_original_text == "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u0941\u0928\u093f\u092f\u093e"
    assert result.voice_note.full_english_text == ""
    assert result.details["asr"] == {"detected_language": "hi", "segment_count": 2}


def test_translation_runs_only_after_successful_asr_segment_creation(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "4.0", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    asr_engine = FakeAsrEngine(
        output=AsrOutput(
            detected_language="hi",
            segments=[
                SegmentResult(
                    start=0.0,
                    end=1.0,
                    detected_lang="hi",
                    original_text="\u0928\u092e\u0938\u094d\u0924\u0947",
                    english_text="",
                    confidence=0.91,
                    flags=[],
                )
            ],
        )
    )
    translator = FakeTranslator()

    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=asr_engine,
        translator=translator,
    ).transcribe(source)

    assert result.status == "ready"
    assert asr_engine.calls == [tmp_path / "work" / "normalized" / "voice.opus.normalized.wav"]
    assert translator.calls == [("\u0928\u092e\u0938\u094d\u0924\u0947", "hi", "en")]
    assert result.voice_note is not None
    assert result.voice_note.segments[0].english_text == "[hi->en] \u0928\u092e\u0938\u094d\u0924\u0947"


def test_translation_is_skipped_on_ingest_failure(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "broken.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return _completed(returncode=1, stderr="not decodable")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)

    translator = FakeTranslator()
    asr_engine = FakeAsrEngine()
    result = VaaniPipeline(Settings(), asr_engine=asr_engine, translator=translator).transcribe(source)

    assert result.status == "error"
    assert asr_engine.calls == []
    assert translator.calls == []


def test_translation_is_skipped_when_there_are_no_asr_segments(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "4.0", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    translator = FakeTranslator()
    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=FakeAsrEngine(output=AsrOutput(segments=[], detected_language=None)),
        translator=translator,
    ).transcribe(source)

    assert result.status == "ready"
    assert translator.calls == []
    assert result.voice_note is not None
    assert result.voice_note.segments == []
    assert result.voice_note.full_english_text == ""


def test_translation_routes_hi_and_bn_segments_and_populates_full_english_text(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "6.0", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    asr_engine = FakeAsrEngine(
        output=AsrOutput(
            detected_language="hi",
            segments=[
                SegmentResult(
                    start=0.0,
                    end=1.0,
                    detected_lang="unknown",
                    original_text="\u0928\u092e\u0938\u094d\u0924\u0947 office",
                    english_text="",
                    confidence=0.91,
                    flags=[],
                ),
                SegmentResult(
                    start=1.0,
                    end=2.0,
                    detected_lang="ambiguous",
                    original_text="\u09ac\u09a8\u09cd\u09a7\u09c1 office",
                    english_text="",
                    confidence=0.89,
                    flags=[],
                ),
            ],
        )
    )
    translator = FakeTranslator()

    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=asr_engine,
        translator=translator,
    ).transcribe(source)

    assert result.voice_note is not None
    assert [segment.detected_lang for segment in result.voice_note.segments] == ["hi", "bn"]
    assert translator.calls == [
        ("\u0928\u092e\u0938\u094d\u0924\u0947 office", "hi", "en"),
        ("\u09ac\u09a8\u09cd\u09a7\u09c1 office", "bn", "en"),
    ]
    assert result.voice_note.segments[0].flags == ["lang_derived_from_script"]
    assert result.voice_note.segments[1].flags == ["lang_derived_from_script"]
    assert result.voice_note.full_original_text == "\u0928\u092e\u0938\u094d\u0924\u0947 office \u09ac\u09a8\u09cd\u09a7\u09c1 office"
    assert result.voice_note.full_english_text == "[hi->en] \u0928\u092e\u0938\u094d\u0924\u0947 office [bn->en] \u09ac\u09a8\u09cd\u09a7\u09c1 office"


def test_ambiguous_and_unknown_segments_are_flagged_and_not_translated(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "6.0", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    asr_engine = FakeAsrEngine(
        output=AsrOutput(
            detected_language=None,
            segments=[
                SegmentResult(
                    start=0.0,
                    end=1.0,
                    detected_lang="unknown",
                    original_text="hello world",
                    english_text="",
                    confidence=0.75,
                    flags=[],
                ),
                SegmentResult(
                    start=1.0,
                    end=2.0,
                    detected_lang="ambiguous",
                    original_text="\u0928\u09ae",
                    english_text="",
                    confidence=0.75,
                    flags=[],
                ),
            ],
        )
    )
    translator = FakeTranslator()

    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=asr_engine,
        translator=translator,
    ).transcribe(source)

    assert translator.calls == []
    assert result.voice_note is not None
    assert result.voice_note.segments[0].detected_lang == "unknown"
    assert result.voice_note.segments[0].english_text == ""
    assert result.voice_note.segments[0].flags == [
        "lang_unknown",
        "no_indic_script",
        "translation_skipped_unsupported_language",
    ]
    assert result.voice_note.segments[1].detected_lang == "ambiguous"
    assert result.voice_note.segments[1].english_text == ""
    assert result.voice_note.segments[1].flags == [
        "lang_ambiguous",
        "translation_skipped_unsupported_language",
    ]
    assert result.voice_note.full_english_text == ""
