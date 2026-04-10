"""
rules/builtin_rules.py
----------------------
Built-in fault-hint rules for Release 1.

Rules included
--------------
  ErrorFrameRule
      Fires on any CAN error frame (is_error_frame == True).
      Severity: error.

  SignalOutOfRangeRule
      Fires when any decoded signal exceeds a user-defined [min, max] range.
      Severity: warning.
      Thresholds are provided as a dict: {signal_name: (min_val, max_val)}.

  UnexpectedFrameIdRule
      Fires when a frame ID is not in a user-supplied allowed-ID set.
      Severity: info.  Useful to flag frames that should not appear on
      the bus during a given test scenario.

create_default_rule_engine()
      Convenience factory that returns a RuleEngine with all stateless
      built-in rules pre-loaded.  Stateful rules (SignalOutOfRangeRule,
      UnexpectedFrameIdRule) are not included by default — callers add
      them with custom parameters as needed.
"""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from decode.frame_record import DecodedFrame
from rules.base_rule import FaultHint, FaultRule
from rules.rule_engine import RuleEngine


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------

class ErrorFrameRule(FaultRule):
    """
    Detect CAN error frames.

    A CAN error frame is a bus-level error condition (bus-off, stuff error,
    form error, …).  Its presence indicates a hardware or wiring problem and
    should always be flagged immediately.
    """

    @property
    def rule_id(self) -> str:
        return "builtin.error_frame"

    def evaluate(self, frame: DecodedFrame) -> Optional[FaultHint]:
        if frame.raw.is_error_frame:
            return FaultHint(
                rule_id=self.rule_id,
                severity="error",
                message="CAN error frame detected — check bus wiring / termination.",
                frame_id=frame.raw.arbitration_id,
            )
        return None


class SignalOutOfRangeRule(FaultRule):
    """
    Detect decoded signal values that exceed defined engineering limits.

    Parameters
    ----------
    thresholds : dict
        Mapping of signal_name -> (min_value, max_value).
        Values are compared against DecodedSignal.value (engineering units).

    Example
    -------
        rule = SignalOutOfRangeRule({
            "EngineSpeed": (0, 8000),        # rpm
            "CoolantTemperature": (-40, 130), # °C
        })
    """

    def __init__(self, thresholds: Dict[str, Tuple[float, float]]) -> None:
        self._thresholds = dict(thresholds)

    @property
    def rule_id(self) -> str:
        return "builtin.signal_out_of_range"

    def evaluate(self, frame: DecodedFrame) -> Optional[FaultHint]:
        for signal in frame.signals:
            if signal.name not in self._thresholds:
                continue
            lo, hi = self._thresholds[signal.name]
            if signal.value < lo or signal.value > hi:
                unit_str = f" {signal.unit}" if signal.unit else ""
                return FaultHint(
                    rule_id=self.rule_id,
                    severity="warning",
                    message=(
                        f"Signal '{signal.name}' = {signal.value}{unit_str} "
                        f"is outside allowed range [{lo}, {hi}]."
                    ),
                    frame_id=frame.raw.arbitration_id,
                    signal_name=signal.name,
                )
        return None


class UnexpectedFrameIdRule(FaultRule):
    """
    Flag frames whose CAN ID is not in the expected set.

    Useful for scenario-level validation: define which IDs are expected
    during a test run, and flag any other ID as suspicious.

    Parameters
    ----------
    allowed_ids : set of int
        Set of CAN arbitration IDs that are expected during this test.
    """

    def __init__(self, allowed_ids: Set[int]) -> None:
        self._allowed = set(allowed_ids)

    @property
    def rule_id(self) -> str:
        return "builtin.unexpected_frame_id"

    def evaluate(self, frame: DecodedFrame) -> Optional[FaultHint]:
        if frame.raw.is_error_frame:
            return None  # Error frames have no useful arbitration ID
        if frame.raw.arbitration_id not in self._allowed:
            id_fmt = (
                f"0x{frame.raw.arbitration_id:08X}"
                if frame.raw.is_extended_id
                else f"0x{frame.raw.arbitration_id:03X}"
            )
            return FaultHint(
                rule_id=self.rule_id,
                severity="info",
                message=f"Unexpected frame ID {id_fmt} received.",
                frame_id=frame.raw.arbitration_id,
            )
        return None


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_default_rule_engine() -> RuleEngine:
    """
    Return a RuleEngine pre-loaded with all stateless built-in rules.

    Currently included:
      - ErrorFrameRule

    Stateful rules (SignalOutOfRangeRule, UnexpectedFrameIdRule) require
    caller-supplied parameters and are not included here.  Add them
    after calling this function:

        engine = create_default_rule_engine()
        engine.add_rule(SignalOutOfRangeRule({"EngineSpeed": (0, 8000)}))
    """
    engine = RuleEngine()
    engine.add_rule(ErrorFrameRule())
    return engine
