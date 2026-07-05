"""Typer CLI for VaaniScript."""

from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .config import Settings
from .pipeline import VaaniPipeline

app = typer.Typer(
    add_completion=False,
    help="Local-first CLI scaffold for Bengali and Hindi voice-note processing.",
)


def build_pipeline() -> VaaniPipeline:
    settings = Settings()
    return VaaniPipeline(settings=settings)


@app.command()
def transcribe(source: Path) -> None:
    """Validate, probe, and normalize a single audio file."""

    result = build_pipeline().transcribe(source)
    typer.echo(result.to_json())


@app.command()
def batch(source_dir: Path) -> None:
    """Placeholder batch command."""

    result = build_pipeline().batch(source_dir)
    typer.echo(result.message)


@app.command()
def watch(source_dir: Path) -> None:
    """Placeholder watch command."""

    result = build_pipeline().watch(source_dir)
    typer.echo(result.message)


@app.command()
def version() -> None:
    """Print the current VaaniScript version."""

    typer.echo(__version__)
