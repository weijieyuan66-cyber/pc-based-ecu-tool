"""
validation/mock_validation_test.py
-----------------------------------
Mock validation test using synthetic (virtual) CAN data.

Purpose
-------
Demonstrates and exercises the validation layer end-to-end without
requiring real CAN hardware or an active CAN bus session.  All frames
are constructed in memory with explicit timestamps.

Scenario
--------
Expectations
  - Message A (0x100)  must appear (required=True)
  - Message B (0x200)  must come from SA=0x10
  - Message C (0x300)  must have cycle time = 100 ms (± 20 %)
  - Message D (0x400)  byte 0 (field "X") must equal 0x3E

Simulated anomalies
  - A is never sent              → MissingExpectedMessage
  - B is sent from SA=0x20       → UnexpectedSourceAddress
  - C is sent at 300 ms intervals → AbnormalCycleTime (× 2 occurrences)
  - D byte 0 = 0x7F              → FixedValueMismatch

Expected result: 4 distinct deviation types, validator.passed == False.

Public API
----------
build_mock_expectation_spec() -> ExpectationSpec
    Build and return the scenario spec (useful for tests or doc examples).

build_mock_frames() -> list of DecodedFrame
    Build and return the synthetic frames with embedded anomalies.

run_mock_validation_test() -> ValidationSummary
    Run the full mock scenario and return the summary.

mock_validation_fault_hints() -> list of FaultHint
    Convenience wrapper: run the test and return FaultHint objects that
    can be passed directly to the existing Fault Hints UI tab.
"""

from __future__ import annotations

import logging
from typing import List

import can

from decode.frame_record import DecodedFrame
from rules.base_rule import FaultHint
from validation.results import ValidationSummary
from validation.specs import (
    ExpectationSpec,
    ExpectedFieldConstraint,
    ExpectedMessageSpec,
)
from validation.validator import ExpectationValidator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario builder helpers
# ---------------------------------------------------------------------------

def build_mock_expectation_spec() -> ExpectationSpec:
    """
    Return the ExpectationSpec for the mock validation scenario.

    Four messages are specified, each exercising a different check type.
    """
    return ExpectationSpec(
        scenario_name="mock_validation_scenario",
        messages=[
            # A: must appear at least once
            ExpectedMessageSpec(
                message_id=0x100,
                label="A",
                required=True,
            ),
            # B: source address must be 0x10
            ExpectedMessageSpec(
                message_id=0x200,
                label="B",
                required=False,
                expected_source_address=0x10,
            ),
            # C: inter-arrival time must be 100 ms ± 20 %
            ExpectedMessageSpec(
                message_id=0x300,
                label="C",
                required=False,
                expected_cycle_time_ms=100.0,
                cycle_time_tolerance_pct=20.0,
            ),
            # D: byte 0 (field "X") must equal 0x3E
            ExpectedMessageSpec(
                message_id=0x400,
                label="D",
                required=False,
                field_constraints=(
                    ExpectedFieldConstraint(
                        field_index=0,
                        expected_value=0x3E,
                        field_name="X",
                    ),
                ),
            ),
        ],
    )


def build_mock_frames() -> List[DecodedFrame]:
    """
    Build synthetic DecodedFrame objects that embody the four anomalies.

    Timestamps are absolute epoch seconds chosen so that inter-arrival
    intervals are well-defined and independent of wall-clock time.

    Anomalies embedded
    ------------------
    - A (0x100)  NOT sent at all.
    - B (0x200)  source_address set to 0x20 (expected 0x10).
    - C (0x300)  sent 3 times at 300 ms intervals (expected 100 ms).
    - D (0x400)  byte 0 = 0x7F  (expected 0x3E).
    """
    frames: List[DecodedFrame] = []
    base_ts = 1_000.0  # arbitrary stable base (seconds)

    # ── B: wrong source address ──────────────────────────────────────────
    msg_b = can.Message(
        arbitration_id=0x200,
        data=[0xAA, 0xBB],
        is_extended_id=False,
        timestamp=base_ts + 0.050,
    )
    frames.append(DecodedFrame(raw=msg_b, source_address=0x20))

    # ── C: sent at 300 ms intervals (3 frames → 2 cycle-time checks) ─────
    for i in range(3):
        ts = base_ts + 0.100 + i * 0.300  # 300 ms apart
        msg_c = can.Message(
            arbitration_id=0x300,
            data=[0x01, 0x02],
            is_extended_id=False,
            timestamp=ts,
        )
        frames.append(DecodedFrame(raw=msg_c))

    # ── D: byte 0 = 0x7F (expected 0x3E) ────────────────────────────────
    msg_d = can.Message(
        arbitration_id=0x400,
        data=[0x7F, 0x00, 0x00],
        is_extended_id=False,
        timestamp=base_ts + 1.000,
    )
    frames.append(DecodedFrame(raw=msg_d))

    return frames


# ---------------------------------------------------------------------------
# Public runners
# ---------------------------------------------------------------------------

def run_mock_validation_test() -> ValidationSummary:
    """
    Run the mock validation scenario and return the ValidationSummary.

    Steps
    -----
    1. Build the ExpectationSpec.
    2. Create synthetic DecodedFrame objects with embedded anomalies.
    3. Feed them to ExpectationValidator.
    4. Call finalize() and return the summary.

    The returned summary will contain deviations for all four anomaly types:
    MissingExpectedMessage, UnexpectedSourceAddress, AbnormalCycleTime (×2),
    and FixedValueMismatch.
    """
    spec = build_mock_expectation_spec()
    validator = ExpectationValidator(spec)

    frames = build_mock_frames()
    for frame in frames:
        per_frame_devs = validator.feed(frame)
        for evt in per_frame_devs:
            logger.info(
                "[MockValidation] %s — %s", evt.deviation_type.value, evt.message
            )

    summary = validator.finalize()

    logger.info(
        "[MockValidation] scenario='%s'  deviations=%d  passed=%s",
        summary.scenario_name,
        summary.total_deviations,
        summary.passed,
    )
    for evt in summary.deviations:
        logger.info(
            "[MockValidation]  [%s] %s: %s",
            evt.severity.upper(), evt.deviation_type.value, evt.message,
        )

    return summary


def mock_validation_fault_hints() -> List[FaultHint]:
    """
    Run the mock validation test and return results as FaultHint objects.

    This is a convenience wrapper for the UI layer: the Fault Hints tab
    can display validation deviations using its existing FaultHint schema
    without any structural change.
    """
    summary = run_mock_validation_test()
    return ExpectationValidator.to_fault_hints(summary.deviations)
