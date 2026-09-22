"""Deprecated automated login.

Use scripts/login.py for manual Cloudflare + sign-in bootstrap.
Page detection lives in src/session.py.
"""

from .session import PageKind, SessionProbe

__all__ = ["PageKind", "SessionProbe"]
