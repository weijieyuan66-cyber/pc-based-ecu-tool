"""
backend/virtual.py
------------------
Virtual CAN backend for development, self-test, and regression testing.

Uses python-can's in-process virtual interface.  No hardware required.

Design note
-----------
The virtual interface requires two separate Bus instances on the same channel
(one for TX, one for RX).  A single Bus instance does not loop back frames
to itself.  This is a python-can virtual-interface requirement, not a design
choice.
"""

from __future__ import annotations

from typing import Optional

import can

from backend.base import CANBackend


class VirtualBackend(CANBackend):
    """
    Backend backed by python-can's virtual interface.

    Acts as the primary mode for all development and regression testing.
    connect() always succeeds (no hardware dependency).
    """

    def __init__(self, config: dict) -> None:
        virtual_cfg = config.get("backends", {}).get("virtual", {})
        # Backward-compatible: accept top-level 'channel' key too
        self._channel: str = (
            virtual_cfg.get("channel")
            or config.get("channel", "test_channel")
        )
        self._rx_bus: Optional[can.BusABC] = None
        self._tx_bus: Optional[can.BusABC] = None
        self._connected: bool = False
        self._error: Optional[str] = None

    @property
    def backend_name(self) -> str:
        return "virtual"

    def connect(self) -> bool:
        try:
            self._rx_bus = can.Bus(interface="virtual", channel=self._channel)
            self._tx_bus = can.Bus(interface="virtual", channel=self._channel)
            self._connected = True
            self._error = None
            return True
        except Exception as exc:
            self._error = str(exc)
            self._connected = False
            self._rx_bus = None
            self._tx_bus = None
            return False

    def disconnect(self) -> None:
        for bus in (self._tx_bus, self._rx_bus):
            if bus is not None:
                try:
                    bus.shutdown()
                except Exception:
                    pass
        self._rx_bus = None
        self._tx_bus = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def connection_error(self) -> Optional[str]:
        return self._error

    def send(self, msg: can.Message) -> None:
        if self._tx_bus is None:
            raise RuntimeError("Virtual backend is not connected.")
        self._tx_bus.send(msg)

    def recv(self, timeout: float) -> Optional[can.Message]:
        if self._rx_bus is None:
            raise RuntimeError("Virtual backend is not connected.")
        return self._rx_bus.recv(timeout=timeout)

    @property
    def channel(self) -> str:
        """The virtual channel name in use (for self-test orchestration)."""
        return self._channel
