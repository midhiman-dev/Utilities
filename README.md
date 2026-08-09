# Utilities

This repository is a collection of small, focused utilities. Each utility lives in its own folder and has its own README with setup, usage, and implementation details.

## Utilities

### Mermaid Diagram to JPG/PNG Converter

Location: [`mermaidtopng`](./mermaidtopng/)

A lightweight Windows desktop utility for converting Mermaid diagrams into image files with live preview and export options.

Documentation: [`mermaidtopng/README.md`](./mermaidtopng/README.md)
Release: [`v1.0.0`](https://github.com/midhiman-dev/Utilities/releases/tag/v1.0.0)
Download: [`MermaidPng.exe`](https://github.com/midhiman-dev/Utilities/releases/download/v1.0.0/MermaidPng.exe)

### PDF Tools GUI

Location: [`pdfmerger`](./pdfmerger/)

A Windows desktop utility for merging, optimizing, and compressing PDFs, with additional Excel-to-HTML and backlog DOCX-to-Excel helpers exposed through the same GUI.

Documentation: [`pdfmerger/README.md`](./pdfmerger/README.md)
Release: [`pdftools-v1.0.0`](https://github.com/midhiman-dev/Utilities/releases/tag/pdftools-v1.0.0)
Download: [`pdf_tools_gui.exe`](https://github.com/midhiman-dev/Utilities/releases/download/pdftools-v1.0.0/pdf_tools_gui.exe)

### Excel Workbook to CSV Converter

Location: [`XL2CSV`](./XL2CSV/)

A Python utility with both CLI and terminal UI modes that reads an Excel workbook and exports every worksheet to its own CSV file in an output folder named after the workbook. It supports `.xlsx`, `.xlsm`, `.xltx`, and `.xltm`, preserves values as strings, writes UTF-8 with BOM for Excel compatibility, sanitises invalid filename characters, and avoids overwriting when sheet names collide.

Documentation: [`XL2CSV/README.md`](./XL2CSV/README.md)

Quick usage:

```bash
python XL2CSV/xlsx_to_csv.py <file.xlsx>
```

Requirements:

```bash
pip install pandas openpyxl
```

### Study Materials Downloader

Location: [`downloadstudymaterial`](./downloadstudymaterial/)

A Google Drive utility with both web and CLI interfaces for browsing Drive folders, previewing supported files, searching by filename across Drive, downloading single files, and packaging full folders or selected items into ZIP archives using the read-only Google Drive API.

Documentation: [`downloadstudymaterial/README.md`](./downloadstudymaterial/README.md)

### HTML-based Utilities

Location: [`HTMLbased-utilites`](./HTMLbased-utilites/)

Small standalone browser utilities that run directly from local HTML files.

Hosted site: [mi-dhiman-utilities.netlify.app](https://mi-dhiman-utilities.netlify.app/)

Files:

- [`md-viewer.html`](./HTMLbased-utilites/md-viewer.html) - Markdown file viewer with rendered preview and table of contents
- [`mermaid-viewer.html`](./HTMLbased-utilites/mermaid-viewer.html) - Mermaid diagram editor with live preview and PNG export

### Redact Secrets

Location: [`Redact_Secrets`](./Redact_Secrets/)

A dependency-free Python CLI that finds and masks sensitive values in UTF-8 text files before they are shared. It detects common cloud and LLM-provider keys, JWTs, bearer tokens, basic-auth URL credentials, private-key blocks, and generic secret assignments. An optional entropy pass can detect unlabelled opaque tokens.

Documentation: [`Redact_Secrets/README.md`](./Redact_Secrets/README.md)

Quick usage:

```bash
pip install -r Redact_Secrets/requirements.txt
redact-secrets application.log
```

The project also includes a reproducible PyInstaller build script for a standalone Windows executable.

### Secure LLM Harness

Location: [`SecureLLMHarness`](./SecureLLMHarness/)

`SecureLLMHarness` is a cross-platform .NET 8 CLI for validating OpenAI-compatible chat-completion endpoints across OpenAI, Azure OpenAI, OpenRouter, Groq, and local services. It supports single tests and CSV batches, validates a deterministic JSON response, reports latency and sanitized failures, and handles Ctrl+C cancellation.

Documentation: [`SecureLLMHarness/README.md`](./SecureLLMHarness/README.md)

Quick usage:

```bash
cd SecureLLMHarness
dotnet restore
dotnet run -- --provider OpenAI --url https://api.openai.com/v1 --model gpt-4o-mini --api-key-env OPENAI_API_KEY
dotnet run -- --csv sample-tests.csv --timeout 45 --verbose
```

API keys are never written to logs, exception messages, result files, or the repository. For Azure OpenAI, use the configured deployment name in the CSV's `Model` column; embedding deployments require a separate embeddings request.

### VaaniScript

Location: [`VaaniScript`](./VaaniScript/)

A local-first Python CLI foundation for Bengali and Hindi voice-note processing. It validates and normalises supported audio files, provides VAD, denoising, ASR, and translation adapter boundaries, and returns a stable JSON result contract. Version 0.1 is a scaffold: `version` is fully implemented, while real ASR/translation integrations and batch/watch workflows remain future work.

Documentation: [`VaaniScript/README.md`](./VaaniScript/README.md)

Quick usage:

```bash
cd VaaniScript
py -3.13 -m pip install -e .[dev]
vaaniscript version
```

### WhatsApp PII Masker

Location: [`WhatsAppPhoneMask`](./WhatsAppPhoneMask/)

A Windows GUI and CLI utility that masks phone numbers in WhatsApp chat exports. It preserves surrounding formatting, whitespace, brackets, and emojis while replacing digits with `X`. It supports file, standard-input, and single-text workflows, configurable digit ranges, a loose matching mode, PyInstaller builds, and a GitHub Actions build workflow.

Documentation: [`WhatsAppPhoneMask/README.md`](./WhatsAppPhoneMask/README.md)

Quick usage:

```bash
python WhatsAppPhoneMask/src/cli.py chat.txt
python WhatsAppPhoneMask/src/gui.py
```

## Structure

- `mermaidtopng` - Mermaid diagram image converter
- `pdfmerger` - PDF Tools GUI and related CLI utilities
- `XL2CSV` - Excel workbook to per-sheet CSV converter
- `downloadstudymaterial` - Google Drive study materials browser and ZIP downloader
- `HTMLbased-utilites` - Standalone HTML browser utilities
- `Redact_Secrets` - Text-file secret detection and redaction CLI
- `VaaniScript` - Local-first Bengali/Hindi voice-note processing CLI foundation
- `WhatsAppPhoneMask` - WhatsApp phone-number masking GUI and CLI
- `SecureLLMHarness` - Secure .NET 8 LLM chat-completion testing harness

More utilities can be added here over time, with each one documented in its own folder.
