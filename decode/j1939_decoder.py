"""
decode/j1939_decoder.py
-----------------------
J1939 PGN / source-address extractor.

Inspects 29-bit extended CAN IDs and extracts:
  - Priority       (3 bits, bits 28-26)
  - Data Page (DP) (1 bit,  bit  24)
  - PDU Format (PF)(8 bits, bits 23-16)
  - PDU Specific   (8 bits, bits 15-8)
  - Source Address (8 bits, bits  7-0)
  - PGN            (derived from DP + PF + PS, see below)

J1939 PDU format rules
----------------------
  PDU2 (PF >= 0xF0): PGN = (DP << 16) | (PF << 8) | PS
                     PS is a group extension, not a destination address
  PDU1 (PF <  0xF0): PGN = (DP << 16) | (PF << 8)
                     PS is the destination address (not part of the PGN)

This module also provides J1939_PGN_NAMES, a lookup table covering the
most common J1939 PGNs used in automotive bench testing.

No additional libraries are required — this module uses only the stdlib.
"""

from __future__ import annotations

from typing import Optional

from decode.frame_record import DecodedFrame

# ---------------------------------------------------------------------------
# J1939 PGN name lookup table
# ---------------------------------------------------------------------------
# Key: PGN (int).  Value: short human-readable name.
# Subset of SAE J1939-71 covering PGNs commonly seen on automotive benches.

J1939_PGN_NAMES: dict = {
    # Engine
    0x00F004: "EEC1 — Electronic Engine Controller 1",
    0x00F003: "EEC2 — Electronic Engine Controller 2",
    0x00FEF2: "CCVS — Cruise Control / Vehicle Speed",
    0x00FEF1: "LFE  — Fuel Economy (Liquid)",
    0x00FEEE: "ET1  — Engine Temperature 1",
    0x00FEEF: "EFL  — Engine Fluid Level / Pressure 1",
    0x00FEF7: "VEP1 — Vehicle Electrical Power 1",
    0x00FEF6: "TCI  — Transmission Current Gear",
    0x00FECA: "DM1  — Diagnostic Message 1 (Active DTCs)",
    0x00FECB: "DM2  — Diagnostic Message 2 (Previously Active DTCs)",
    0x00FECC: "DM3  — Diagnostic Message 3 (Previously Active DTCs Clear)",
    0x00FECE: "DM5  — Diagnostic Readiness 1",
    0x00FEED: "HOURS — Engine Hours / Revolutions",
    0x00FEE5: "ET3  — Engine Temperature 3",
    0x00FEE6: "IC1  — Inlet/Exhaust Conditions 1",
    0x00FEE9: "LBC  — Auxiliary Input/Output Status",
    0x00FEEA: "AMB  — Ambient Conditions",
    0x00FEEC: "VI   — Vehicle Identification",
    0x00FEF0: "ETC1 — Electronic Transmission Controller 1",
    0x00FEDF: "EEC3 — Electronic Engine Controller 3",
    0x00FE6B: "SERV — Service Information",
    # Transport Protocol (address-specific, PDU1)
    0x00EC00: "TP.CM — Transport Protocol Connection Management",
    0x00EB00: "TP.DT — Transport Protocol Data Transfer",
    # Request PGN
    0x00EA00: "RQST — Request",
    # ACK
    0x00E800: "ACK  — Acknowledgement",
    # Address Claim
    0x00EE00: "AC   — Address Claimed",
}


# ---------------------------------------------------------------------------
# PGN extraction helpers
# ---------------------------------------------------------------------------

def extract_pgn(arbitration_id: int) -> Optional[int]:
    """
    Extract the J1939 PGN from a 29-bit CAN identifier.

    Returns None if the ID is not a valid 29-bit J1939 frame (caller should
    check is_extended_id before calling this function, but the function is
    safe regardless).

    Parameters
    ----------
    arbitration_id : int
        The 29-bit (or 11-bit) CAN arbitration ID.

    Returns
    -------
    int or None
        The PGN (0 … 0x3FFFF) or None.
    """
    if arbitration_id > 0x1FFFFFFF:
        return None  # Not a valid 29-bit ID

    dp = (arbitration_id >> 24) & 0x01
    pf = (arbitration_id >> 16) & 0xFF

    if pf >= 0xF0:
        # PDU2: PS is group extension — PS is part of the PGN
        ps = (arbitration_id >> 8) & 0xFF
        return (dp << 16) | (pf << 8) | ps
    else:
        # PDU1: PS is destination address — not part of the PGN
        return (dp << 16) | (pf << 8)


def extract_source_address(arbitration_id: int) -> int:
    """Extract the J1939 source address (bits 7-0) from a 29-bit ID."""
    return arbitration_id & 0xFF


# ---------------------------------------------------------------------------
# J1939Decoder
# ---------------------------------------------------------------------------

class J1939Decoder:
    """
    Enriches DecodedFrame objects with J1939 PGN information.

    Operates on 29-bit extended-ID frames only.  Standard 11-bit frames
    are returned unchanged.

    Does NOT decode individual SPNs (signal values).  SPN decoding requires
    a J1939 DBC or SPN database and is handled by DBCDecoder when a DBC
    file is loaded.  This decoder focuses on PGN identification and
    source-address extraction.
    """

    def decode(self, frame: DecodedFrame) -> DecodedFrame:
        """
        Identify the J1939 PGN and source address in *frame*.

        Modifies *frame* in-place:
          - Sets frame.pgn to the extracted PGN (int).
          - Sets frame.pgn_name to a human-readable name (or None).
          - Sets frame.source_address to the SA byte.
          - Sets frame.decode_source to "j1939" if previously "raw".

        11-bit (standard) ID frames are returned without modification.

        Parameters
        ----------
        frame : DecodedFrame

        Returns
        -------
        DecodedFrame
            The same frame object (modified in-place).
        """
        if not frame.raw.is_extended_id:
            return frame

        pgn = extract_pgn(frame.raw.arbitration_id)
        if pgn is None:
            return frame

        frame.pgn = pgn
        frame.pgn_name = J1939_PGN_NAMES.get(pgn)
        frame.source_address = extract_source_address(frame.raw.arbitration_id)

        # Upgrade decode_source only if DBC hasn't already claimed it
        if frame.decode_source == "raw":
            frame.decode_source = "j1939"

        return frame
