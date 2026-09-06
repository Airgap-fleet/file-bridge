"""Regression: structured logs must not pollute stdio MCP stdout."""

from __future__ import annotations

import io
import logging
import sys

import structlog

from filesystem_mcp.server import configure_logging


def test_configure_logging_writes_to_stderr_only(monkeypatch):
    """PrintLogger must target stderr so JSON-RPC on stdout stays clean."""
    fake_out = io.StringIO()
    fake_err = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_out)
    monkeypatch.setattr(sys, "stderr", fake_err)

    configure_logging(logging.INFO)
    log = structlog.get_logger("file_bridge_audit")
    log.info("audit_probe", channel="stderr_only")

    out = fake_out.getvalue()
    err = fake_err.getvalue()
    assert out == "", f"stdout polluted by logs: {out!r}"
    assert "audit_probe" in err
    assert "stderr_only" in err