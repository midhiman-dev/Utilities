# VaaniScript v0.1

VaaniScript v0.1 is Slice S0 from `TECH_SPEC.md`: repo foundation plus an executable CLI skeleton for a local-first Bengali/Hindi voice-note pipeline.

## Scope in v0.1

- Installable Python 3.13 package with a `vaaniscript` entry point
- Typer CLI skeleton with `transcribe`, `batch`, `watch`, and `version`
- Typed config loading via `pydantic-settings`
- Placeholder pipeline interfaces for the future flow:
  ingest -> VAD/denoise -> ASR -> language detection -> translation -> storage/export

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

`version` is fully implemented. `transcribe`, `batch`, and `watch` are executable CLI placeholders in S0 and intentionally do not perform audio processing yet.
