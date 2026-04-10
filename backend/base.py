"""
backend/base.py
---------------
Abstract base class for all CAN backend implementations.

Design principles
-----------------
- CANBackend is the ONLY interface that UI, decode, and rule layers use.
  No vendor-specific import (pcan, vector, etc.) is ever made outside the
  backend package.

- _SingleBusBackend is a shared implementation for hardware backends that
  wrap a single python-can Bus instance (PCAN, Vector).  It avoids
  duplicating connect/disconnect/send/recv logic across PCAN and Vector.

- VirtualBackend is separate because it needs two bus instances for the
  virtual interface (one TX, one RX — required by the python-can virtual
  interface design).

Backend contract
----------------
  connect()         Open the bus.  Returns True on success, False on failure
                    (e.g. hardware not present).  Never raises.
  disconnect()      Close the bus.  Safe to call when already disconnected.
  is_connected      True iff the bus is open and ready for send/recv.
  connection_error  Last error string when connect() returned False, else None.
  backend_name      Short lowercase identifier: 'virtual', 'pcan', 'vector'.
  send(msg)         Transmit a can.Message.  Raises RuntimeError if not connected.
  recv(timeout)     Block up to timeout seconds for a frame.
                    Returns can.Message or None (timeout).
                    Raises RuntimeError if not connected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import can


class CANBackend(ABC):
    """
    Unified CAN bus interface.

    All UI and core logic must use only this interface.
    Concrete implementations live in backend/virtual.py, backend/pcan.py,
    and backend/vector.py.
    """

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Short lowercase identifier, e.g. 'virtual', 'pcan', 'vector'."""

    @abstractmethod
    def connect(self) -> bool:
        """
        Open the underlying bus.

        Returns True on success.
        Returns False (never raises) if the bus cannot be opened
        (e.g. driver not installed, hardware not present).
        Populates connection_error on failure.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the underlying bus. Safe to call when already disconnected."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True iff the bus is open and ready."""

    @property
    def connection_error(self) -> Optional[str]:
        """
        The last error message when connect() returned False.
        None when connected or not yet attempted.
        Subclasses override when they track error state.
        """
        return None

    @abstractmethod
    def send(self, msg: can.Message) -> None:
        """
        Transmit a CAN frame.

        Raises
        ------
        RuntimeError
            If the backend is not connected.
        """

    @abstractmethod
    def recv(self, timeout: float) -> Optional[can.Message]:
        """
        Block up to *timeout* seconds waiting for a CAN frame.

        Returns the frame or None on timeout.

        Raises
        ------
        RuntimeError
            If the backend is not connected.
        """


class _SingleBusBackend(CANBackend):
    """
    Shared implementation for hardware backends backed by a single python-can Bus.

    Used by PCANBackend and VectorBackend to avoid duplicating connect /
    disconnect / send / recv logic.  Subclasses only need to provide:
      - backend_name   property
      - __init__       (call super().__init__(interface, channel, bitrate))

    Not intended for direct use outside this package.
    """

    def __init__(self, interface: str, channel, bitrate: int) -> None:
        self._interface = interface
        self._channel = channel
        self._bitrate = bitrate
        self._bus: Optional[can.BusABC] = None
        self._connected: bool = False
        self._error: Optional[str] = None

    def connect(self) -> bool:
        try:
            self._bus = can.Bus(
                interface=self._interface,
                channel=self._channel,
                bitrate=self._bitrate,
            )
            self._connected = True
            self._error = None
            return True
        except Exception as exc:
            self._error = str(exc)
            self._connected = False
            self._bus = None
            return False

    def disconnect(self) -> None:
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def connection_error(self) -> Optional[str]:
        return self._error

    def send(self, msg: can.Message) -> None:
        if self._bus is None:
            raise RuntimeError(f"{self.backend_name} backend is not connected.")
        self._bus.send(msg)

    def recv(self, timeout: float) -> Optional[can.Message]:
        if self._bus is None:
            raise RuntimeError(f"{self.backend_name} backend is not connected.")
        return self._bus.recv(timeout=timeout)
