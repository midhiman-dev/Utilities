# WhatsApp PII Masker

A Windows desktop GUI and command-line tool to mask phone numbers in WhatsApp chat exports. It uses a two-stage approach (regex-based candidate matching + digit-count validation) to mask digits to 'X' while preserving all formatting, spaces, brackets, and emojis.

## Project Structure

```text
WhatsAppPhoneMask/
├── src/
│   ├── __init__.py
│   ├── mask_core.py      # Core masking logic (shared)
│   ├── cli.py            # CLI entrypoint (identical flags/behavior)
│   └── gui.py            # Windows Tkinter GUI application
├── tests/
│   ├── conftest.py       # Pytest configuration
│   └── test_mask_core.py # Core unit and regression tests
├── build/
│   ├── version_info.txt  # Executable version metadata
│   ├── build_cli.spec    # PyInstaller spec for CLI
│   └── build_gui.spec    # PyInstaller spec for GUI
├── assets/
│   └── icon.ico          # Application icon
├── requirements.txt      # Dev/build dependencies
└── README.md
```

---

## 1. Running the CLI directly with Python

The CLI has identical flags and behavior to the original `phone_mask.py` script.

### Usage Examples

```bash
# Basic usage: writes to <input>.masked.txt
python src/cli.py chat.txt

# Custom output path
python src/cli.py chat.txt -o clean.txt

# Overwrite input file in-place
python src/cli.py chat.txt --in-place

# Pipe stdin to stdout
cat chat.txt | python src/cli.py

# Mask a single string directly
python src/cli.py --text "Call +91 98450 12345"

# Loose mode (also mask numbers without '+' or '00' prefix)
python src/cli.py chat.txt --loose

# Customize digit counts
python src/cli.py chat.txt --min-digits 8 --max-digits 13

# Run built-in self-tests/regression checks
python src/cli.py --selftest
```

---

## 2. Running and Building the GUI Locally

The GUI is written using Python's standard library `tkinter/ttk` with a custom dark theme. It operates on a background thread using queue polling to keep the UI fully responsive even when masking multi-gigabyte files.

### Running the GUI

Run the GUI directly from the terminal:
```bash
python src/gui.py
```

### Local Packaging with PyInstaller

To build the self-contained `.exe` binaries locally, first install the dependencies:
```bash
pip install -r requirements.txt
```

Then run PyInstaller using the spec files:
```bash
# Build the CLI exe (dist/phone_mask.exe)
pyinstaller build/build_cli.spec

# Build the GUI exe (dist/WhatsApp PII Masker.exe)
pyinstaller build/build_gui.spec
```

Both build commands use the `--noupx` flag to prevent common antivirus false positives associated with UPX packer heuristics.

---

## 3. GitHub Actions CI Build Workflow

The repository includes a GitHub Actions CI workflow to build the executables automatically:
- Location: `.github/workflows/build-whatsapp-phonemask.yml`
- Triggers: Runs automatically on push/PR modifying files in `WhatsAppPhoneMask/` or the workflow itself.
- Artifacts: Builds the CLI and GUI executables, calculates their SHA256 checksums, and uploads them to the run's **Artifacts** section. You can download the pre-compiled `.exe` files directly from the GHA run page.

---

## 4. Windows SmartScreen and Antivirus Notes

### SmartScreen "Unknown Publisher" Warnings
Because these executables are not signed with a paid Authenticode Certificate, Windows SmartScreen will likely display a **"Windows protected your PC / Unknown Publisher"** warning when you run the `.exe` for the first time.
- **Why this happens:** SmartScreen blocks all unrecognized binaries unless they are signed by a trusted certificate authority (CA) and have established reputation.
- **How to bypass:** Click **"More Info"** on the popup, and then click **"Run anyway"**.

### Anti-Virus/Windows Defender False Positives
Occasionally, heuristic scanning from Windows Defender or third-party AVs flags Python executables compiled with PyInstaller.
- **Manual Whitelisting:** If Windows Defender flags the `.exe`, you can submit it to Microsoft for analysis and whitelisting at:
  [Microsoft Security Intelligence File Submission](https://www.microsoft.com/wdsi/filesubmission)
- **Code Signing (For Developers):** To sign the binary, you can use the commented-out signing step in the GitHub Actions workflow using `signtool.exe`. You will need to obtain a certificate from a trusted public CA (e.g. DigiCert, Sectigo, etc., or use services like SignPath.io for open-source projects) and add its base64 PFX data to your repository secrets.
