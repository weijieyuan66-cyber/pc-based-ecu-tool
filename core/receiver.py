"""
Basic CAN receive module (initial skeleton).

Current status:
- project structure only
- no active hardware interaction yet

Next step:
- add python-can interface initialization
- add receive loop
- print timestamp / CAN ID / DLC / data
"""

from typing import Any


class CANReceiver:
    """Initial skeleton for CAN receiving logic."""

    def __init__(self, config: dict, logger: Any) -> None:
        self.config = config
        self.logger = logger
        self.channel = config.get("channel", "CAN0")
        self.bitrate = config.get("bitrate", 500000)
        self.interface = config.get("interface", "socketcan")

        self.logger.info(
            "CANReceiver initialized | interface=%s channel=%s bitrate=%s",
            self.interface,
            self.channel,
            self.bitrate,
        )

    def start(self) -> None:
        """
        Placeholder for future receive loop.

        Intended future behavior:
        - open CAN interface
        - listen for messages
        - print timestamp / CAN ID / DLC / data
        """
        self.logger.info("CANReceiver.start() called - not implemented yet")

    def stop(self) -> None:
        """Placeholder for future stop logic."""
        self.logger.info("CANReceiver.stop() called - not implemented yet")
