"""
core/transmitter.py
-------------------
CAN transmit module for the PC-based ECU communication tool.

Design principles
-----------------
- The bus object is created OUTSIDE this class and passed in.
  This mirrors the receiver pattern and keeps hardware initialisation
  in one place (main.py). The transmitter never calls can.Bus() itself.

- send_frame()        — sends a pre-built can.Message directly.
- send_single_frame() — builds a can.Message from raw fields and sends it.
- send_frames()       — sends a list of pre-built messages with an optional
                        inter-frame delay. Used by main.py for the virtual
                        self-test and for any future TX sequences.

- Switching from virtual to real hardware requires zero changes here.
  Only the bus object passed in changes.

Out of scope (do not add):
- ISO-TP / UDS framing
- Periodic TX scheduling
- Any ECU control logic
"""

import time
import logging
from typing import Iterable, List

import can


class CANTransmitter:
    """
    CAN frame transmitter.

    Sends raw CAN frames via an already-initialised python-can Bus.
    The bus is created by the caller (main.py) and must be shut down
    by the caller after use.

    Parameters
    ----------
    bus : can.BusABC
        An open python-can bus object. Created by the caller (main.py).
    config : dict
        Full application config dict loaded from settings.json.
        Used to read interface/channel metadata for log messages.
    logger : logging.Logger
        Standard Python logger for diagnostic messages.
    """

    def __init__(self, bus: can.BusABC, config: dict, logger: logging.Logger) -> None:
        self.bus = bus
        self.config = config
        self.logger = logger

        self.logger.info(
            "CANTransmitter initialized | interface=%s  channel=%s  bitrate=%s",
            config.get("interface", "?"),
            config.get("channel", "?"),
            config.get("bitrate", "?"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_frame(self, msg: can.Message) -> None:
        """
        Send a pre-built can.Message on the bus.

        Parameters
        ----------
        msg : can.Message
            A fully constructed python-can Message object.
        """
        self.bus.send(msg)
        id_str = (
            f"0x{msg.arbitration_id:08X}" if msg.is_extended_id
            else f"0x{msg.arbitration_id:03X}"
        )
        self.logger.debug(
            "[TX] id=%s  DLC=%d  data=%s",
            id_str,
            msg.dlc,
            " ".join(f"{b:02X}" for b in msg.data),
        )

    def send_single_frame(
        self,
        arbitration_id: int,
        data: Iterable[int],
        is_extended_id: bool = False,
    ) -> None:
        """
        Build and send a single CAN frame.

        Parameters
        ----------
        arbitration_id : int
            CAN identifier (11-bit or 29-bit depending on is_extended_id).
        data : iterable of int
            Payload bytes. Up to 8 bytes for classic CAN.
        is_extended_id : bool
            True for 29-bit extended IDs, False (default) for 11-bit.
        """
        msg = can.Message(
            arbitration_id=arbitration_id,
            data=list(data),
            is_extended_id=is_extended_id,
        )
        self.send_frame(msg)

    def send_frames(
        self,
        frames: List[can.Message],
        interval_s: float = 0.1,
    ) -> None:
        """
        Send a list of pre-built CAN frames with an optional inter-frame delay.

        Parameters
        ----------
        frames : list of can.Message
            Frames to send in order.
        interval_s : float
            Seconds to wait between consecutive frames. Default 0.1 s.
        """
        for i, frame in enumerate(frames):
            self.send_frame(frame)
            self.logger.debug("Sent frame %d / %d", i + 1, len(frames))
            if i < len(frames) - 1:
                time.sleep(interval_s)

        self.logger.info("TX complete — %d frame(s) sent.", len(frames))
