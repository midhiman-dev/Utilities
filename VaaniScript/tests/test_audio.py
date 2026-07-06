from pathlib import Path

from pathlib import Path

from vaaniscript.audio import AudioChunk, FakeDenoiseProcessor, FakeVadProcessor, NoOpDenoiseProcessor, NoOpVadProcessor


def test_noop_vad_processor_returns_single_chunk_for_normalized_wav() -> None:
    normalized_wav = Path("workspace/normalized/voice.wav")

    chunks = NoOpVadProcessor().detect_speech_chunks(normalized_wav)

    assert chunks == [AudioChunk(path=normalized_wav, start_sec=0.0, end_sec=None, flags=[])]


def test_noop_denoise_processor_returns_chunks_unchanged() -> None:
    chunks = [AudioChunk(path=Path("workspace/normalized/voice.wav"), start_sec=1.0, end_sec=2.0)]

    output = NoOpDenoiseProcessor().denoise_chunks(chunks)

    assert output == chunks


def test_fake_processors_record_calls() -> None:
    chunk = AudioChunk(path=Path("workspace/normalized/voice.wav"))
    vad = FakeVadProcessor(chunks=[chunk])
    denoise = FakeDenoiseProcessor(output_chunks=[chunk])

    assert vad.detect_speech_chunks(Path("workspace/normalized/voice.wav")) == [chunk]
    assert denoise.denoise_chunks([chunk]) == [chunk]
    assert vad.calls == [Path("workspace/normalized/voice.wav")]
    assert denoise.calls == [[chunk]]
