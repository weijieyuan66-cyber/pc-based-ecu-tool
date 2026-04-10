"""
decode/dbc_decoder.py
---------------------
DBC-based CAN signal decoder.

Wraps the cantools library to load a DBC file and decode signal values from
raw CAN frames.  cantools is listed in requirements.txt; if it is not
installed the decoder reports itself as not loaded and frames pass through
undecoded (no crash).

Usage
-----
    decoder = DBCDecoder()
    decoder.load("path/to/my.dbc")      # optional; skip for raw-only view
    frame = DecodedFrame(raw=msg)
    decoder.decode(frame)               # modifies frame in-place
    # frame.signals now contains named engineering values
    # frame.decode_source == "dbc"

If no DBC file is loaded, decode() is a no-op and returns the frame
unchanged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from decode.frame_record import DecodedFrame, DecodedSignal

logger = logging.getLogger(__name__)


class DBCDecoder:
    """
    Decodes CAN frame signals using a loaded DBC database.

    Parameters
    ----------
    dbc_path : str or None
        Path to a .dbc file.  None means no file is loaded yet.
    """

    def __init__(self, dbc_path: Optional[str] = None) -> None:
        self._db = None
        self._path: Optional[str] = None
        if dbc_path:
            self.load(dbc_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, dbc_path: str) -> None:
        """
        Load a DBC file.

        Raises
        ------
        ImportError
            If cantools is not installed.
        ValueError
            If the file cannot be parsed.
        FileNotFoundError
            If the file does not exist.
        """
        path = Path(dbc_path)
        if not path.exists():
            raise FileNotFoundError(f"DBC file not found: {dbc_path}")

        try:
            import cantools  # noqa: PLC0415 (lazy import intentional)
        except ImportError as exc:
            raise ImportError(
                "cantools is required for DBC decoding.  "
                "Install it with:  pip install cantools"
            ) from exc

        try:
            self._db = cantools.database.load_file(str(path))
            self._path = str(path)
            logger.info("DBC loaded: %s (%d messages)", path.name, len(self._db.messages))
        except Exception as exc:
            raise ValueError(f"Failed to parse DBC file '{dbc_path}': {exc}") from exc

    @property
    def is_loaded(self) -> bool:
        """True when a DBC database is loaded and decode is available."""
        return self._db is not None

    @property
    def loaded_path(self) -> Optional[str]:
        """Path of the currently loaded DBC file, or None."""
        return self._path

    def decode(self, frame: DecodedFrame) -> DecodedFrame:
        """
        Attempt to decode signals in *frame* using the loaded DBC database.

        Modifies *frame* in-place:
          - Appends to frame.signals any signals found for the frame's ID.
          - Sets frame.decode_source to "dbc" if at least one signal was decoded.

        If no DBC is loaded, or the frame ID is not in the DBC, the frame
        is returned unchanged.

        Parameters
        ----------
        frame : DecodedFrame
            The frame to decode.  frame.raw must be a valid can.Message.

        Returns
        -------
        DecodedFrame
            The same frame object (modified in-place).
        """
        if not self.is_loaded:
            return frame

        try:
            db_msg = self._db.get_message_by_frame_id(frame.raw.arbitration_id)
        except KeyError:
            return frame  # Unknown ID — leave as raw

        try:
            decoded = db_msg.decode(bytes(frame.raw.data), decode_choices=False)
        except Exception as exc:
            logger.debug(
                "DBC decode error for ID 0x%X: %s", frame.raw.arbitration_id, exc
            )
            return frame

        signals = []
        for sig_name, raw_or_scaled in decoded.items():
            try:
                sig_def = db_msg.get_signal_by_name(sig_name)
                unit = sig_def.unit or ""
            except Exception:
                unit = ""
            signals.append(
                DecodedSignal(
                    name=sig_name,
                    value=float(raw_or_scaled),
                    unit=unit,
                )
            )

        frame.signals.extend(signals)
        if signals:
            frame.decode_source = "dbc"

        return frame
