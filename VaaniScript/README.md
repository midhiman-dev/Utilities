# VaaniScript v0.1

VaaniScript v0.1 currently implements S5 foundations from `TECH_SPEC.md`: ingest validation/normalization, stable pipeline result contracts, an ASR adapter boundary, and a translation adapter boundary for a future local-first Bengali/Hindi voice-note pipeline.

## Scope in v0.1

- Installable Python 3.13 package with a `vaaniscript` entry point
- Typer CLI skeleton with `transcribe`, `batch`, `watch`, and `version`
- Typed config loading via `pydantic-settings`
- Safe ingest support for `.opus`, `.mp3`, and `.m4a`
- `ffprobe` validation before `ffmpeg` normalization
- Deterministic normalization to 16kHz mono WAV (`s16`) under the workspace directory
- Structured ingest-stage CLI output describing validation/probe/normalize success or controlled failure
- Stable `voice_note` JSON contract with file, duration, segments, `original_text`, `english_text`, and full-text fields
- Mockable ASR engine boundary with a lazy `faster-whisper` adapter that does not require the dependency for unit tests
- Mockable translation boundary with deterministic fake translation in tests and a lazy IndicTrans2 adapter that does not require translation dependencies for unit tests

## Out of Scope in v0.1

- GUI
- Cloud fallback
- Real ASR
- Hinglish or romanized text support
- Sanscript or glossary logic
- Auth, web API, streaming, diarization
- Model downloads or bundled large models

## Install

```bash
py -3.13 -m pip install -e .[dev]
```

Run from [C:\Dhiman\P\portfolio\Utilities\vaaniscript](C:\Dhiman\P\portfolio\Utilities\vaaniscript).
Run from `C:\Dhiman\P\portfolio\Utilities\vaaniscript`.

## Commands Available Now

```bash
vaaniscript --help
vaaniscript version
vaaniscript transcribe path\to\file.opus
vaaniscript batch path\to\folder
vaaniscript watch path\to\folder
```

`version` is fully implemented. `transcribe` validates the input extension, runs `ffprobe`, normalizes supported audio to a deterministic WAV path, passes that WAV through the ASR adapter boundary, and then routes supported Hindi/Bengali segments through the translation adapter boundary. By default the CLI still emits deterministic empty English text unless a real ASR engine and translator are explicitly wired in. `batch` and `watch` remain placeholders.
