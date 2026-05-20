"""Compatibility entrypoint for older deployments using `server:app`."""

from app.main import app


__all__ = ["app"]
