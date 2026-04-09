"""
Entry point for the bench-test ECU communication MVP.

Current scope:
- initialize configuration
- initialize logger
- placeholder flow for CAN receive / transmit modules

This project is intended for authorized static bench testing only.
"""

from pathlib import Path
import json

from app_logging.logger import setup_logger
from core.receiver import CANReceiver
from core.transmitter import CANTransmitter


def load_config(config_path: str = "config/settings.example.json") -> dict:
    """Load JSON configuration from disk."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    config = load_config()
    logger = setup_logger()

    logger.info("Starting PC-based ECU communication MVP")
    logger.info("Mode: static bench test only")

    receiver = CANReceiver(config=config, logger=logger)
    transmitter = CANTransmitter(config=config, logger=logger)

    logger.info("Receiver and transmitter objects created successfully")
    logger.info("This is the initial project skeleton. Runtime CAN logic will be added next.")

    # Placeholder: later we can call:
    # receiver.start()
    # transmitter.send_single_frame(arbitration_id=0x123, data=[0x01, 0x02])

    logger.info("Initialization complete.")


if __name__ == "__main__":
    main()
