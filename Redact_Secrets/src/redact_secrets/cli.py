"""Command-line interface for redact-secrets."""

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional, Sequence

from .core import redact_high_entropy, redact_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Detect and mask secrets in a UTF-8 text file.")
    parser.add_argument("input", type=Path, help="path to the input text file")
    parser.add_argument("-o", "--output", type=Path, help="output path (default: <input>.redacted<ext>)")
    parser.add_argument("--in-place", action="store_true", help="overwrite the input file")
    parser.add_argument("--quiet", action="store_true", help="suppress the summary report")
    parser.add_argument("--entropy", action="store_true", help="also mask bare high-entropy tokens; may produce false positives")
    parser.add_argument("--entropy-min-len", type=int, default=20, metavar="N", help="minimum token length for entropy detection (default: 20)")
    parser.add_argument("--entropy-threshold", type=float, default=4.3, metavar="BITS", help="non-hex entropy threshold in bits/character (default: 4.3)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI and return a process status code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.in_place and args.output:
        parser.error("--in-place cannot be used with --output")
    if args.entropy_min_len < 1:
        parser.error("--entropy-min-len must be at least 1")
    if args.entropy_threshold < 0:
        parser.error("--entropy-threshold cannot be negative")
    if not args.input.is_file():
        print(f"Error: input file not found or is not a file: {args.input}", file=sys.stderr)
        return 1
    try:
        text = args.input.read_text(encoding="utf-8", errors="replace")
        redacted, findings = redact_text(text)
        if args.entropy:
            redacted, entropy_findings = redact_high_entropy(redacted, args.entropy_min_len, args.entropy_threshold)
            findings.extend(entropy_findings)
        output = args.input if args.in_place else args.output or args.input.with_suffix(f".redacted{args.input.suffix}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(redacted, encoding="utf-8")
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"Scanned: {args.input}\nOutput:  {output}")
        if findings:
            print(f"Redacted {len(findings)} secret(s):")
            for label, count in Counter(findings).items():
                print(f"  - {label}: {count}")
        else:
            print("No secrets detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
