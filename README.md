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

## Structure

- `mermaidtopng` - Mermaid diagram image converter
- `pdfmerger` - PDF Tools GUI and related CLI utilities
- `XL2CSV` - Excel workbook to per-sheet CSV converter
- `downloadstudymaterial` - Google Drive study materials browser and ZIP downloader
- `HTMLbased-utilites` - Standalone HTML browser utilities

More utilities can be added here over time, with each one documented in its own folder.
