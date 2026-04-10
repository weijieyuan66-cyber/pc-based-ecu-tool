"""
main.py
-------
Entry point for the PC-based ECU communication tool — Release 1.

Responsibilities (orchestration only)
--------------------------------------
- Parse --ui flag: if present, launch the Tkinter desktop UI (ui/app.py).
- Load configuration from config/settings.example.json.
- Delegate self-test to run_virtual_self_test() in core/self_test.py.
- For monitoring mode, create the backend via BackendFactory and run the
  blocking receive loop.
- Shut down the backend cleanly on exit.

How to switch backends
--------------------------------------
1. Edit config/settings.example.json:
       "backend": "pcan"    (or "vector" / "virtual")
2. Run again. No code changes needed.

Out of scope (do not add here):
- ISO-TP / UDS
- Flashing, Security Access, ECUReset
- Any high-risk ECU control
"""

import argparse
import datetime
import json
import logging
from pathlib import Path

from app_logging.logger import setup_logger
from core.self_test import run_virtual_self_test


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
        description="PC-based ECU Communication Tool — Release 1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the graphical Tkinter desktop UI instead of the CLI.",
    )
    parser.add_argument(
        "--config",
        default="config/settings.example.json",
        help="Path to JSON config file (default: config/settings.example.json).",
    )
    args = parser.parse_args()

    # ── UI mode ─────────────────────────────────────────────────────────
    if args.ui:
        from ui.app import launch
        launch(config_path=args.config)
        return

    # ── CLI mode ─────────────────────────────────────────────────────────
    config = load_config(args.config)
    logger = setup_logger()

    # Support both new ("backend") and old ("interface") config format
    backend_name = config.get("backend", config.get("interface", "virtual"))
    app_mode = config.get("app_mode", "")

    logger.info("=" * 50)
    logger.info("PC-based ECU Communication Tool — Release 1")
    logger.info("Backend   : %s", backend_name)
    logger.info("Mode      : %s", app_mode)
    logger.info("=" * 50)

    # ── Virtual self-test ────────────────────────────────────────────────
    if app_mode == "self_test_only" and backend_name == "virtual":
        result = run_virtual_self_test(config, logger)
        _print_self_test_results(result)
        return

    # ── Monitoring mode: backend → blocking receive loop ─────────────────
    from backend.factory import BackendFactory

    backend = BackendFactory.create(config)
    logger.info("Connecting to backend '%s' ...", backend.backend_name)

    if not backend.connect():
        logger.error(
            "Failed to connect to '%s' backend: %s",
            backend.backend_name,
            backend.connection_error,
        )
        print(f"[ERROR] Could not connect: {backend.connection_error}")
        return

    rx_timeout_s = float(config.get("rx_timeout_s", 1.0))
    rx_count = 0

    print("\n" + "=" * 60)
    print("  CAN Monitor")
    print(f"  Backend : {backend.backend_name}")
    print("=" * 60)
    print("  Timestamp        ID         DLC  Data (hex)")
    print("-" * 60)

    try:
        while True:
            msg = backend.recv(timeout=rx_timeout_s)
            if msg is None:
                continue
            rx_count += 1
            _print_msg(msg)
    except KeyboardInterrupt:
        print("-" * 60)
        print(f"  Stopped by user. Total frames received: {rx_count}")
        print("=" * 60 + "\n")
        logger.info("Monitoring stopped by user. Total RX: %d", rx_count)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
    finally:
        backend.disconnect()
        logger.info("Backend disconnected. Exiting.")


def _print_msg(msg) -> None:
    """Format and print a single CAN frame to stdout."""
    ts = msg.timestamp if msg.timestamp is not None else datetime.datetime.now().timestamp()
    wall = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
    id_str = (
        f"{msg.arbitration_id:08X}" if msg.is_extended_id
        else f"{msg.arbitration_id:03X}"
    )
    data_hex = " ".join(f"{b:02X}" for b in msg.data)
    flags = " [EXT]" if msg.is_extended_id else ""
    print(f"[RX] {wall}  ID={id_str:<8}  DLC={msg.dlc}  Data={data_hex}{flags}")


if __name__ == "__main__":
    main()
