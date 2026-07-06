# VaaniScript Build Tracker

| Slice | Status | Commit | Tests | Notes |
|---|---|---|---|---|
| S0 Repo foundation | Done | 8837fa9 | pytest passed | CLI skeleton, config, package layout, README, gitignore |
| S1 Ingest | Next |  |  | ffmpeg probe/normalize wrappers |
| S2 Language detection | Done | c3aac57 | 26 passed | Unicode script detector for hi/bn with unknown and ambiguous handling |
| S3 Pipeline contracts | Done | ccb6dde | 29 passed | Stable DTOs and deterministic JSON result shape |
| S4 ASR adapter | Done | 23470f9 | 33 passed | Mockable ASR boundary with lazy faster-whisper adapter |
| S5 Translation adapter | Done | <commit-hash> | 41 passed | Mockable IndicTrans2 boundary with hi/bn routing |
| S6 Audio preprocessing | Done | <commit-hash> | 43 passed | VAD/denoise boundaries, chunk-wise ASR, structured no-speech path |
| S7 Robustness guards | Next |  |  | Confidence flags, hallucination guard, duration cap, error consistency |
| S8 Batch/watch | Not started |  |  |  |
| S9 Packaging | Not started |  |  |  |
