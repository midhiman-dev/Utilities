"""Minimal pydantic-settings-compatible shim for Slice S0."""

from __future__ import annotations


class SettingsConfigDict(dict):
    """Dictionary container matching the pydantic-settings API name."""


class BaseSettings:
    """Marker base class for local settings models."""
