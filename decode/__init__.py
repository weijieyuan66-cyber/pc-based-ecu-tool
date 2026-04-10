"""
decode/
-------
CAN frame decode layer.

Components
----------
  frame_record   -- DecodedFrame / DecodedSignal data classes
  dbc_decoder    -- DBC-based signal decoding via cantools (optional)
  j1939_decoder  -- J1939 PGN / SA extraction and name lookup

Usage
-----
    from decode.frame_record import DecodedFrame
    from decode.dbc_decoder import DBCDecoder
    from decode.j1939_decoder import J1939Decoder

    frame = DecodedFrame(raw=msg)
    dbc.decode(frame)      # enriches frame.signals (if DBC loaded)
    j1939.decode(frame)    # enriches frame.pgn / frame.pgn_name
"""
