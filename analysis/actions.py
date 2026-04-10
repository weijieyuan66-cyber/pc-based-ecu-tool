"""
analysis/actions.py
-------------------
Enumerations and data classes representing future analysis actions,
requests, results, and the state machine that governs the analysis lifecycle.

Nothing here is wired to an actual AI model — this is a reservation layer.

Classes
-------
AnalysisAction  -- enum of supported action types
AnalysisState   -- enum of analysis lifecycle states
AnalysisRequest -- input object for a future analysis invocation
AnalysisResult  -- unified output object for both rule-based and AI results
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from analysis.context import AnalysisContext


class AnalysisAction(Enum):
    """
    Supported future analysis action types.

    Members
    -------
    ANALYZE_CURRENT_SESSION
        Analyse the full current session (frames, decodes, faults).
    EXPLAIN_SELECTED_FAULT
        Produce a human-readable explanation of the selected fault hint.
    GENERATE_REPORT
        Generate a structured session report (JSON / PDF / text).
    """

    ANALYZE_CURRENT_SESSION = auto()
    EXPLAIN_SELECTED_FAULT = auto()
    GENERATE_REPORT = auto()


class AnalysisState(Enum):
    """
    Lifecycle states of the analysis subsystem.

    Members
    -------
    IDLE       -- no analysis has been requested yet
    READY      -- context is populated; ready to accept a request
    ANALYZING  -- an analysis is in progress
    COMPLETED  -- analysis finished successfully
    FAILED     -- analysis encountered an error
    DISABLED   -- AI / analysis subsystem is disabled (placeholder state)
    """

    IDLE = auto()
    READY = auto()
    ANALYZING = auto()
    COMPLETED = auto()
    FAILED = auto()
    DISABLED = auto()


@dataclass
class AnalysisRequest:
    """
    Represents a single future analysis request.

    Attributes
    ----------
    action : AnalysisAction
        Which analysis action to perform.
    context : AnalysisContext
        The analysis context snapshot at the time of the request.
    source : str
        What triggered the request: "button" | "chat" | "voice" | "api".
        Currently only "button" will be used.
    extra : dict
        Optional additional parameters specific to the action type.
    """

    action: AnalysisAction
    context: AnalysisContext
    source: str = "button"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """
    Unified output object for both rule-based and AI-based analysis.

    Designed to be suitable for any future analysis backend so that the UI
    layer never needs to distinguish between them.

    Attributes
    ----------
    action : AnalysisAction
        The action that produced this result.
    state : AnalysisState
        Final state after the analysis (COMPLETED or FAILED).
    summary : str
        Short human-readable summary (one sentence / headline).
    detail : str
        Full human-readable output (may be multi-line markdown text).
    structured : dict
        Machine-readable structured output (for report generation).
    error : str or None
        Error message when state is FAILED; None otherwise.
    """

    action: AnalysisAction
    state: AnalysisState
    summary: str = ""
    detail: str = ""
    structured: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
