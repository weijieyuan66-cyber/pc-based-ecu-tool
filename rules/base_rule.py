"""
rules/base_rule.py
------------------
FaultHint data class and FaultRule abstract base class.

Design
------
- FaultHint is a plain, immutable result object returned by rules.
- FaultRule is the contract every rule must implement.
- Rules are pure functions: given a DecodedFrame, return a FaultHint or None.
- Rules must never raise.  Internal errors should be caught and logged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from decode.frame_record import DecodedFrame


@dataclass(frozen=True)
class FaultHint:
    """
    A single fault detection result produced by a FaultRule.

    Attributes
    ----------
    rule_id : str
        Unique rule identifier string (e.g. "builtin.error_frame").
    severity : str
        One of "info", "warning", "error".
    message : str
        Human-readable description of the detected condition.
    frame_id : int or None
        CAN arbitration ID of the frame that triggered the hint, or None.
    signal_name : str or None
        Name of the signal involved (if applicable), or None.
    """

    rule_id: str
    severity: str       # "info" | "warning" | "error"
    message: str
    frame_id: Optional[int] = None
    signal_name: Optional[str] = None


class FaultRule(ABC):
    """
    Abstract base class for fault-hint rules.

    Each rule evaluates one DecodedFrame and returns either a FaultHint
    describing the detected condition, or None when the rule does not fire.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique rule identifier string."""

    @abstractmethod
    def evaluate(self, frame: DecodedFrame) -> Optional[FaultHint]:
        """
        Evaluate the rule against one frame.

        Parameters
        ----------
        frame : DecodedFrame
            The frame to evaluate.

        Returns
        -------
        FaultHint or None
            A hint when the rule fires; None otherwise.
        """
