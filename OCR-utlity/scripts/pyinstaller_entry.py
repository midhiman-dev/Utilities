"""Stable import entry point used only by PyInstaller.

Executing a package's ``__main__.py`` as a script loses its package context,
so the frozen application imports the installed package explicitly instead.
"""

from ocr_utility.cli import main

raise SystemExit(main())
