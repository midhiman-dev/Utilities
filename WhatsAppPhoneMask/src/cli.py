#!/usr/bin/env python3
"""
cli.py - Command-line interface for the WhatsApp PII Masker.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Import core masking functions
from mask_core import mask_phone_numbers, process_stream, run_selftest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mask phone numbers in WhatsApp chat exports or any text file."
    )
    parser.add_argument('input', nargs='?', help="Input file (omit to read stdin)")
    parser.add_argument('-o', '--output',
                         help="Output file (default: <input>.masked.txt, or stdout for stdin)")
    parser.add_argument('--in-place', action='store_true', help="Overwrite the input file")
    parser.add_argument('--text', help="Mask a single string instead of a file, print result")
    parser.add_argument('--loose', action='store_true',
                         help="Also mask digit groups without a leading '+'/'00' "
                              "(catches domestic formats like '(123) 456-7890', "
                              "but more prone to false positives on IDs/codes)")
    parser.add_argument('--min-digits', type=int, default=7,
                         help="Minimum digits to count as a phone number (default 7)")
    parser.add_argument('--max-digits', type=int, default=15,
                         help="Maximum digits to count as a phone number (default 15, E.164 max)")
    parser.add_argument('-q', '--quiet', action='store_true', help="Suppress the summary line")
    parser.add_argument('--selftest', action='store_true', help="Run built-in edge-case tests and exit")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(0 if run_selftest() else 1)

    mask_kwargs = dict(
        min_digits=args.min_digits,
        max_digits=args.max_digits,
        require_plus=not args.loose,
    )

    if args.text is not None:
        masked, n = mask_phone_numbers(args.text, **mask_kwargs)
        print(masked)
        if not args.quiet:
            print(f"# masked {n} number(s)", file=sys.stderr)
        return

    if args.input is None:
        total = process_stream(sys.stdin, sys.stdout, **mask_kwargs)
        if not args.quiet:
            print(f"# masked {total} number(s)", file=sys.stderr)
        return

    in_path = Path(args.input)
    if not in_path.exists():
        parser.error(f"Input file not found: {in_path}")

    if args.in_place:
        out_path = in_path
        tmp_path = in_path.with_suffix(in_path.suffix + '.tmp')
        with in_path.open('r', encoding='utf-8', errors='replace') as f_in, \
             tmp_path.open('w', encoding='utf-8') as f_out:
            total = process_stream(f_in, f_out, **mask_kwargs)
        tmp_path.replace(out_path)
    else:
        out_path = Path(args.output) if args.output else in_path.with_name(
            in_path.stem + '.masked' + in_path.suffix
        )
        with in_path.open('r', encoding='utf-8', errors='replace') as f_in, \
             out_path.open('w', encoding='utf-8') as f_out:
            total = process_stream(f_in, f_out, **mask_kwargs)

    if not args.quiet:
        print(f"Masked {total} phone number(s).")
        print(f"Output written to: {out_path}")


if __name__ == "__main__":
    main()
