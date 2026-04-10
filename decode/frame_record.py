"""
decode/frame_record.py
----------------------
Data classes for decoded CAN frames.

DecodedFrame wraps a raw can.Message together with everything the decode
layer has extracted from it:
  - J1939 PGN and name (if J1939 extended ID)
  - Named signals with engineering values (if decoded via DBC or J1939 SPN)
  - The decode source that produced the signals

These classes are plain data containers.  No decode logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import can


@dataclass
class DecodedSignal:
    """
    A single decoded signal extracted from a CAN frame.

    Attributes
    ----------
    name : str
        Signal name as defined in the DBC or J1939 SPN table.
    value : float
        Decoded engineering value (after scaling and offset).
    unit : str
        Engineering unit string, e.g. "rpm", "°C", "V".
    raw_value : int
        Raw bit-pattern value before scaling/offset.
    """

    name: str
    value: float
    unit: str = ""
    raw_value: int = 0


@dataclass
class DecodedFrame:
    """
    A CAN frame enriched with decode information.

    Attributes
    ----------
    raw : can.Message
        The original unmodified frame from the bus.
    pgn : int or None
        J1939 Parameter Group Number extracted from the 29-bit ID, or None
        if the frame is not a J1939 extended-ID frame.
    pgn_name : str or None
        Human-readable J1939 PGN name, or None if unknown or not applicable.
    source_address : int or None
        J1939 source address byte (bits 7-0 of the 29-bit ID), or None.
    signals : list of DecodedSignal
        Decoded signals.  Empty if no DBC or SPN decode is available.
    decode_source : str
        Which layer produced the signals:
          "raw"    -- no decode performed
          "dbc"    -- decoded from a loaded DBC file
          "j1939"  -- identified via J1939 PGN lookup
    """

    raw: can.Message
    pgn: Optional[int] = None
    pgn_name: Optional[str] = None
    source_address: Optional[int] = None
    signals: List[DecodedSignal] = field(default_factory=list)
    decode_source: str = "raw"
