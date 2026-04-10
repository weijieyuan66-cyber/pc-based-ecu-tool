"""
analysis/context.py
-------------------
Data structures that aggregate the current session state and serve as the
context payload for future AI / rule-based analysis.

All classes are plain, serialisation-friendly data containers.  They are
populated by the UI layer and passed to AnalysisRequest when an analysis
action is triggered.

Classes
-------
SelectedObjectContext  -- the item currently selected in the UI
FaultHintSummary       -- aggregated fault-hint statistics
SessionSummary         -- per-session frame / decode / fault statistics
AnalysisContext        -- top-level context object combining all of the above
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SelectedObjectContext:
    """
    Captures whatever the user has currently selected in the UI.

    All fields are optional; only the relevant one(s) will be set at any
    given moment.

    Attributes
    ----------
    raw_frame : dict or None
        Snapshot of the selected raw CAN frame (serialisable form).
    decoded_message : dict or None
        Snapshot of the selected decoded message / signal row.
    fault_hint : dict or None
        Snapshot of the selected fault hint row.
    """

    raw_frame: Optional[Dict[str, Any]] = None
    decoded_message: Optional[Dict[str, Any]] = None
    fault_hint: Optional[Dict[str, Any]] = None


@dataclass
class FaultHintSummary:
    """
    Aggregated statistics over all fault hints accumulated in the session.

    Attributes
    ----------
    total : int
        Total number of fault hints triggered.
    by_severity : dict
        Counts keyed by severity string ("error", "warning", "info").
    by_rule_id : dict
        Counts keyed by rule_id string.
    by_frame_id : dict
        Counts keyed by frame arbitration ID (as hex string).
    by_signal : dict
        Counts keyed by signal name string.
    top_faults : list of dict
        Up to 5 most-frequent (rule_id, severity, message) entries.
    """

    total: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_rule_id: Dict[str, int] = field(default_factory=dict)
    by_frame_id: Dict[str, int] = field(default_factory=dict)
    by_signal: Dict[str, int] = field(default_factory=dict)
    top_faults: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SessionSummary:
    """
    High-level statistics for the current analysis session.

    Attributes
    ----------
    frame_count : int
        Total raw CAN frames received.
    decoded_count : int
        Frames that were successfully decoded (DBC or J1939).
    fault_count : int
        Total fault hints triggered.
    top_messages : list of dict
        Up to 5 most-seen CAN IDs with counts.
    fault_summary : FaultHintSummary
        Detailed fault breakdown.
    session_start_iso : str
        ISO-8601 timestamp of when the session started (or empty string).
    session_end_iso : str
        ISO-8601 timestamp of when the session ended / snapshot was taken.
    """

    frame_count: int = 0
    decoded_count: int = 0
    fault_count: int = 0
    top_messages: List[Dict[str, Any]] = field(default_factory=list)
    fault_summary: FaultHintSummary = field(default_factory=FaultHintSummary)
    session_start_iso: str = ""
    session_end_iso: str = ""


@dataclass
class AnalysisContext:
    """
    Top-level context object aggregating all information available at the time
    an analysis action is triggered.

    This object is the single source of truth passed from the UI layer to the
    future AI / report layer.

    Attributes
    ----------
    connection_state : str
        Current backend connection state: "connected" | "disconnected".
    backend_name : str
        Name of the active backend ("virtual", "pcan", "vector", etc.).
    dbc_loaded : bool
        True when a DBC file has been loaded successfully.
    dbc_filename : str
        Basename of the loaded DBC file, or empty string.
    recent_raw_frames : list of dict
        Snapshot of the most recent raw frame rows (up to a fixed window).
    recent_decoded_frames : list of dict
        Snapshot of the most recent decoded rows (up to a fixed window).
    fault_hints : list of dict
        All fault hints accumulated in the current session.
    selected_object : SelectedObjectContext
        Currently selected UI object.
    session_summary : SessionSummary
        Per-session statistics snapshot.
    session_time_window_s : float
        Approximate length of the captured session in seconds.
    """

    connection_state: str = "disconnected"
    backend_name: str = ""
    dbc_loaded: bool = False
    dbc_filename: str = ""
    recent_raw_frames: List[Dict[str, Any]] = field(default_factory=list)
    recent_decoded_frames: List[Dict[str, Any]] = field(default_factory=list)
    fault_hints: List[Dict[str, Any]] = field(default_factory=list)
    selected_object: SelectedObjectContext = field(default_factory=SelectedObjectContext)
    session_summary: SessionSummary = field(default_factory=SessionSummary)
    session_time_window_s: float = 0.0
