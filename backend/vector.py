"""
backend/vector.py
-----------------
Vector hardware backend.

Uses Vector hardware (VN-series interfaces, CANalyzer hardware) via
python-can's 'vector' interface.

Hardware readiness
------------------
This backend is prepared for future Vector hardware.  It gracefully handles
the case where no Vector hardware (or XL Driver Library) is present:
  connect() returns False and populates connection_error with a clear
  diagnostic message.  No exception is raised to the caller.

To activate with real hardware:
  1. Install the Vector XL Driver Library from https://www.vector.com/
  2. Set config.backends.vector.channel to the correct channel index (0, 1, …)
  3. Optionally set app_name to match your CANdb++ / CANalyzer app
  4. Select 'vector' as the active backend in config.backend
"""

from __future__ import annotations

import can

from backend.base import _SingleBusBackend


class VectorBackend(_SingleBusBackend):
    """
    Backend for Vector hardware adapters (VN-series, CANalyzer-compatible).

    Configuration keys (under config["backends"]["vector"]):
        channel   -- Vector channel index, e.g. 0 (default)
        bitrate   -- CAN bitrate in bits/second (default 500000)
        app_name  -- XL Driver application name (default "ECUTool")
    """

    def __init__(self, config: dict) -> None:
        vector_cfg = config.get("backends", {}).get("vector", {})
        channel = vector_cfg.get("channel", 0)
        bitrate = int(vector_cfg.get("bitrate", config.get("bitrate", 500000)))
        app_name = vector_cfg.get("app_name", "ECUTool")
        super().__init__(
            interface="vector",
            channel=channel,
            bitrate=bitrate,
        )
        self._app_name = app_name

    def connect(self) -> bool:
        # Pass app_name to python-can's Vector interface when available
        try:
            self._bus = can.Bus(
                interface=self._interface,
                channel=self._channel,
                bitrate=self._bitrate,
                app_name=self._app_name,
            )
            self._connected = True
            self._error = None
            return True
        except TypeError:
            # Older python-can versions may not accept app_name; fall back
            return super().connect()
        except Exception as exc:
            self._error = str(exc)
            self._connected = False
            self._bus = None
            return False

    @property
    def backend_name(self) -> str:
        return "vector"
