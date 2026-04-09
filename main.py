"""
main.py
-------
Entry point for the PC-based ECU communication tool.

Current phase: virtual self-test only.
- Loads configuration from config/settings.example.json
- Opens a python-can virtual bus
- Injects 3 test frames from a background thread
- Runs the blocking CAN receive loop in the main thread
- Shuts down cleanly on Ctrl+C

How to switch to real hardware later
-------------------------------------
1. Edit config/settings.example.json:
       "interface": "pcan"          (or "kvaser", "vector", "socketcan")
       "channel":   "PCAN_USBBUS1"  (vendor-specific channel name)
2. Run again. No code changes needed.

Out of scope (do not add here):
- ISO-TP / UDS
- Flashing, Security Access, ECUReset
- DBC decoding
- Any high-risk ECU control
"""

import json
import logging
import threading
import time
from pathlib import Path

import can

from app_logging.logger import setup_logger
from core.receiver import CANReceiver
from core.transmitter import CANTransmitter


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config/settings.example.json") -> dict:
    """Load and return the JSON configuration dict."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


# ---------------------------------------------------------------------------
# Bus factory
# ---------------------------------------------------------------------------

def create_bus(config: dict, logger: logging.Logger) -> can.BusABC:
    """
    Construct and return an open python-can Bus from config.

    This is the ONLY place in the project that calls can.Bus().
    Every other module receives the bus object — hardware details
    are fully isolated here.

    Supported interfaces (config-driven, no code change needed):
        virtual   — python-can in-process bus (current phase)
        pcan      — PEAK PCAN-USB
        kvaser    — Kvaser adapters
        vector    — Vector hardware
        socketcan — Linux SocketCAN
    """
    interface = config["interface"]
    channel   = config["channel"]
    bitrate   = config.get("bitrate", 500000)
    fd        = config.get("fd_enabled", False)

    kwargs: dict = {
        "interface": interface,
        "channel":   channel,
        "bitrate":   bitrate,
    }
    if fd:
        kwargs["fd"] = True

    logger.info("Opening CAN bus | interface=%s  channel=%s  bitrate=%d  fd=%s",
                interface, channel, bitrate, fd)

    bus = can.Bus(**kwargs)
    logger.info("Bus opened: %s", bus)
    return bus


# ---------------------------------------------------------------------------
# Virtual self-test injector
# ---------------------------------------------------------------------------

def _inject_test_frames(channel: str, logger: logging.Logger) -> None:
    """
    Push 3 test frames into the virtual bus so the receiver has real traffic.

    Runs in a daemon thread — exits automatically when main thread exits.
    Only used in self_test_only mode. Remove or ignore for real hardware.

    The injector opens its OWN Bus object on the same virtual channel.
    python-can virtual buses are shared by channel name within a process,
    so these frames appear on the receiver's bus immediately.
    """
    time.sleep(0.3)  # Brief delay — give the RX loop time to start printing

    try:
        injector_bus = can.Bus(interface="virtual", channel=channel)

        test_frames = [
            can.Message(
                arbitration_id=0x7E8,
                data=[0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
                is_extended_id=False,
            ),
            can.Message(
                arbitration_id=0x123,
                data=[0xDE, 0xAD, 0xBE, 0xEF],
                is_extended_id=False,
            ),
            can.Message(
                arbitration_id=0x18DA00F1,
                data=[0x01, 0x3E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                is_extended_id=True,
            ),
        ]

        for i, frame in enumerate(test_frames):
            injector_bus.send(frame)
            logger.debug("Injected test frame %d: ID=0x%X", i + 1, frame.arbitration_id)
            time.sleep(0.1)

        injector_bus.shutdown()
        logger.info("Test frame injection complete (3 frames sent).")

    except Exception as exc:
        logger.warning("Test frame injector error: %s", exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    config = load_config()
    logger = setup_logger()

    logger.info("=" * 50)
    logger.info("PC-based ECU Communication Tool — starting")
    logger.info("Mode      : %s", config.get("app_mode", "unknown"))
    logger.info("Interface : %s", config.get("interface"))
    logger.info("Channel   : %s", config.get("channel"))
    logger.info("=" * 50)

    app_mode  = config.get("app_mode", "")
    interface = config.get("interface", "")

    bus = None
    try:
        bus = create_bus(config, logger)

        # Receiver: owns the blocking loop, uses the shared bus
        receiver = CANReceiver(bus=bus, config=config, logger=logger)

        # Transmitter: skeleton only this phase, holds the bus reference
        # for when send_single_frame() is implemented next
        transmitter = CANTransmitter(config=config, logger=logger)

        # ── Virtual self-test: inject frames so the RX loop has traffic ──
        if app_mode == "self_test_only" and interface == "virtual":
            logger.info("Self-test mode: injecting 3 test frames via background thread.")
            channel = config.get("channel", "test_channel")
            injector = threading.Thread(
                target=_inject_test_frames,
                args=(channel, logger),
                daemon=True,
                name="frame-injector",
            )
            injector.start()

        # ── Blocking receive loop (main thread) ──
        # Returns only on Ctrl+C
        receiver.start()

    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
    except can.CanInitializationError as exc:
        logger.error("Failed to open CAN bus: %s", exc)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
    finally:
        if bus is not None:
            bus.shutdown()
            logger.info("CAN bus shut down.")
        logger.info("Exiting.")


if __name__ == "__main__":
    main()

