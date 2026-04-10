"""
validation/specs.py
-------------------
Pure data containers that describe what behaviour is expected from the
CAN bus during a given test or operating scenario.

These classes have no imports from the transport layer, the UI, or any
decode layer.  They can therefore be constructed from JSON / YAML config,
from a UI form, from a test script, or from a future AI-generated plan —
all without coupling to any specific environment.

Classes
-------
ExpectedFieldConstraint
    A constraint on one byte position within a frame payload.

ExpectedMessageSpec
    All expectations for a single CAN message (presence, source address,
    cycle time, field values).

ExpectationSpec
    Top-level scenario container: a named collection of ExpectedMessageSpec
    entries.

Extensibility
-------------
To add a new kind of check later (e.g. DLC constraint, sequence ordering),
add a new field to ExpectedMessageSpec (or a new sub-dataclass) and handle
it in ExpectationValidator.feed() / finalize().  No existing callers change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExpectedFieldConstraint:
    """
    A constraint on a specific byte within a CAN frame payload.

    Attributes
    ----------
    field_index : int
        Zero-based byte index within frame.data.
    expected_value : int
        Expected raw byte value (0–255).
    mask : int
        Bitmask applied to the raw byte before comparison.
        Default 0xFF means all bits must match.
    field_name : str
        Human-readable name used in deviation messages (e.g. "X", "Status").
    """

    field_index: int
    expected_value: int
    mask: int = 0xFF
    field_name: str = "field"


@dataclass(frozen=True)
class ExpectedMessageSpec:
    """
    All expectations for a single CAN message.

    Attributes
    ----------
    message_id : int
        CAN arbitration ID to match.
    label : str
        Human-readable name (e.g. "A", "EngineSpeed").  Used in reports.
    required : bool
        When True, the message MUST appear at least once; a
        MissingExpectedMessage deviation is raised at finalize() if not seen.
    expected_source_address : int or None
        J1939 source address expected in DecodedFrame.source_address.
        None means "do not check source address".
    expected_cycle_time_ms : float or None
        Expected inter-arrival period in milliseconds.
        None means "do not check timing".
    cycle_time_tolerance_pct : float
        Allowed deviation from expected_cycle_time_ms expressed as a
        percentage (default 20 %).  A cycle time is flagged when it falls
        outside [expected × (1 − tol), expected × (1 + tol)].
    field_constraints : tuple of ExpectedFieldConstraint
        Zero or more byte-level value constraints checked on every frame.
    """

    message_id: int
    label: str
    required: bool = True
    expected_source_address: Optional[int] = None
    expected_cycle_time_ms: Optional[float] = None
    cycle_time_tolerance_pct: float = 20.0
    field_constraints: Tuple[ExpectedFieldConstraint, ...] = ()


@dataclass
class ExpectationSpec:
    """
    Top-level container for all message expectations in a scenario.

    Attributes
    ----------
    messages : list of ExpectedMessageSpec
        One entry per expected CAN message.  Messages not listed here are
        ignored by the validator (use UnexpectedFrameIdRule for that).
    scenario_name : str
        Optional human-readable name (used in ValidationSummary and logs).
    """

    messages: List[ExpectedMessageSpec] = field(default_factory=list)
    scenario_name: str = "default"
