"""
core/self_test.py
-----------------
Virtual self-test orchestration.

This module owns:
- SELF_TEST_FRAMES  — the canonical list of test frames
- SelfTestResult    — plain dataclass returned by the runner
- run_virtual_self_test() — single function called by both CLI and UI

Design principles
-----------------
- No UI code lives here.  No blocking console loops live here.
- The function opens its own buses, runs the test, shuts them down,
  and returns a SelfTestResult.  Callers just await the return value.
- Switching to real hardware later: supply a non-virtual config dict
  and a matching bus factory; the receiver/transmitter logic is identical.

Out of scope (do not add here):
- ISO-TP / UDS
- DBC decoding
- Any ECU control logic
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

import can

from core.receiver import CANReceiver
from core.transmitter import CANTransmitter


# ---------------------------------------------------------------------------
# Canonical test-frame list
# ---------------------------------------------------------------------------

SELF_TEST_FRAMES: List[can.Message] = [
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
# Result container
# ---------------------------------------------------------------------------

@dataclass
class SelfTestResult:
    """
    Returned by run_virtual_self_test().

    Attributes
    ----------
    sent_count : int
        Number of frames that were transmitted.
    received_frames : list of can.Message
        Frames captured by the receiver during the test.
    passed : bool
        True when len(received_frames) == sent_count.
    log_lines : list of str
        Human-readable log messages produced during the run.
        Suitable for display in a UI log area or CLI output.
    """

    sent_count: int
    received_frames: List[can.Message] = field(default_factory=list)
    passed: bool = False
    log_lines: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Self-test runner
# ---------------------------------------------------------------------------

def run_virtual_self_test(
    config: dict,
    logger: logging.Logger,
) -> SelfTestResult:
    """
    Run the virtual CAN self-test end-to-end and return the result.

    Opens two separate python-can virtual bus instances on the same channel
    (one for TX, one for RX — required because the virtual interface does not
    loop frames back to the sender).  Sends SELF_TEST_FRAMES from the TX side
    in a background thread while collecting frames on the RX side.  Shuts
    both buses down before returning.

    Parameters
    ----------
    config : dict
        Application config dict.  Relevant keys:
          \"channel\"             — virtual channel name (default \"test_channel\")
          \"tx_frame_interval_s\" — inter-frame delay in seconds (default 0.1)
    logger : logging.Logger
        Diagnostic logger.

    Returns
    -------
    SelfTestResult
    """
    result = SelfTestResult(sent_count=len(SELF_TEST_FRAMES))
    log: List[str] = []

    channel = config.get("channel", "test_channel")
    try:
        interval_s = float(config.get("tx_frame_interval_s", 0.1))
    except (TypeError, ValueError):
        interval_s = 0.1

    rx_bus: Optional[can.BusABC] = None
    tx_bus: Optional[can.BusABC] = None

    try:
        log.append(f"Opening virtual buses on channel '{channel}' ...")
        rx_bus = can.Bus(interface="virtual", channel=channel)
        tx_bus = can.Bus(interface="virtual", channel=channel)

        transmitter = CANTransmitter(bus=tx_bus, config=config, logger=logger)
        receiver = CANReceiver(bus=rx_bus, config=config, logger=logger)

        log.append(f"Sending {len(SELF_TEST_FRAMES)} frame(s) ...")
        logger.info(
            "Self-test: sending %d frame(s) on channel=%s",
            len(SELF_TEST_FRAMES), channel,
        )

        # Send in a background thread so the receive loop runs concurrently.
        # A brief head-start delay ensures the receiver is ready before the
        # first frame arrives.
        def _send() -> None:
            time.sleep(0.15)
            transmitter.send_frames(SELF_TEST_FRAMES, interval_s=interval_s)

        sender = threading.Thread(target=_send, daemon=True, name="self-test-sender")
        sender.start()

        # Total receive window: all frames * interval + a 2-second buffer
        rx_timeout_s = len(SELF_TEST_FRAMES) * interval_s + 2.0
        received = receiver.collect(
            expected_count=len(SELF_TEST_FRAMES),
            timeout_s=rx_timeout_s,
        )

        sender.join(timeout=5.0)

        result.received_frames = received
        result.passed = len(received) == len(SELF_TEST_FRAMES)

        log.append(f"Frames sent     : {len(SELF_TEST_FRAMES)}")
        log.append(f"Frames received : {len(received)}")
        log.append("Result          : " + ("PASS" if result.passed else "FAIL"))

        logger.info(
            "Self-test complete | sent=%d  received=%d  passed=%s",
            len(SELF_TEST_FRAMES), len(received), result.passed,
        )

    except Exception as exc:
        logger.exception("Self-test error: %s", exc)
        log.append(f"ERROR: {exc}")

    finally:
        if tx_bus is not None:
            tx_bus.shutdown()
        if rx_bus is not None:
            rx_bus.shutdown()

    result.log_lines = log
    return result
