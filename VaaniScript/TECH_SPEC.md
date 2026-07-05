# VaaniScript — Local-First Design Spec (Bengali + Hindi Voice Note Transcriber/Translator)

## 0. Assumptions (stated explicitly, since the brief left these open)

1. **Input path**: User exports/forwards `.opus` (WhatsApp's native voice-note codec, Opus-in-OGG container) or `.mp3`/`.m4a` files to a watched folder — NOT live capture from WhatsApp Desktop's memory/socket. WhatsApp doesn't expose a public API for this, so file-drop is the only sane integration point.
2. **"Lightweight"** = runs on a mid-range laptop (8GB RAM, no GPU) without needing a cloud account, but can *optionally* use a GPU or cloud API if the user has one — never a hard requirement.
3. **Scope is now Bengali and Hindi speech only** — spoken in native pronunciation, whether or not the speaker occasionally drops in an English word (e.g. "meeting", "office" mid-sentence is common and expected; full Hinglish/romanized-script handling is explicitly dropped per this revision).
4. **Output**: plain English text primarily; original-language (native-script) transcript kept as a side artifact for verification, not shown as the main product.
5. **Single-user desktop tool**, not a multi-tenant service — so no auth system, no user accounts.
6. **Offline-first, online-optional**: default pipeline must work with zero network calls. Cloud STT/MT is an opt-in toggle for users who accept the privacy tradeoff for higher accuracy.
7. **Occasional embedded English words within Bengali/Hindi speech** (common in real conversation) are handled by the translation model directly — Whisper transcribes them in Latin script inline, and IndicTrans2 passes them through largely unchanged. This is a much smaller problem than full Hinglish and doesn't need its own subsystem.

Dropping Hinglish removes the single hardest and least reliable part of the original design — the lexical post-hoc classifier, the Sanscript normalization step, and the glossary-fallback maintenance burden all go away. What's left is a substantially simpler and more accurate two-language pipeline.

---

## 1. Recommended Architecture

**Local Python core + Typer CLI + optional PySide6 GUI shell, packaged with PyInstaller** — unchanged from the original recommendation, still consistent with your Utilities monorepo pattern.

```
+-------------------------------------------------------------------+
|                      USER'S MACHINE (offline)                      |
|                                                                     |
|  +---------------+     +----------------------------------------+ |
|  |  Watched Dir  |     |            PySide6 GUI (optional)        | |
|  |  ~/VaaniScript/  |     |  drag-drop, progress bar, review pane     | |
|  |  inbox/       |     +-----------------+----------------------+ |
|  +-------+-------+                       | calls                   |
|          | new file event                 v                        |
|          |              +-----------------------------+            |
|          +------------->|   CLI Core (Typer commands)   |            |
|                         |   transcribe / translate /    |            |
|                         |   batch / watch                |            |
|                         +---------------+---------------+            |
|                                          v                            |
|              +-----------------------------------------------+       |
|              |  1. Ingest & Normalize (ffmpeg)                  |       |
|              |     opus/m4a/mp3 -> 16kHz mono WAV                |       |
|              +---------------------+---------------------------+       |
|                                    v                                   |
|              +-----------------------------------------------+       |
|              |  2. VAD + Denoise (silero-vad, noisereduce)      |       |
|              |     strip silence, trim compression artifacts,   |       |
|              |     chunk long notes (>60s)                       |       |
|              +---------------------+---------------------------+       |
|                                    v                                   |
|              +-----------------------------------------------+       |
|              |  3. ASR: faster-whisper (CTranslate2)             |       |
|              |     model: small or medium (CPU int8)             |       |
|              |     lang forced/detected in {hi, bn}              |       |
|              |     -> per-segment: text, lang_probs, timing      |       |
|              +---------------------+---------------------------+       |
|                                    v                                   |
|              +-----------------------------------------------+       |
|              |  4. Language Confirm (hi vs bn)                   |       |
|              |     Whisper lang_id + Unicode-block check          |       |
|              |     (Devanagari vs Bengali script ranges)          |       |
|              +---------------------+---------------------------+       |
|                        +-----------+-----------+                       |
|                        v                       v                        |
|            +--------------------+   +--------------------+             |
|            | Hindi -> IndicTrans2|   | Bengali -> IndicTrans2|          |
|            |  (hi -> en)          |   |  (bn -> en)           |          |
|            +----------+----------+   +-----------+----------+          |
|                        +-----------+-----------+                       |
|                                    v                                    |
|              +-----------------------------------------------+       |
|              |  5. Post-process: merge segments, punctuate,     |       |
|              |     confidence-flag low-quality spans             |       |
|              +---------------------+---------------------------+       |
|                                    v                                   |
|              +-----------------------------------------------+       |
|              |  6. Local SQLite store + .txt/.srt/.json exports  |       |
|              |     ~/VaaniScript/db.sqlite + outputs/                |       |
|              +-----------------------------------------------+       |
+---------------------------------------------------------------------+

   Optional, opt-in, network-gated:
   [Cloud fallback] -> Azure Speech / Google STT / OpenAI Whisper API
   (only triggered if local confidence < threshold AND user enabled it)
```

The pipeline shape is identical to the original — the change is entirely inside step 4, which used to be a three-way router (Hindi / Bengali / Hinglish) with a lexical classifier, and is now a two-way router using only script/Unicode detection, which is far more reliable.

---

## 2. Tech Stack (updated)

**Runtime baseline:** VaaniScript is built and validated on **Python 3.13**. The repository should pin this explicitly in `pyproject.toml` using `requires-python = ">=3.13,<3.14"`. If any ML/audio dependency does not support Python 3.13 cleanly, do not silently downgrade the project; capture it as a spike finding and decide whether to replace the dependency, isolate it, or revise the runtime decision.

| Layer | Choice | Why this and not the alternative |
|---|---|---|
| Language/runtime | Python 3.13 | Matches the current VaaniScript build environment; pin the project to Python 3.13 and validate ASR/MT/package compatibility during the spike before adding real model code |
| Audio decode/normalize | `ffmpeg` (subprocess, static binary bundled) | Only reliable Opus/OGG decoder across OS |
| VAD | `silero-vad` (ONNX, ~2MB) | Fast on CPU, no PyTorch runtime needed at inference if exported to ONNX |
| Denoise | `noisereduce` (spectral gating) | Lightweight, good enough for compressed voice notes |
| ASR engine | `faster-whisper` (CTranslate2 backend) | 4x faster, lower RAM than openai-whisper on CPU |
| ASR model size | `small` default, `medium` toggle | `medium` gives a real accuracy bump on Hindi/Bengali; worth exposing since Hinglish complexity is gone and this is now the main accuracy lever |
| Language ID | Whisper `detect_language()` **restricted to {hi, bn}** via `initial_prompt`/language hint, confirmed by Unicode-block ratio on the output text | Constraining Whisper's language search space to two candidates measurably improves both speed and accuracy versus open-vocabulary detection |
| Hindi/Bengali -> English MT | `IndicTrans2` (AI4Bharat, distilled 200M variant) | Purpose-built for Indic->English; no need for a Hinglish-tolerant "informal mode" anymore — standard mode is sufficient |
| ~~Hinglish transliteration~~ | **removed** | `indic-transliteration`/Sanscript dependency dropped entirely |
| ~~Hinglish glossary~~ | **removed** | No CSV to build or maintain |
| GUI (optional) | PySide6 | LGPL, native look on Win/Mac |
| Packaging | PyInstaller + GitHub Actions matrix build (win/mac) | Same pipeline you already run |
| Storage | SQLite (single file) | Zero-config, portable |
| Config | `pydantic-settings` + local `config.toml` | Type-safe, human-editable |

**Model footprint** (lighter than before — no Sanscript, no glossary asset):
- faster-whisper small (int8): ~250MB
- silero-vad: ~2MB
- IndicTrans2 distilled: ~500MB-1GB

Total local disk: still under 2GB.

---

## 3. Speech-to-Text Pipeline (detail)

Unchanged from the original except step 4, which is simpler:

1. **Ingest**: `ffmpeg -i input.opus -ar 16000 -ac 1 -sample_fmt s16 out.wav`.
2. **Chunking**: split at VAD-detected silence boundaries into <=30s chunks.
3. **Denoise**: apply spectral gating only if RMS noise floor exceeds a threshold.
4. **ASR pass**: run faster-whisper **with the language search space restricted to `{hi, bn}`** (Whisper supports passing a language hint or picking the argmax among a restricted set of language tokens) rather than fully open detection across 90+ languages. This alone reduces a class of misdetection errors that existed in the original three-way design. Use `condition_on_previous_text=False` and `vad_filter=True` as before.
5. **Segment-level metadata retained**: text, timestamps, `avg_logprob`, `no_speech_prob`.
6. **Low-confidence flagging**: unchanged — `avg_logprob < -1.0` or `no_speech_prob > 0.6` triggers `[uncertain]` tag.

---

## 4. Language Detection & Routing Logic (simplified)

This used to be the hardest part of the design (three-way routing with a lexical classifier for romanized text). With Hinglish dropped, it becomes a straightforward two-way decision:

```
transcript_segment
     |
     v
whisper_lang_id (constrained to hi/bn) 
     |
     v
unicode_block_check(text)
     |
     +-- Devanagari range (U+0900-U+097F) dominant -> lang = hi
     +-- Bengali range   (U+0980-U+09FF) dominant -> lang = bn
     +-- disagreement between whisper_lang_id and script check
              -> flag [lang_ambiguous], default to whisper_lang_id,
                 surface both signals in the JSON for manual review
```

Why keep both signals instead of trusting Whisper alone: Whisper's acoustic language ID for Hindi vs Bengali is generally good but not perfect, especially on noisy compressed audio, and a free Unicode-range check on its own *output text* is essentially zero-cost cross-validation. Unlike the Hinglish case, this doesn't need a hand-built stopword lexicon — script detection alone is a strong, reliable signal once romanized input is out of scope.

**Mixed-script edge case that remains**: a Bengali or Hindi sentence with an English proper noun or loanword transcribed in Latin script (e.g. "office" inside a Bengali sentence) — this is expected and handled at the *translation* step (Section 5), not the language-routing step, since it's a token-level, not segment-level, phenomenon.

---

## 5. Translation Logic (simplified)

```
transcript_segment (lang = hi or bn)
     |
     v
IndicTrans2(lang -> en)
     |
     v
English text (embedded English words/proper nouns pass through
   largely unchanged since they're already in Latin script and
   the model has seen code-mixed training data of this form)
```

No glossary fallback, no informal-mode branch, no spelling-variant normalization. This is now a two-branch model call, which is both simpler to implement and easier to test — you can build a small labeled validation set (e.g. 20 Bengali + 20 Hindi voice notes with human reference translations) and directly measure BLEU/human-rated accuracy per language without a third noisy category muddying results.

**Output structure per voice note (JSON) — unchanged shape, simpler content:**
```json
{
  "file": "PTT-20260705-WA0001.opus",
  "duration_sec": 42.3,
  "segments": [
    {
      "start": 0.0, "end": 6.2,
      "detected_lang": "bn",
      "original_text": "\u0995\u09be\u09b2 \u0985\u09ab\u09bf\u09b8\u09c7 \u09ae\u09bf\u099f\u09bf\u0982 \u0986\u099b\u09c7 \u09a8\u09be?",
      "english_text": "There's a meeting at the office tomorrow, right?",
      "confidence": 0.88,
      "flags": []
    }
  ],
  "full_english_text": "...",
  "full_original_text": "..."
}
```

---

## 6. Privacy & Storage

Unchanged from the original design — this part of the spec didn't depend on which languages are in scope:

- **Default: zero network calls.** All models run locally via CTranslate2.
- **Cloud fallback is opt-in and explicit**: `allow_cloud_fallback = false` by default; only low-confidence segments sent if enabled, with a one-time consent dialog.
- **Storage**: SQLite DB and audio stay in `~/VaaniScript/`. No telemetry by default.
- **Retention**: config option to auto-delete source audio after N days.
- **Exported WhatsApp media caveat**: still worth a one-line disclaimer about consent when transcribing others' forwarded voice notes.

---

## 7. Error Handling

Same table as the original, minus the Hindi/Bengali-vs-Hinglish misrouting row, which no longer applies:

| Failure mode | Real cause with WhatsApp audio | Handling |
|---|---|---|
| Whisper hallucination loop | Long silence/noise-only segments | `condition_on_previous_text=False`; hard segment-length cap; repeated-ngram detector -> `[hallucination_suspected]` |
| Corrupt/partial .opus | Forwarded media that didn't fully download | `ffmpeg` probe before processing; skip + log on decode failure, never crash the batch |
| Silent/near-silent file | Background-noise-only note | VAD speech ratio near zero -> skip ASR, mark `no_speech_detected` |
| Extremely long files | Manually concatenated voice-note chains | Max duration cap (e.g. 10 min) with a clear error, not silent OOM |
| Hindi/Bengali script ambiguity | Rare cross-script noise in transcription, or genuinely mixed household speech | Flag `[lang_ambiguous]` per Section 4, surface both signals, let user override manually rather than guessing silently |
| GUI hang on large batch | Synchronous processing blocking the Qt event loop | Run pipeline in a worker thread/process; progress signals per file |

---

## 8. MVP Scope (revised)

**In scope for v0.1:**
- CLI: `vaaniscript <file_or_folder>` -> outputs `.txt` (English) + `.json` (full detail)
- Local-only faster-whisper `small` model, language search space constrained to `{hi, bn}`
- Unicode-block-based language confirmation
- IndicTrans2 standard mode for both Hindi and Bengali
- Low-confidence and lang-ambiguous flagging
- Basic `--watch` mode for a folder

**Out of scope for v0.1:**
- GUI (v0.2, same as before)
- Cloud fallback toggle (v0.3)
- Speaker diarization
- Real-time/streaming transcription
- Direct WhatsApp Desktop integration
- Any romanized/Hinglish handling (explicitly and permanently dropped per this revision, not deferred)
- Fine-tuning any model on user data

---

## 9. Rejected Alternative

**Rejected: Cloud-first architecture using Azure Speech + Azure Translator.**

Same reasoning as before — still rejected for the same three reasons (privacy premise, recurring cost, offline-usefulness), and it remains available as the opt-in fallback in Section 6. Dropping Hinglish doesn't change this tradeoff; if anything it makes the local-only path more attractive, since Hindi/Bengali standard-mode accuracy from open models is closer to commercial-API quality than the Hinglish case was, narrowing the accuracy gap that would have justified going cloud-first.

---

## 10. APIs / Libraries Reference (updated)

| Component | Package | Notes |
|---|---|---|
| ASR | `faster-whisper` | `pip install faster-whisper`; needs `ffmpeg` on PATH |
| VAD | `silero-vad` | via `torch.hub` or ONNX export |
| Denoise | `noisereduce` | pure numpy/scipy |
| Translation | `ai4bharat/indictrans2` (HuggingFace) | via `transformers` + `IndicTransToolkit`; only need `hi-en` and `bn-en` checkpoints, not the full multi-lingual set |
| ~~Transliteration~~ | ~~`indic-transliteration`~~ | **removed — no longer a dependency** |
| Audio decode | `ffmpeg-python` or raw subprocess | prefer static bundled ffmpeg binary |
| CLI | `typer` | consistent with your other Utilities tools |
| GUI | `PySide6` | for v0.2 |
| DB | `sqlite3` (stdlib) or `sqlmodel` | |
| Packaging | `pyinstaller` + GitHub Actions matrix | mirrors your existing build pipeline |

---

## 11. Milestone-Based Build Plan (revised — one fewer milestone than the original)

**M0 — Spike (2 days, down from 2-3)**
Validate Python 3.13 dependency compatibility first, then run faster-whisper on 5-10 real forwarded Hindi and Bengali voice notes (mix of clean and noisy). Confirm `small` model viability before building further.

**M1 — CLI core (1 week)**
`ffmpeg` normalize -> VAD -> faster-whisper (constrained to hi/bn) -> raw transcript + language tag. Ship `vaaniscript file.opus` dumping native-script text.

**M2 — Language routing + translation (3-4 days, down from 1 week)**
Unicode-block classifier, IndicTrans2 integration for both languages. No glossary-building work needed this time, which is the main time saving versus the original plan.

**M3 — Robustness pass (3-4 days)**
Hallucination detection, corrupt file handling, silence skipping, confidence flags, lang-ambiguity flagging.

**M4 — Batch + watch mode (2-3 days)**
`--watch` folder mode, SQLite persistence, `.srt` export.

**M5 — GUI shell (1 week)**
PySide6 wrapper: drag-drop, progress, review pane. Reuses M1-M4 core, runs in a worker thread.

**M6 — Packaging + release (2-3 days)**
PyInstaller builds for Windows and macOS, GitHub Actions matrix, first tagged release.

**M7 — Opt-in cloud fallback (stretch, later)**
Section 6 opt-in toggle for low-confidence segment re-processing.

Total core build (M0-M4) is roughly **1.5-2 weeks shorter** than the original three-language design, almost entirely from removing the Hinglish lexical classifier and glossary work in M2.

---

## 12. Risks (revised)

1. **Hindi/Bengali script-ambiguity edge cases**: rare, but a noisy segment can occasionally get misclassified between the two languages by Whisper; the Unicode cross-check catches most of these, but budget for a manual-override UI control rather than expecting 100% auto-routing accuracy.
2. **WhatsApp compression artifacts**: unchanged risk — heavily compressed, possibly re-compressed audio degrades ASR accuracy versus Whisper's published clean-audio benchmarks.
3. **Model size vs "lightweight" tension**: unchanged — `medium` model materially improves Hindi/Bengali accuracy at real CPU/RAM cost; keep this a user-facing toggle.
4. **Embedded English tokens inside Bengali/Hindi sentences**: not fully eliminated by dropping Hinglish — casual speech still mixes in English nouns/verbs. This is now a much smaller, token-level risk handled by IndicTrans2's own training rather than a dedicated subsystem, but don't expect it to be flawless; occasional mistranslated loanwords are still possible.
5. **Reduced but nonzero complexity from dropping Hinglish**: worth naming that this simplification measurably improves both build time and expected accuracy for the two supported languages, which is the direct payoff of this scope cut.

---

## 13. Repo Layout (`utilities/vaaniscript/`)

Matches the CLI-first, PyInstaller-packaged pattern of your existing Utilities tools (e.g. the WhatsApp masking CLI), so it drops into the monorepo without inventing new conventions.

```
utilities/
└── vaaniscript/
    ├── README.md                     # what it does, install, usage examples
    ├── pyproject.toml                # deps, entry point: vaaniscript = "vaaniscript.cli:app"
    ├── config.example.toml           # default config (model size, cloud fallback off, dirs)
    ├── .gitignore                    # exclude models/, *.sqlite, local audio dirs
    │
    ├── vaaniscript/                  # package root
    │   ├── __init__.py
    │   ├── cli.py                    # Typer app: transcribe / batch / watch commands
    │   ├── config.py                 # pydantic-settings model
    │   │
    │   ├── ingest/
    │   │   ├── normalize.py          # ffmpeg wrapper: opus/m4a/mp3 -> 16kHz mono wav
    │   │   └── probe.py              # corrupt-file detection before processing
    │   │
    │   ├── audio/
    │   │   ├── vad.py                # silero-vad: silence trim, chunking
    │   │   └── denoise.py            # noisereduce spectral gating
    │   │
    │   ├── asr/
    │   │   └── whisper_engine.py     # faster-whisper wrapper, hi/bn-constrained lang id,
    │   │                             #   hallucination/repeated-ngram guard
    │   │
    │   ├── lang/
    │   │   └── script_detect.py      # Unicode-block ratio check (Devanagari vs Bengali)
    │   │
    │   ├── translate/
    │   │   └── indictrans.py         # IndicTrans2 wrapper, hi->en / bn->en
    │   │
    │   ├── pipeline.py               # orchestrates ingest -> vad -> asr -> lang -> translate -> store
    │   │
    │   ├── storage/
    │   │   ├── db.py                 # SQLite schema + read/write (sqlmodel)
    │   │   └── export.py             # .txt / .srt / .json writers
    │   │
    │   └── gui/                      # v0.2, not in v0.1 build
    │       ├── main_window.py        # PySide6 shell
    │       └── worker.py             # QThread wrapper around pipeline.py
    │
    ├── models/                       # gitignored; downloaded on first run
    │   ├── faster-whisper-small/
    │   └── indictrans2-distilled/
    │
    ├── tests/
    │   ├── fixtures/                 # sample .opus files: clean hi, clean bn, noisy, corrupt, silent
    │   ├── test_pipeline.py
    │   ├── test_script_detect.py
    │   └── test_error_handling.py    # hallucination loop, corrupt file, silence cases from Section 7
    │
    ├── scripts/
    │   └── download_models.py        # first-run model fetch, called by cli.py or standalone
    │
    ├── build/
    │   └── vaaniscript.spec          # PyInstaller spec file
    │
    └── .github/
        └── workflows/
            └── build.yml            # matrix build: windows-latest, macos-latest -> release artifacts
```

**Notes on the layout:**
- `lang/` is intentionally thin (just `script_detect.py`) — this is the module that would have carried the Hinglish lexical classifier and glossary CSV in the original design; dropping Hinglish is what keeps this folder small.
- `models/` stays gitignored and populated by `scripts/download_models.py` on first run, keeping the repo itself lightweight even though the tool's runtime footprint is ~1-2GB.
- `gui/` is scaffolded now but implemented in M5 — having the folder in place from M1 makes the "CLI core first, GUI wraps it later" boundary explicit in the repo structure itself, not just in the milestone plan.
- `tests/fixtures/` should include at least one Bengali and one Hindi sample with a known corrupt file and a silence-only file, matching the failure modes named in Section 7 — worth seeding this early rather than after M3.
