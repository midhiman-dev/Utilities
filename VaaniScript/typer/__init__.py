"""Minimal Typer-compatible shim for local CLI tests and packaging."""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Callable

_OUTPUT_STREAM: StringIO | None = None


def echo(message: Any = "") -> None:
    text = str(message)
    stream = _OUTPUT_STREAM
    if stream is None:
        print(text)
        return
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")


@dataclass(slots=True)
class _CommandSpec:
    name: str
    callback: Callable[..., Any]
    help_text: str


class Typer:
    def __init__(self, *, add_completion: bool = False, help: str | None = None) -> None:
        self.add_completion = add_completion
        self.help = help or ""
        self._commands: dict[str, _CommandSpec] = {}

    def command(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            command_name = name or func.__name__
            self._commands[command_name] = _CommandSpec(
                name=command_name,
                callback=func,
                help_text=inspect.getdoc(func) or "",
            )
            return func

        return decorator

    def __call__(self, *args: Any, **kwargs: Any) -> int:
        return self.run(list(sys.argv[1:]))

    def run(self, args: list[str]) -> int:
        if not args or args[0] in {"--help", "-h"}:
            echo(self.format_help())
            return 0

        command = self._commands.get(args[0])
        if command is None:
            echo(f"Unknown command: {args[0]}")
            return 2

        try:
            parsed = self._parse_args(command.callback, args[1:])
        except ValueError as exc:
            echo(str(exc))
            return 2

        command.callback(*parsed)
        return 0

    def format_help(self) -> str:
        lines = [self.help, "", "Commands:"]
        for name in sorted(self._commands):
            help_text = self._commands[name].help_text
            lines.append(f"  {name}  {help_text}")
        return "\n".join(lines).strip()

    @staticmethod
    def _parse_args(func: Callable[..., Any], raw_args: list[str]) -> list[Any]:
        signature = inspect.signature(func)
        parameters = list(signature.parameters.values())
        required_count = len(parameters)
        if len(raw_args) != required_count:
            raise ValueError(f"Expected {required_count} argument(s); got {len(raw_args)}.")

        parsed: list[Any] = []
        for parameter, raw in zip(parameters, raw_args):
            annotation = parameter.annotation
            if annotation is Path or annotation == "Path":
                parsed.append(Path(raw))
            else:
                parsed.append(raw)
        return parsed
