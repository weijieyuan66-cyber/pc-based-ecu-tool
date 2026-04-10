"""
validation/results.py
---------------------
Output types of the expectation / validation layer.

Classes
-------
DeviationType
    Enum of known deviation categories.  New members can be added here
    without changing existing code that already handles other members —
    each handler simply ignores unknown types it does not recognise.

DeviationEvent
    A single detected deviation: immutable, serialisation-friendly.

ValidationSummary
    Aggregated result returned by ExpectationValidator.finalize().

Extensibility
-------------
Add a new DeviationType member to introduce a new check category.
Existing handlers (fault-hint bridge, UI, future AI layer) automatically
receive events of the new type; they can choose to handle or ignore it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class DeviationType(str, Enum):
    """
    Known categories of expectation deviation.

    Using ``str`` as a mixin makes instances directly JSON-serialisable
    and human-readable in log output.

    Members
    -------
    MISSING_EXPECTED_MESSAGE
        A required message was never received during the session.
    UNEXPECTED_SOURCE_ADDRESS
        A message arrived from a source address other than the expected one.
    ABNORMAL_CYCLE_TIME
        A message's inter-arrival time fell outside the allowed tolerance.
    FIXED_VALUE_MISMATCH
        A byte in the message payload did not match the expected fixed value.
    """

    MISSING_EXPECTED_MESSAGE = "MissingExpectedMessage"
    UNEXPECTED_SOURCE_ADDRESS = "UnexpectedSourceAddress"
    ABNORMAL_CYCLE_TIME = "AbnormalCycleTime"
    FIXED_VALUE_MISMATCH = "FixedValueMismatch"


@dataclass(frozen=True)
class DeviationEvent:
    """
    A single detected deviation from an expectation.

    Attributes
    ----------
    deviation_type : DeviationType
        Category of the deviation.
    message_id : int
        CAN arbitration ID of the message involved.
    label : str
        Human-readable message label from the spec (e.g. "A", "EngineSpeed").
    severity : str
        One of "error", "warning", "info".
    message : str
        Human-readable description suitable for display or logging.
    detail : dict
        Structured key/value pairs for programmatic use (e.g. by a future AI
        analysis layer or a report generator).  Always a plain dict so it can
        be JSON-serialised directly.
    """

    deviation_type: DeviationType
    message_id: int
    label: str
    severity: str
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationSummary:
    """
    Aggregated result of running ExpectationValidator over a session.

    Attributes
    ----------
    scenario_name : str
        Name of the scenario as supplied in ExpectationSpec.
    deviations : list of DeviationEvent
        All deviation events produced during the session (feed + finalize).
    total_deviations : int
        Total number of deviations (convenience counter).
    by_type : dict
        DeviationType.value → count mapping for quick breakdowns.
    passed : bool
        True when no deviations were found (total_deviations == 0).
    """

    scenario_name: str = "default"
    deviations: List[DeviationEvent] = field(default_factory=list)
    total_deviations: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    passed: bool = True
