"""Enable ``python -m redact_secrets``."""

from redact_secrets.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
