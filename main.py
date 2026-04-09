"""
main.py
-------
Entry point for the PC-based ECU communication tool.

Responsibilities (orchestration only)
--------------------------------------
- Parse --ui flag: if present, launch the Tkinter desktop UI (ui/app.py).
- Load configuration from config/settings.example.json.
- Create the shared python-can Bus (single call site for hardware init).
- In self_test_only mode, delegate to run_virtual_self_test() in
  core/self_test.py and print the results summary to the console.
- For other modes (e.g. real-hardware monitoring), run the blocking
  CANReceiver.start() loop.
- Shut down the bus cleanly on exit.

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

import argparse
import json
import logging
from pathlib import Path

import can

from app_logging.logger import setup_logger
from core.receiver import CANReceiver
from core.self_test import SELF_TEST_FRAMES, run_virtual_self_test


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
        virtual   -- python-can in-process bus (current phase)
        pcan      -- PEAK PCAN-USB
        kvaser    -- Kvaser adapters
        vector    -- Vector hardware
        socketcan -- Linux SocketCAN
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

    logger.info(
        "Opening CAN bus | interface=%s  channel=%s  bitrate=%d  fd=%s",
        interface, channel, bitrate, fd,
    )

    bus = can.Bus(**kwargs)
    logger.info("Bus opened: %s", bus)
    return bus


# ---------------------------------------------------------------------------
# CLI self-test result printer
# ---------------------------------------------------------------------------

def _print_self_test_results(result) -> None:
    """Print a formatted self-test summary to stdout."""
    print()
    print("=" * 64)
    print("  Self-Test Results")
    print("=" * 64)
    print(f"  {'Timestamp':<16} {'CAN ID':<10} {'DLC':<5} Data (hex)")
    print("-" * 64)
    for msg in result.received_frames:
        import datetime
        ts = msg.timestamp if msg.timestamp is not None else datetime.datetime.now().timestamp()
        wall = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
        id_str = (
            f"{msg.arbitration_id:08X}" if msg.is_extended_id
            else f"{msg.arbitration_id:03X}"
        )
        data_hex = " ".join(f"{b:02X}" for b in msg.data)
        flags = " [EXT]" if msg.is_extended_id else ""
        print(f"  {wall:<16} {id_str:<10} {msg.dlc:<5} {data_hex}{flags}")
    print("-" * 64)
    outcome = "PASS" if result.passed else "FAIL"
    print(f"  Result  : {outcome}")
    print(f"  Sent    : {result.sent_count}")
    print(f"  Received: {len(result.received_frames)}")
    print("=" * 64)
    print()
    for line in result.log_lines:
        print(f"  {line}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PC-based ECU Communication Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the graphical Tkinter desktop UI instead of the CLI.",
    )
    args = parser.parse_args()

    # ── UI mode ─────────────────────────────────────────────────────────
    if args.ui:
        from ui.app import launch
        launch()
        return

    # ── CLI mode ─────────────────────────────────────────────────────────
    config = load_config()
    logger = setup_logger()

    logger.info("=" * 50)
    logger.info("PC-based ECU Communication Tool -- starting")
    logger.info("Mode      : %s", config.get("app_mode", "unknown"))
    logger.info("Interface : %s", config.get("interface"))
    logger.info("Channel   : %s", config.get("channel"))
    logger.info("=" * 50)

    app_mode  = config.get("app_mode", "")
    interface = config.get("interface", "")

    # ── Virtual self-test: use the shared runner, then print results ─────
    if app_mode == "self_test_only" and interface == "virtual":
        result = run_virtual_self_test(config, logger)
        _print_self_test_results(result)
        return

    # ── Other modes: open bus and run the blocking receive loop ──────────
    rx_bus = None
    try:
        rx_bus = create_bus(config, logger)
        receiver = CANReceiver(bus=rx_bus, config=config, logger=logger)
        receiver.start()

    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
    except can.CanInitializationError as exc:
        logger.error("Failed to open CAN bus: %s", exc)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
    finally:
        if rx_bus is not None:
            rx_bus.shutdown()
            logger.info("CAN bus shut down.")
        logger.info("Exiting.")


if __name__ == "__main__":
    main()
