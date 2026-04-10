"""
backend/pcan.py
---------------
PCAN hardware backend.

Uses the PEAK PCAN-Basic driver via python-can's 'pcan' interface.

Hardware readiness
------------------
This backend is prepared for future PCAN hardware.  It gracefully handles
the case where no PCAN hardware (or driver) is present:
  connect() returns False and populates connection_error with a clear
  diagnostic message.  No exception is raised to the caller.

To activate with real hardware:
  1. Install the PEAK PCAN-Basic driver from https://www.peak-system.com/
  2. Set config.backends.pcan.channel to e.g. "PCAN_USBBUS1"
  3. Select 'pcan' as the active backend in config.backend
"""

from __future__ import annotations

from backend.base import _SingleBusBackend


class PCANBackend(_SingleBusBackend):
    """
    Backend for PEAK PCAN hardware adapters.

    Configuration keys (under config["backends"]["pcan"]):
        channel  -- PCAN channel name, e.g. "PCAN_USBBUS1" (default)
        bitrate  -- CAN bitrate in bits/second (default 500000)
    """

    def __init__(self, config: dict) -> None:
        pcan_cfg = config.get("backends", {}).get("pcan", {})
        super().__init__(
            interface="pcan",
            channel=pcan_cfg.get("channel", "PCAN_USBBUS1"),
            bitrate=int(pcan_cfg.get("bitrate", config.get("bitrate", 500000))),
        )

    @property
    def backend_name(self) -> str:
        return "pcan"
