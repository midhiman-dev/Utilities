"""Testing helpers exposed by the local Typer shim."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any

import typer


@dataclass(slots=True)
class Result:
    exit_code: int
    stdout: str
    exception: Exception | None = None


class CliRunner:
    def invoke(self, app: Any, args: list[str] | None = None) -> Result:
        stream = StringIO()
        previous_stream = typer._OUTPUT_STREAM
        typer._OUTPUT_STREAM = stream
        try:
            exit_code = app.run(args or [])
            return Result(exit_code=exit_code, stdout=stream.getvalue())
        except Exception as exc:
            return Result(exit_code=1, stdout=stream.getvalue(), exception=exc)
        finally:
            typer._OUTPUT_STREAM = previous_stream


__all__ = ["CliRunner", "Result"]
