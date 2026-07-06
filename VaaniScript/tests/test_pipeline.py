import json
import subprocess
from pathlib import Path

from vaaniscript.asr.whisper_engine import AsrOutput, FakeAsrEngine
from vaaniscript.audio import AudioChunk, FakeDenoiseProcessor, FakeVadProcessor
from vaaniscript.config import Settings
from vaaniscript.contracts import SegmentResult
from vaaniscript.pipeline import VaaniPipeline
from vaaniscript.translate import FakeTranslator


def _completed(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_pipeline_probes_before_normalize_and_routes_normalized_audio_to_vad(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"
    commands: list[str] = []
    normalized_wav = tmp_path / "work" / "normalized" / "voice.opus.normalized.wav"
    vad_processor = FakeVadProcessor(chunks=[AudioChunk(path=normalized_wav)])

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command[0])
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "9.5", "format_name": "ogg"}}')
        if command[0] == "ffmpeg":
            return _completed()
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    settings = Settings(app={"workspace_dir": str(tmp_path / "work")})
    asr_engine = FakeAsrEngine()
    result = VaaniPipeline(settings, asr_engine=asr_engine, vad_processor=vad_processor).transcribe(source)

    assert result.status == "ready"
    assert result.stage == "ingest"
    assert commands == ["ffprobe", "ffmpeg"]
    assert vad_processor.calls == [normalized_wav]
    assert asr_engine.calls == [normalized_wav]
    assert result.artifacts["normalized_wav"] == normalized_wav
    assert result.voice_note is not None
    assert result.voice_note.file == "voice.opus"
    assert result.voice_note.duration_sec == 9.5
    assert result.voice_note.segments == []
    assert result.details["audio"] == {
        "chunk_count": 1,
        "denoised_chunk_count": 1,
        "speech_detected": True,
    }
    assert result.details["asr"]["segment_count"] == 0


def test_pipeline_runs_vad_then_denoise_then_asr_then_translation(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"
    normalized_wav = tmp_path / "work" / "normalized" / "voice.opus.normalized.wav"
    denoised_wav = tmp_path / "work" / "denoised" / "voice.chunk0.wav"
    call_order: list[str] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        call_order.append(command[0])
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "4.0", "format_name": "ogg"}}')
        return _completed()

    class OrderedVadProcessor(FakeVadProcessor):
        def detect_speech_chunks(self, normalized_wav: Path) -> list[AudioChunk]:
            call_order.append("vad")
            return super().detect_speech_chunks(normalized_wav)

    class OrderedDenoiseProcessor(FakeDenoiseProcessor):
        def denoise_chunks(self, chunks: list[AudioChunk]) -> list[AudioChunk]:
            call_order.append("denoise")
            return super().denoise_chunks(chunks)

    class OrderedAsrEngine(FakeAsrEngine):
        def transcribe(self, audio_path: Path) -> AsrOutput:
            call_order.append("asr")
            return super().transcribe(audio_path)

    class OrderedTranslator(FakeTranslator):
        def translate(self, *, text: str, source_lang: str, target_lang: str = "en"):
            call_order.append("translate")
            return super().translate(text=text, source_lang=source_lang, target_lang=target_lang)

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    vad_processor = OrderedVadProcessor(chunks=[AudioChunk(path=normalized_wav)])
    denoise_processor = OrderedDenoiseProcessor(output_chunks=[AudioChunk(path=denoised_wav)])
    asr_engine = OrderedAsrEngine(
        output=AsrOutput(
            detected_language="hi",
            segments=[
                SegmentResult(
                    start=0.0,
                    end=1.0,
                    detected_lang="hi",
                    original_text="\u0928\u092e\u0938\u094d\u0924\u0947",
                    english_text="",
                    confidence=0.9,
                    flags=[],
                )
            ],
        )
    )
    translator = OrderedTranslator()

    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=asr_engine,
        vad_processor=vad_processor,
        denoise_processor=denoise_processor,
        translator=translator,
    ).transcribe(source)

    assert result.status == "ready"
    assert call_order == ["ffprobe", "ffmpeg", "vad", "denoise", "asr", "translate"]
    assert asr_engine.calls == [denoised_wav]
    assert translator.calls == [("\u0928\u092e\u0938\u094d\u0924\u0947", "hi", "en")]


def test_pipeline_surfaces_probe_failure_and_skips_vad_denoise_asr_and_translation(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "broken.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return _completed(returncode=1, stderr="not decodable")

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)

    vad_processor = FakeVadProcessor(chunks=[AudioChunk(path=Path("unused.wav"))])
    denoise_processor = FakeDenoiseProcessor()
    asr_engine = FakeAsrEngine()
    translator = FakeTranslator()
    result = VaaniPipeline(
        Settings(),
        asr_engine=asr_engine,
        vad_processor=vad_processor,
        denoise_processor=denoise_processor,
        translator=translator,
    ).transcribe(source)

    assert result.status == "error"
    assert result.stage == "ingest"
    assert result.code == "decode_failed"
    assert result.details["stderr"] == "not decodable"
    assert vad_processor.calls == []
    assert denoise_processor.calls == []
    assert asr_engine.calls == []
    assert translator.calls == []
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
    assert payload["details"]["audio"] == {
        "chunk_count": 1,
        "denoised_chunk_count": 1,
        "speech_detected": True,
    }
    assert json.loads(json.dumps(payload))["stage"] == "ingest"
    assert payload["voice_note"] == {
        "file": "voice.mp3",
        "duration_sec": 5.0,
        "segments": [],
        "full_english_text": "",
        "full_original_text": "",
    }


