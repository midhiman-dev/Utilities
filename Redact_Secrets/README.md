# Redact Secrets

`redact-secrets` is a small, dependency-free command-line tool that scans UTF-8 text files for common credentials and replaces detected values with readable redaction markers. It is intended for safely sharing logs, configuration files, and snippets.

> Note: the current codebase is a text secret-redaction utility. It does not edit PDF vector drawings or recolour text/highlights.

## Features

- Detects common AWS, Google, GitHub, Slack, Stripe, OpenAI, Anthropic, and other provider credentials.
- Masks JWTs, bearer tokens, basic-auth URL credentials, private-key blocks, and generic key/secret assignments.
- Retains a small masked hint for most values, while fully replacing private-key blocks.
- Supports an opt-in Shannon-entropy pass for unlabelled opaque tokens.
- Writes a separate output file by default; supports explicit output paths and in-place edits.
- Works as an installable `redact-secrets` command or a standalone Windows executable.

## Quickstart

Requires Python 3.9 or newer.

```powershell
git clone <repository-url>
cd Redact_Secrets
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
redact-secrets .\example.log
```

The default output for `example.log` is `example.redacted.log`.

```powershell
# Choose an output location
redact-secrets .\config.txt --output .\safe\config.txt

# Overwrite a file (use with care)
redact-secrets .\config.txt --in-place

# Add the stricter, heuristic entropy pass
redact-secrets .\application.log --entropy --entropy-min-len 24
```

You can also run the installed package directly with Python:

```powershell
python -m redact_secrets .\example.log
```

## Standalone executable usage

Download `redact-secrets.exe` from the project's release assets, then run it directly—Python is not required:

```powershell
.\redact-secrets.exe .\example.log
.\redact-secrets.exe .\config.txt -o .\clean-config.txt
```

Use `--help` to view the available options.

## Build a Windows executable

1. Create and activate a Python virtual environment.
2. Install the package and build dependency:

   ```powershell
   pip install -r requirements.txt
   pip install -r requirements-build.txt
   ```

3. From the repository root, build a single-file executable:

   ```powershell
   pyinstaller --noconfirm --clean --onefile --name redact-secrets --paths src src\redact_secrets\__main__.py
   ```

   Or run the provided build script:

   ```powershell
   .\scripts\build_executable.ps1
   ```

4. Find the result at `dist\redact-secrets.exe`. Validate it with:

   ```powershell
   .\dist\redact-secrets.exe --help
   ```

`build/`, `dist/`, and the generated `.spec` file are ignored by Git.

## CLI flags reference

| Argument / flag | Description |
| --- | --- |
| `input` | Required path to a text file to scan. |
| `-o PATH`, `--output PATH` | Write the result to `PATH`. Defaults to `<input>.redacted<extension>`. |
| `--in-place` | Replace the input file. Cannot be combined with `--output`. |
| `--quiet` | Do not print the scan summary. |
| `--entropy` | Also inspect bare high-entropy strings. This may produce false positives. |
| `--entropy-min-len N` | Minimum token length considered by `--entropy`; default `20`. |
| `--entropy-threshold BITS` | Non-hex entropy threshold for `--entropy`; default `4.3`. |
| `-h`, `--help` | Print help and exit. |

## Development

Run the test suite after installing the package:

```powershell
python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
