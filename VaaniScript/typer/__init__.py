"""Minimal Typer-compatible shim for Slice S0."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

import click

echo = click.echo


class Typer:
    def __init__(self, *, add_completion: bool = False, help: str | None = None) -> None:
        self.add_completion = add_completion
        self._group = click.Group(help=help)
        self.name = self._group.name

    def command(self, name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            command_name = name or func.__name__
            params = []
            for parameter in inspect.signature(func).parameters.values():
                annotation = parameter.annotation
                if annotation is Path:
                    param_type = click.Path(path_type=Path)
                else:
                    param_type = click.STRING
                params.append(click.Argument([parameter.name], type=param_type))

            command = click.Command(
                name=command_name,
                callback=func,
                params=params,
                help=inspect.getdoc(func),
            )
            self._group.add_command(command)
            return func

        return decorator

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._group(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._group, item)