def test_pipeline_skips_asr_when_vad_returns_no_speech_chunks(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "4.5", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    vad_processor = FakeVadProcessor(chunks=[])
    denoise_processor = FakeDenoiseProcessor()
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
        vad_processor=vad_processor,
        denoise_processor=denoise_processor,
        translator=translator,
    ).transcribe(source)

    assert result.status == "ready"
    assert result.code == "no_speech_detected"
    assert result.voice_note is not None
    assert result.voice_note.segments == []
    assert result.voice_note.full_original_text == ""
    assert result.voice_note.full_english_text == ""
    assert result.details["audio"] == {
        "chunk_count": 0,
        "denoised_chunk_count": 0,
        "speech_detected": False,
        "flags": ["no_speech_detected"],
    }
    assert result.details["asr"] == {
        "detected_language": None,
        "segment_count": 0,
    }
    assert denoise_processor.calls == []
    assert asr_engine.calls == []
    assert translator.calls == []


def test_pipeline_maps_multiple_preprocessed_chunks_into_voice_note_in_order(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "8.0", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    vad_processor = FakeVadProcessor(
        chunks=[
            AudioChunk(path=tmp_path / "work" / "normalized" / "voice.chunk0.wav", start_sec=0.0, end_sec=2.0),
            AudioChunk(path=tmp_path / "work" / "normalized" / "voice.chunk1.wav", start_sec=5.0, end_sec=7.0),
        ]
    )
    denoise_processor = FakeDenoiseProcessor(
        output_chunks=[
            AudioChunk(path=tmp_path / "work" / "denoised" / "voice.chunk0.wav", start_sec=0.0, end_sec=2.0),
            AudioChunk(path=tmp_path / "work" / "denoised" / "voice.chunk1.wav", start_sec=5.0, end_sec=7.0),
        ]
    )
    asr_engine = FakeAsrEngine(
        outputs=[
            AsrOutput(
                detected_language="hi",
                segments=[
                    SegmentResult(
                        start=0.1,
                        end=0.9,
                        detected_lang="hi",
                        original_text="\u0928\u092e\u0938\u094d\u0924\u0947",
                        english_text="",
                        confidence=0.91,
                        flags=[],
                    )
                ],
            ),
            AsrOutput(
                detected_language="hi",
                segments=[
                    SegmentResult(
                        start=0.2,
                        end=0.8,
                        detected_lang="hi",
                        original_text="\u0926\u0941\u0928\u093f\u092f\u093e",
                        english_text="",
                        confidence=0.83,
                        flags=[],
                    )
                ],
            ),
        ]
    )

    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=asr_engine,
        vad_processor=vad_processor,
        denoise_processor=denoise_processor,
    ).transcribe(source)

    assert result.voice_note is not None
    assert [segment.original_text for segment in result.voice_note.segments] == [
        "\u0928\u092e\u0938\u094d\u0924\u0947",
        "\u0926\u0941\u0928\u093f\u092f\u093e",
    ]
    assert [(segment.start, segment.end) for segment in result.voice_note.segments] == [
        (0.1, 0.9),
        (5.2, 5.8),
    ]
    assert result.voice_note.full_original_text == "\u0928\u092e\u0938\u094d\u0924\u0947 \u0926\u0941\u0928\u093f\u092f\u093e"
    assert result.details["audio"] == {
        "chunk_count": 2,
        "denoised_chunk_count": 2,
        "speech_detected": True,
    }
    assert result.details["asr"] == {"detected_language": "hi", "segment_count": 2}
    assert asr_engine.calls == [
        tmp_path / "work" / "denoised" / "voice.chunk0.wav",
        tmp_path / "work" / "denoised" / "voice.chunk1.wav",
    ]


def test_translation_still_runs_after_chunk_preprocessing(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.opus"

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command[0] == "ffprobe":
            return _completed(stdout='{"format": {"duration": "4.0", "format_name": "ogg"}}')
        return _completed()

    monkeypatch.setattr("vaaniscript.ingest.probe.run_command", fake_runner)
    monkeypatch.setattr("vaaniscript.ingest.normalize.run_command", fake_runner)

    vad_processor = FakeVadProcessor(
        chunks=[AudioChunk(path=tmp_path / "work" / "normalized" / "voice.chunk0.wav", start_sec=0.0)]
    )
    denoise_processor = FakeDenoiseProcessor(
        output_chunks=[AudioChunk(path=tmp_path / "work" / "denoised" / "voice.chunk0.wav", start_sec=0.0)]
    )
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
                )
            ],
        )
    )
    translator = FakeTranslator()

    result = VaaniPipeline(
        Settings(app={"workspace_dir": str(tmp_path / "work")}),
        asr_engine=asr_engine,
        vad_processor=vad_processor,
        denoise_processor=denoise_processor,
        translator=translator,
    ).transcribe(source)

    assert translator.calls == [("\u0928\u092e\u0938\u094d\u0924\u0947 office", "hi", "en")]
    assert result.voice_note is not None
    assert result.voice_note.segments[0].detected_lang == "hi"
    assert result.voice_note.segments[0].flags == ["lang_derived_from_script"]
    assert result.voice_note.segments[0].english_text == "[hi->en] \u0928\u092e\u0938\u094d\u0924\u0947 office"
    assert result.voice_note.full_english_text == "[hi->en] \u0928\u092e\u0938\u094d\u0924\u0947 office"


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
