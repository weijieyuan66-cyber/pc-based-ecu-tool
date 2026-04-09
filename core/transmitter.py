"""
Basic CAN transmit module (initial skeleton).

Current status:
- project structure only
- no active hardware interaction yet

Next step:
- add python-can bus initialization
- add single-frame transmit method
"""

from typing import Any, Iterable


class CANTransmitter:
    """Initial skeleton for CAN transmit logic."""

    def __init__(self, config: dict, logger: Any) -> None:
        self.config = config
        self.logger = logger
        self.channel = config.get("channel", "CAN0")
        self.bitrate = config.get("bitrate", 500000)
        self.interface = config.get("interface", "socketcan")

        self.logger.info(
            "CANTransmitter initialized | interface=%s channel=%s bitrate=%s",
            self.interface,
            self.channel,
            self.bitrate,
        )

    def send_single_frame(self, arbitration_id: int, data: Iterable[int]) -> None:
        """
        Placeholder for future single-frame transmission.

        Parameters:
        - arbitration_id: CAN identifier
        - data: iterable of integer bytes
        """
        data_list = list(data)
        self.logger.info(
            "Requested TX | id=0x%X data=%s (not implemented yet)",
            arbitration_id,
            [f"0x{byte:02X}" for byte in data_list],
        )
