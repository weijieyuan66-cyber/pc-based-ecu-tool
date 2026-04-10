"""
validation/validator.py
-----------------------
ExpectationValidator — the core engine of the validation layer.

Design
------
- Stateful: tracks which messages have been seen and the last arrival
  timestamp per message ID so cycle-time deviations can be computed.
- feed(frame) is called once per decoded frame.  It returns any
  DeviationEvent objects produced by that specific frame.
- finalize() is called once after all frames have been processed.  It
  checks post-session constraints (e.g. messages that never arrived) and
  returns the complete ValidationSummary.
- reset() clears all state so the validator can be reused for a new run.
- to_fault_hints() is a static bridge method that converts a list of
  DeviationEvent objects into FaultHint objects, allowing the existing
  Fault Hints tab and rule pipeline to display validation results without
  any schema changes.

This module has no UI imports and no transport-layer imports beyond
decode.frame_record.DecodedFrame.

Extensibility
-------------
To add a new check category:
  1. Add a new DeviationType member in results.py.
  2. Add the corresponding field(s) to ExpectedMessageSpec in specs.py.
  3. Add the check logic inside feed() or finalize() below.
  No callers need to change.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from decode.frame_record import DecodedFrame
from rules.base_rule import FaultHint
from validation.results import DeviationEvent, DeviationType, ValidationSummary
from validation.specs import ExpectedMessageSpec, ExpectationSpec

logger = logging.getLogger(__name__)

# Prefix used when converting DeviationEvents to FaultHint rule_id strings.
_RULE_ID_PREFIX = "validation"


class ExpectationValidator:
    """
    Validates a stream of DecodedFrames against an ExpectationSpec.

    Lifecycle
    ---------
    1. Construct with an ExpectationSpec.
    2. Call feed(frame) for every frame in the session.
    3. Call finalize() once to obtain the complete ValidationSummary.
    4. Optionally call to_fault_hints(summary.deviations) to convert
       results into FaultHint objects for the existing rule pipeline.
    5. Call reset() if you want to reuse the validator for another session.

    Parameters
    ----------
    spec : ExpectationSpec
        The scenario to validate against.
    """

    def __init__(self, spec: ExpectationSpec) -> None:
        self._spec = spec
        # Index specs by message_id for O(1) per-frame lookup.
        self._specs_by_id: Dict[int, ExpectedMessageSpec] = {
            m.message_id: m for m in spec.messages
        }
        # Tracks whether each *required* message has been seen at least once.
        self._seen: Dict[int, bool] = {
            m.message_id: False
            for m in spec.messages
            if m.required
        }
        # Last arrival timestamp (seconds) per message_id, used for cycle-time.
        self._last_ts: Dict[int, float] = {}
        # Accumulates all per-frame deviations; finalize() appends post-session ones.
        self._deviations: List[DeviationEvent] = []
        self._finalized = False

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """
        Clear all accumulated state so the validator can be reused.

        Call this before feeding frames for a new session when the same
        ExpectationSpec is to be re-applied.
        """
        for mid in self._seen:
            self._seen[mid] = False
        self._last_ts.clear()
        self._deviations.clear()
        self._finalized = False

    def feed(self, frame: DecodedFrame) -> List[DeviationEvent]:
        """
        Evaluate one decoded frame against the expectation spec.

        Checks applied per frame
        ~~~~~~~~~~~~~~~~~~~~~~~~
        - UnexpectedSourceAddress  (if expected_source_address is set)
        - AbnormalCycleTime        (if expected_cycle_time_ms is set and a
                                    prior arrival was recorded)
        - FixedValueMismatch       (for every ExpectedFieldConstraint)

        Parameters
        ----------
        frame : DecodedFrame
            The frame to evaluate.

        Returns
        -------
        list of DeviationEvent
            Deviations produced by this frame only.  Empty when none fire.
        """
        mid = frame.raw.arbitration_id
        msg_spec = self._specs_by_id.get(mid)
        if msg_spec is None:
            return []

        events: List[DeviationEvent] = []
        ts: Optional[float] = frame.raw.timestamp

        # Mark required message as seen.
        if mid in self._seen:
            self._seen[mid] = True

        # ── Source-address check ─────────────────────────────────────────
        if msg_spec.expected_source_address is not None:
            actual_sa = frame.source_address
            if actual_sa != msg_spec.expected_source_address:
                expected_hex = f"0x{msg_spec.expected_source_address:02X}"
                actual_hex = (
                    f"0x{actual_sa:02X}" if actual_sa is not None else "??"
                )
                events.append(DeviationEvent(
                    deviation_type=DeviationType.UNEXPECTED_SOURCE_ADDRESS,
                    message_id=mid,
                    label=msg_spec.label,
                    severity="warning",
                    message=(
                        f"Message '{msg_spec.label}' (0x{mid:X}): "
                        f"expected SA={expected_hex}, got SA={actual_hex}."
                    ),
                    detail={
                        "expected_sa": msg_spec.expected_source_address,
                        "actual_sa": actual_sa,
                    },
                ))

        # ── Cycle-time check ─────────────────────────────────────────────
        if msg_spec.expected_cycle_time_ms is not None and ts is not None:
            prev_ts = self._last_ts.get(mid)
            if prev_ts is not None:
                measured_ms = (ts - prev_ts) * 1000.0
                tol = msg_spec.cycle_time_tolerance_pct / 100.0
                lo = msg_spec.expected_cycle_time_ms * (1.0 - tol)
                hi = msg_spec.expected_cycle_time_ms * (1.0 + tol)
                if not (lo <= measured_ms <= hi):
                    events.append(DeviationEvent(
                        deviation_type=DeviationType.ABNORMAL_CYCLE_TIME,
                        message_id=mid,
                        label=msg_spec.label,
                        severity="warning",
                        message=(
                            f"Message '{msg_spec.label}' (0x{mid:X}): "
                            f"cycle time {measured_ms:.1f} ms is outside "
                            f"expected {msg_spec.expected_cycle_time_ms:.0f} ms "
                            f"± {msg_spec.cycle_time_tolerance_pct:.0f} %."
                        ),
                        detail={
                            "expected_ms": msg_spec.expected_cycle_time_ms,
                            "measured_ms": round(measured_ms, 2),
                            "tolerance_pct": msg_spec.cycle_time_tolerance_pct,
                        },
                    ))
            self._last_ts[mid] = ts

        # ── Field-constraint checks ──────────────────────────────────────
        data = bytes(frame.raw.data)
        for constraint in msg_spec.field_constraints:
            if constraint.field_index >= len(data):
                logger.debug(
                    "Field constraint for '%s' byte %d skipped: "
                    "frame only has %d byte(s).",
                    msg_spec.label, constraint.field_index, len(data),
                )
                continue
            raw_byte = data[constraint.field_index]
            masked_actual = raw_byte & constraint.mask
            masked_expected = constraint.expected_value & constraint.mask
            if masked_actual != masked_expected:
                events.append(DeviationEvent(
                    deviation_type=DeviationType.FIXED_VALUE_MISMATCH,
                    message_id=mid,
                    label=msg_spec.label,
                    severity="warning",
                    message=(
                        f"Message '{msg_spec.label}' (0x{mid:X}): "
                        f"field '{constraint.field_name}' at byte "
                        f"{constraint.field_index} = 0x{raw_byte:02X} "
                        f"(masked: 0x{masked_actual:02X}), "
                        f"expected 0x{constraint.expected_value:02X}."
                    ),
                    detail={
                        "field_name": constraint.field_name,
                        "field_index": constraint.field_index,
                        "expected": constraint.expected_value,
                        "actual": raw_byte,
                        "mask": constraint.mask,
                    },
                ))

        self._deviations.extend(events)
        return events

    def finalize(self) -> ValidationSummary:
        """
        Check post-session constraints and return the complete ValidationSummary.

        Post-session checks applied
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        - MissingExpectedMessage  (required messages that were never seen)

        Must be called after all frames have been fed.  Calling finalize()
        more than once returns an updated summary each time (idempotent
        with respect to the frame stream, but missing-message events will
        not be duplicated on repeat calls).
        """
        if not self._finalized:
            for mid, seen in self._seen.items():
                if not seen:
                    msg_spec = self._specs_by_id[mid]
                    self._deviations.append(DeviationEvent(
                        deviation_type=DeviationType.MISSING_EXPECTED_MESSAGE,
                        message_id=mid,
                        label=msg_spec.label,
                        severity="error",
                        message=(
                            f"Required message '{msg_spec.label}' (0x{mid:X}) "
                            f"was never received during the session."
                        ),
                        detail={"message_id": mid},
                    ))
            self._finalized = True

        by_type: Dict[str, int] = {}
        for evt in self._deviations:
            key = evt.deviation_type.value
            by_type[key] = by_type.get(key, 0) + 1

        return ValidationSummary(
            scenario_name=self._spec.scenario_name,
            deviations=list(self._deviations),
            total_deviations=len(self._deviations),
            by_type=dict(by_type),
            passed=len(self._deviations) == 0,
        )

    # ------------------------------------------------------------------ #
    # Fault-hint bridge                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_fault_hints(deviations: List[DeviationEvent]) -> List[FaultHint]:
        """
        Convert DeviationEvent objects into FaultHint objects.

        This bridge method allows the existing Fault Hints tab and
        fault-hint rule pipeline to display validation results without
        any schema changes on their side.

        The rule_id of each produced FaultHint follows the pattern:
            "validation.<DeviationType.value>"
        e.g. "validation.MissingExpectedMessage"

        Parameters
        ----------
        deviations : list of DeviationEvent

        Returns
        -------
        list of FaultHint
        """
        return [
            FaultHint(
                rule_id=f"{_RULE_ID_PREFIX}.{evt.deviation_type.value}",
                severity=evt.severity,
                message=evt.message,
                frame_id=evt.message_id,
            )
            for evt in deviations
        ]
