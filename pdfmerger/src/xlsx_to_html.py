"""
CLI tool to convert Excel (.xlsx) files to HTML with embedded styling.
Generates a single HTML file with a table of contents and each sheet as a section.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

import pandas as pd


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert Excel (.xlsx) files to HTML with table of contents."
    )
    parser.add_argument(
        "input",
        help="Input Excel file path (.xlsx)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output HTML file path (default: derived from input name)",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="Disable Table of Contents generation",
    )
    parser.add_argument(
        "--index",
        action="store_true",
        help="Include DataFrame index in HTML tables",
    )
    return parser.parse_args(argv)


def validate_input(input_path: Path) -> None:
    """Validate that the input file exists and has .xlsx extension."""
    if not input_path.exists():
        print(f"Error: Input file does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    if not input_path.is_file():
        print(f"Error: Input path is not a file: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    if input_path.suffix.lower() != ".xlsx":
        print(f"Error: Input file must be .xlsx format, got: {input_path.suffix}", file=sys.stderr)
        sys.exit(1)


def derive_output_path(input_path: Path, output_arg: str | None) -> Path:
    """Derive output HTML path from input if not provided."""
    if output_arg:
        return Path(output_arg).resolve()
    return input_path.with_suffix(".html")


def sanitize_anchor(sheet_name: str) -> str:
    """Convert sheet name to a valid HTML anchor ID."""
    # Replace spaces with hyphens, remove special characters
    anchor = re.sub(r'[^\w\s-]', '', sheet_name)
    anchor = re.sub(r'[-\s]+', '-', anchor)
    return f"sheet-{anchor.strip('-')}"


def read_excel_sheets(input_path: Path) -> List[Tuple[str, pd.DataFrame]]:
    """Read all sheets from Excel file, preserving order."""
    try:
        # Read all sheets using openpyxl engine
        sheets_dict = pd.read_excel(
            input_path,
            sheet_name=None,
            engine="openpyxl",
        )
        # Return as list of tuples to preserve order
        return list(sheets_dict.items())
    except FileNotFoundError:
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error reading Excel file: {exc}", file=sys.stderr)
        sys.exit(1)


def get_css_styles() -> str:
    """Return embedded CSS styles for the HTML document."""
    return """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                         "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
            max-width: 100%;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            color: #2c3e50;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #3498db;
        }
        
        h2 {
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            padding: 10px 0;
            border-bottom: 2px solid #ecf0f1;
        }
        
        .toc {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
            border-left: 4px solid #3498db;
        }
        
        .toc h2 {
            margin-top: 0;
            border-bottom: none;
        }
        
        .toc ul {
            list-style: none;
            padding-left: 0;
        }
        
        .toc li {
            padding: 8px 0;
        }
        
        .toc a {
            color: #2980b9;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
        }
        
        .toc a:hover {
            color: #3498db;
            text-decoration: underline;
        }
        
        .sheet-section {
            margin-bottom: 50px;
            padding-bottom: 30px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .sheet-section:last-child {
            border-bottom: none;
        }
        
        .table-wrapper {
            overflow-x: auto;
            margin-top: 20px;
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            background-color: white;
        }
        
        .data-table thead {
            position: sticky;
            top: 0;
            background-color: #34495e;
            color: white;
            z-index: 10;
        }
        
        .data-table th {
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            border: 1px solid #2c3e50;
        }
        
        .data-table td {
            padding: 10px 15px;
            border: 1px solid #ddd;
        }
        
        .data-table tbody tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .data-table tbody tr:hover {
            background-color: #f1f1f1;
        }
        
        .empty-sheet {
            color: #7f8c8d;
            font-style: italic;
            padding: 20px;
            background-color: #ecf0f1;
            border-radius: 5px;
        }
        
        @media print {
            body {
                background-color: white;
                padding: 0;
            }
            
            .container {
                box-shadow: none;
                padding: 0;
            }
            
            .data-table thead {
                position: static;
            }
        }
    </style>
    """


def generate_toc(sheets: List[Tuple[str, pd.DataFrame]]) -> str:
    """Generate HTML table of contents."""
    toc_items = []
    for sheet_name, _ in sheets:
        anchor = sanitize_anchor(sheet_name)
        # HTML escape the sheet name
        escaped_name = sheet_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        toc_items.append(f'            <li><a href="#{anchor}">{escaped_name}</a></li>')
    
    return f"""    <div class="toc">
        <h2>Table of Contents</h2>
        <ul>
{chr(10).join(toc_items)}
        </ul>
    </div>
"""


def generate_sheet_section(sheet_name: str, df: pd.DataFrame, include_index: bool) -> str:
    """Generate HTML section for a single sheet."""
    anchor = sanitize_anchor(sheet_name)
    # HTML escape the sheet name
    escaped_name = sheet_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    section_html = f'    <div class="sheet-section" id="{anchor}">\n'
    section_html += f'        <h2>{escaped_name}</h2>\n'
    
    if df.empty:
        section_html += '        <div class="empty-sheet">No data in this sheet.</div>\n'
    else:
        # Convert DataFrame to HTML table
        table_html = df.to_html(
            index=include_index,
            border=0,
            classes="data-table",
            na_rep="",  # Empty string for NaN values
        )
        section_html += '        <div class="table-wrapper">\n'
        section_html += f'            {table_html}\n'
        section_html += '        </div>\n'
    
    section_html += '    </div>\n'
    return section_html


def generate_html(
    sheets: List[Tuple[str, pd.DataFrame]],
    input_filename: str,
    include_toc: bool,
    include_index: bool,
) -> str:
    """Generate complete HTML document."""
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '    <meta charset="UTF-8">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'    <title>{input_filename} - Excel to HTML</title>',
        get_css_styles(),
        '</head>',
        '<body>',
        '    <div class="container">',
        f'        <h1>{input_filename}</h1>',
    ]
    
    # Add table of contents if requested
    if include_toc and sheets:
        html_parts.append(generate_toc(sheets))
    
    # Add sheet sections
    if not sheets:
        html_parts.append('        <div class="empty-sheet">No sheets found in workbook.</div>')
    else:
        for sheet_name, df in sheets:
            html_parts.append(generate_sheet_section(sheet_name, df, include_index))
    
    html_parts.extend([
        '    </div>',
        '</body>',
        '</html>',
    ])
    
    return '\n'.join(html_parts)


def write_html_file(output_path: Path, html_content: str) -> None:
    """Write HTML content to file with UTF-8 encoding."""
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write HTML file
        output_path.write_text(html_content, encoding='utf-8')
    except Exception as exc:
        print(f"Error writing output file: {exc}", file=sys.stderr)
        sys.exit(1)


def run(args: argparse.Namespace) -> int:
    """Main execution function."""
    try:
        input_path = Path(args.input).resolve()
        validate_input(input_path)

        output_path = derive_output_path(input_path, args.output)

        print(f"Reading Excel file: {input_path}")
        sheets = read_excel_sheets(input_path)

        if not sheets:
            print("Warning: No sheets found in workbook.", file=sys.stderr)
        else:
            print(f"Found {len(sheets)} sheet(s)")

        print("Generating HTML...")
        html_content = generate_html(
            sheets=sheets,
            input_filename=input_path.name,
            include_toc=not args.no_toc,
            include_index=args.index,
        )

        write_html_file(output_path, html_content)
        print(f"✓ Successfully created HTML file: {output_path.absolute()}")
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
