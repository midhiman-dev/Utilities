# VaaniScript v0.1

VaaniScript v0.1 currently implements Slice S1 from `TECH_SPEC.md`: audio ingest validation, probe, and normalization for a future local-first Bengali/Hindi voice-note pipeline.

## Scope in v0.1

- Installable Python 3.13 package with a `vaaniscript` entry point
- Typer CLI skeleton with `transcribe`, `batch`, `watch`, and `version`
- Typed config loading via `pydantic-settings`
- Safe ingest support for `.opus`, `.mp3`, and `.m4a`
- `ffprobe` validation before `ffmpeg` normalization
- Deterministic normalization to 16kHz mono WAV (`s16`) under the workspace directory
- Structured ingest-stage CLI output describing validation/probe/normalize success or controlled failure

## Out of Scope in v0.1

- GUI
- Cloud fallback
- Real ASR or translation
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

`version` is fully implemented. `transcribe` now validates the input extension, runs `ffprobe`, and normalizes supported audio to a deterministic WAV path before any future ASR work. It prints a structured ingest-stage result and does not transcribe yet. `batch` and `watch` remain placeholders.
