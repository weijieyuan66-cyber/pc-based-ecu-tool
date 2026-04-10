"""
rules/rule_engine.py
--------------------
RuleEngine: applies a list of FaultRule instances to a single DecodedFrame.

Design
------
- Rules are evaluated in registration order.
- All errors inside individual rules are caught and logged; one bad rule
  never prevents others from running.
- The engine is intentionally stateless between calls — each call to
  evaluate() is independent.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from decode.frame_record import DecodedFrame
from rules.base_rule import FaultHint, FaultRule

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Applies all registered FaultRule instances to a decoded CAN frame.

    Parameters
    ----------
    rules : list of FaultRule, optional
        Initial list of rules.  Additional rules can be added later via
        add_rule().
    """

    def __init__(self, rules: Optional[List[FaultRule]] = None) -> None:
        self._rules: List[FaultRule] = list(rules) if rules else []

    def add_rule(self, rule: FaultRule) -> None:
        """Append a rule to the evaluation list."""
        self._rules.append(rule)

    @property
    def rules(self) -> List[FaultRule]:
        """Read-only view of the registered rules list."""
        return list(self._rules)

    def evaluate(self, frame: DecodedFrame) -> List[FaultHint]:
        """
        Run all rules against *frame* and return the triggered hints.

        Parameters
        ----------
        frame : DecodedFrame
            The frame to evaluate.

        Returns
        -------
        list of FaultHint
            All hints produced by rules that fired.  Empty list when no
            rules fire.
        """
        hints: List[FaultHint] = []
        for rule in self._rules:
            try:
                hint = rule.evaluate(frame)
                if hint is not None:
                    hints.append(hint)
            except Exception as exc:
                logger.error(
                    "Rule '%s' raised an unexpected error: %s",
                    rule.rule_id, exc,
                )
        return hints
