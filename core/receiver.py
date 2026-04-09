"""
core/receiver.py
----------------
CAN receive module for the PC-based ECU communication tool.

Current phase: virtual self-test only (no physical hardware).

Design principles
-----------------
- The bus object is created OUTSIDE this class and passed in.
  This keeps hardware initialisation in one place (main.py) and makes
  the receiver independently testable with any bus — virtual or real.

- The receive loop is intentionally blocking and single-threaded.
  No threading in Phase 1. Simple is correct here.

- The console output format is fixed and practical:
    [RX] HH:MM:SS.mmm  ID=XXX  DLC=N  Data=XX XX XX ...

- Switching from virtual to real hardware requires zero changes here.
  Only the bus object passed in changes.

Out of scope (do not add):
- ISO-TP / UDS framing
- DBC decoding (placeholder in dbc/ directory)
- Periodic TX scheduling
- Any ECU control logic
"""

import can
import datetime
import logging
from typing import Any, Optional


class CANReceiver:
    """
    Blocking CAN frame receiver.

    Reads raw CAN frames from an already-initialised python-can Bus
    and prints each frame to the console. Optionally writes to a logger.

    Parameters
    ----------
    bus : can.BusABC
        An open python-can bus object. Created by the caller (main.py).
        Must be shut down by the caller after stop() returns.
    config : dict
        Full application config dict loaded from settings.json.
        Used only to read rx_timeout_s.
    logger : logging.Logger
        Standard Python logger for diagnostic messages (not frame data).
    """

    def __init__(self, bus: can.BusABC, config: dict, logger: logging.Logger) -> None:
        self.bus = bus
        self.config = config
        self.logger = logger

        # How long bus.recv() blocks waiting for a message before looping.
        # Shorter = more responsive to Ctrl+C. 1.0 s is a safe default.
        self._rx_timeout_s: float = float(config.get("rx_timeout_s", 1.0))

        # Count received frames for the session summary line.
        self._rx_count: int = 0

        self.logger.info(
            "CANReceiver ready | interface=%s  channel=%s  rx_timeout=%.1fs",
            config.get("interface", "?"),
            config.get("channel", "?"),
            self._rx_timeout_s,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Enter the blocking receive loop.

        Runs until the user presses Ctrl+C.
        Prints every received frame to stdout in a fixed, readable format.

        This method is intentionally simple. No threading, no queues.
        Threading is added only when TX-while-RX requires it (next phase).
        """
        self.logger.info("RX loop starting. Press Ctrl+C to stop.")
        print("\n" + "=" * 60)
        print("  CAN Receiver — listening for frames")
        print(f"  Interface : {self.config.get('interface')}")
        print(f"  Channel   : {self.config.get('channel')}")
        print(f"  Mode      : {self.config.get('app_mode')}")
        print("=" * 60)
        print("  Timestamp        ID       DLC  Data (hex)")
        print("-" * 60)

        self._rx_count = 0

        try:
            while True:
                msg = self.bus.recv(timeout=self._rx_timeout_s)

                if msg is None:
                    # Timeout — no message arrived in this window.
                    # Loop again. This also serves as the Ctrl+C check point.
                    continue

                self._rx_count += 1
                self._print_frame(msg)

        except KeyboardInterrupt:
            print("-" * 60)
            print(f"  Stopped by user. Total frames received: {self._rx_count}")
            print("=" * 60 + "\n")
            self.logger.info("RX loop stopped by user. Total RX frames: %d", self._rx_count)

    def stop(self) -> None:
        """
        Signal the receive loop to stop.

        In Phase 1 (blocking loop), Ctrl+C is the primary stop mechanism.
        This method exists so main.py has a consistent API to call,
        and so Phase 2 (threaded) can set a stop event here without
        changing any callers.
        """
        self.logger.info("CANReceiver.stop() called.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_frame(msg: can.Message) -> str:
        """
        Format a single CAN frame as a fixed-width console line.

        Output example (standard 11-bit ID):
            [RX] 14:22:05.123  ID=7E8    DLC=8  Data=02 10 01 00 00 00 00 00

        Output example (extended 29-bit ID):
            [RX] 14:22:05.456  ID=18DA00F1  DLC=8  Data=02 10 01 00 00 00 00 00 [EXT]

        Flags appended when true: [EXT]  [FD]  [RTR]  [ERR]
        """
        # Wall-clock time from the message hardware timestamp (fallback to now if absent)
        ts = msg.timestamp if msg.timestamp is not None else datetime.datetime.now().timestamp()
        wall = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]

        # CAN ID: 3 hex digits for 11-bit, 8 hex digits for 29-bit extended
        if msg.is_extended_id:
            id_str = f"{msg.arbitration_id:08X}"
        else:
            id_str = f"{msg.arbitration_id:03X}"

        # Data bytes as space-separated uppercase hex pairs
        data_hex = " ".join(f"{b:02X}" for b in msg.data)

        # Optional flag annotations
        flags = ""
        if msg.is_extended_id:
            flags += " [EXT]"
        if msg.is_fd:
            flags += " [FD]"
        if msg.is_remote_frame:
            flags += " [RTR]"
        if msg.is_error_frame:
            flags += " [ERR]"

        return f"[RX] {wall}  ID={id_str:<8}  DLC={msg.dlc}  Data={data_hex}{flags}"

    def _print_frame(self, msg: can.Message) -> None:
        """Print one frame line to stdout and record it in the diagnostic logger."""
        line = self._format_frame(msg)
        print(line)
        # Debug-level so this does not flood the diagnostic log file
        # under normal operation. Change to INFO if you need full frame logs there.
        self.logger.debug(line)

