"""
backend/
--------
Multi-backend abstraction layer for CAN hardware access.

Provides a unified CANBackend interface so that UI, decode, and rule layers
never depend directly on PCAN, Vector, or any other vendor-specific API.

Supported backends
------------------
  virtual   -- python-can in-process virtual bus (development / self-test)
  pcan      -- PEAK PCAN hardware via python-can pcan interface
  vector    -- Vector hardware via python-can vector interface

Usage
-----
    from backend.factory import BackendFactory
    backend = BackendFactory.create(config)
    ok = backend.connect()
"""

from backend.base import CANBackend
from backend.factory import BackendFactory

__all__ = ["CANBackend", "BackendFactory"]
