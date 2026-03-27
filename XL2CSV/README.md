# xlsx-to-csv

A cross-platform utility that converts every worksheet in an Excel workbook into its own CSV file, with both direct CLI usage and a dependency-free terminal UI.

## Features

- One CSV per sheet, written into a folder named after the workbook
- Interactive TUI mode for selecting a workbook from the terminal
- Supports `.xlsx`, `.xlsm`, `.xltx`, and `.xltm`
- Preserves cell values as strings to avoid silent type coercion
- Writes UTF-8 with BOM so CSV files open cleanly in Excel
- Sanitises invalid filename characters automatically
- Avoids overwriting when multiple sheets resolve to the same filename
- Continues past per-sheet write failures and reports them in the summary

## Requirements

- Python 3.9+
- `pandas`
- `openpyxl`

## Installation

```bash
pip install pandas openpyxl
```

## Usage

Direct conversion:

```bash
python xlsx_to_csv.py Inventory.xlsx
```

Interactive terminal UI:

```bash
python xlsx_to_csv.py
```

Explicit TUI flag:

```bash
python xlsx_to_csv.py --tui
```

Help:

```bash
python xlsx_to_csv.py --help
```

## TUI Flow

When launched without arguments, the script:

1. Lists supported Excel workbooks in the current directory.
2. Lets you choose a workbook by number or paste a full path.
3. Runs the same conversion logic as the CLI mode.
4. Prompts to convert another workbook before exiting.

## Output

Given `Inventory.xlsx`, the tool creates:

```text
Inventory/
|- Summary.csv
|- Sales_2024.csv
`- Raw_Data.csv
```

## Data Handling

- All values are loaded with `dtype=str`
- Empty cells remain empty strings instead of `NaN`
- Output encoding is `utf-8-sig`
- Line endings are written as `\n`

## Error Handling

The tool reports clear errors for:

- Missing files
- Unsupported extensions
- Permission issues
- Corrupted or invalid Excel files
- Password-protected workbooks
- Per-sheet write failures

## Project Structure

```text
XL2CSV/
|- xlsx_to_csv.py
`- README.md
```
