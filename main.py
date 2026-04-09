"""
main.py
-------
Entry point for the PC-based ECU communication tool.

Responsibilities (orchestration only)
--------------------------------------
- Load configuration from config/settings.example.json
- Create the shared python-can Bus (single call site for hardware init)
- Instantiate CANTransmitter and CANReceiver, passing them the open bus
- In self-test mode, build the test frame list and delegate sending to
  CANTransmitter running in a background daemon thread
- Run the blocking CAN receive loop in the main thread
- Shut down the bus cleanly on exit

How to switch to real hardware later
--------------------------------------
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
# Virtual self-test frames
# ---------------------------------------------------------------------------

SELF_TEST_FRAMES = [
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

    rx_bus = None
    tx_bus = None
    try:
        rx_bus = create_bus(config, logger)

        # python-can virtual bus: messages sent on bus_A are delivered to all
        # OTHER bus instances on the same channel — NOT looped back to bus_A.
        # For the virtual self-test we therefore open a separate TX bus so the
        # receiver sees the injected frames. For real hardware a single shared
        # bus object handles both directions, so tx_bus stays None.
        if app_mode == "self_test_only" and interface == "virtual":
            tx_bus = can.Bus(
                interface="virtual",
                channel=config.get("channel", "test_channel"),
            )
            logger.debug("Opened dedicated TX bus for virtual self-test.")

        transmitter = CANTransmitter(
            bus=tx_bus if tx_bus is not None else rx_bus,
            config=config,
            logger=logger,
        )
        receiver = CANReceiver(bus=rx_bus, config=config, logger=logger)

        # ── Virtual self-test: inject frames so the RX loop has traffic ──
        if app_mode == "self_test_only" and interface == "virtual":
            try:
                interval_s = float(config.get("tx_frame_interval_s", 0.1))
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid tx_frame_interval_s in config; using default 0.1 s."
                )
                interval_s = 0.1
            logger.info(
                "Self-test mode: scheduling %d test frame(s) via background thread.",
                len(SELF_TEST_FRAMES),
            )

            def _run_self_test() -> None:
                time.sleep(0.3)  # Give the RX loop time to start
                transmitter.send_frames(SELF_TEST_FRAMES, interval_s=interval_s)

            injector = threading.Thread(
                target=_run_self_test,
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
        if tx_bus is not None:
            tx_bus.shutdown()
            logger.debug("TX bus shut down.")
        if rx_bus is not None:
            rx_bus.shutdown()
            logger.info("CAN bus shut down.")
        logger.info("Exiting.")


if __name__ == "__main__":
    main()

