# PC-based ECU Communication Tool

A lightweight Python project for **authorized static bench testing only**.

## Current development phase

**Phase 1 — Virtual self-test (no hardware required)**

The project is currently running in pure-software self-test mode using the
`python-can` virtual interface. No physical CAN adapter or real ECU is needed.

## How to run (virtual self-test)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run (uses config/settings.example.json automatically)
python main.py

# 3. Stop
Ctrl+C
```

Expected output:

```
============================================================
  CAN Receiver — listening for frames
  Interface : virtual
  Channel   : test_channel
  Mode      : self_test_only
============================================================
  Timestamp        ID       DLC  Data (hex)
------------------------------------------------------------
[RX] 14:22:05.123  ID=7E8       DLC=8  Data=02 10 01 00 00 00 00 00
[RX] 14:22:05.234  ID=123       DLC=4  Data=DE AD BE EF
[RX] 14:22:05.345  ID=18DA00F1  DLC=8  Data=01 3E 00 00 00 00 00 00 [EXT]
------------------------------------------------------------
  Stopped by user. Total frames received: 3
============================================================
```

## How to switch to real hardware

Edit `config/settings.example.json`:

```json
{
  "interface": "pcan",
  "channel":   "PCAN_USBBUS1",
  "bitrate":   500000
}
```

| Hardware       | `interface`  | `channel` example  |
|----------------|--------------|--------------------|
| PEAK PCAN-USB  | `pcan`       | `PCAN_USBBUS1`     |
| Kvaser         | `kvaser`     | `0`                |
| Vector         | `vector`     | `0`                |
| SocketCAN      | `socketcan`  | `can0`             |

No Python code changes are required.

## MVP scope

| Capability                        | Status        |
|-----------------------------------|---------------|
| Virtual self-test RX              | ✅ Implemented |
| Config-driven interface switching | ✅ Implemented |
| Single-frame TX                   | 🔜 Next step   |
| TX/RX file logging                | 🔜 Next step   |
| DBC parsing                       | ⬜ Placeholder  |

## Out of scope (will not be implemented)

- Full UDS / ISO-TP diagnostics
- Flashing / programming / bootloader
- Security Access
- WriteDataByIdentifier / RoutineControl / ECUReset
- Coding or calibration writing
- Any high-risk ECU control capability

## Intended use

- Static bench testing only
- Authorized ECU test setup only
- Not for real vehicle use
- Not for production use

## Project structure

```text
.
├── main.py                    Entry point
├── requirements.txt
├── config/
│   └── settings.example.json  Interface config (virtual → real by config only)
├── core/
│   ├── receiver.py            Blocking CAN RX loop
│   └── transmitter.py         TX skeleton (next phase)
├── app_logging/
│   └── logger.py              Console + file logger
├── dbc/
│   └── .gitkeep               Placeholder for future DBC parser
└── logs/                      Created at runtime
```

