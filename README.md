# PC-based ECU Communication Tool

A lightweight Python project for **authorized static bench testing only**.

## Release 1 — Multi-Backend Foundation

This release adds a clean multi-backend architecture so the tool is not tied
to any single hardware vendor.  All UI, decode, and rule logic talks only to
the `CANBackend` abstraction layer — never to vendor-specific APIs directly.

### Supported backends

| Backend   | Status              | When to use                                  |
|-----------|---------------------|----------------------------------------------|
| `virtual` | ✅ Active            | Development, self-test, regression testing   |
| `pcan`    | 🔧 Hardware-ready   | PEAK PCAN-USB (install driver + hardware)    |
| `vector`  | 🔧 Hardware-ready   | Vector VN-series / CANalyzer hardware        |

### How to run (virtual self-test — no hardware required)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run CLI self-test
python main.py

# 3. Run desktop UI
python main.py --ui
```

Expected CLI output:

```
================================================================
  Self-Test Results
================================================================
  Timestamp        CAN ID     DLC   Data (hex)
----------------------------------------------------------------
  14:22:05.123     7E8        8     02 10 01 00 00 00 00 00
  14:22:05.234     123        4     DE AD BE EF
  14:22:05.345     18DA00F1   8     01 3E 00 00 00 00 00 00 [EXT]
----------------------------------------------------------------
  Result  : PASS
  Sent    : 3
  Received: 3
================================================================
```

### How to switch backends

Edit `config/settings.example.json`:

```json
{
  "backend": "pcan",
  "backends": {
    "pcan": {
      "channel": "PCAN_USBBUS1",
      "bitrate": 500000
    }
  }
}
```

| Hardware        | `backend` | Channel example    | Driver required              |
|-----------------|-----------|--------------------|------------------------------|
| Virtual (dev)   | `virtual` | `test_channel`     | None                         |
| PEAK PCAN-USB   | `pcan`    | `PCAN_USBBUS1`     | PCAN-Basic from peak-system  |
| Vector VN-USB   | `vector`  | `0`                | XL Driver from vector.com    |

No Python code changes are required to switch backends.

### When PCAN / Vector hardware is not available

Clicking **Connect** in the UI (or running in a non-virtual mode) will
produce a clear error message:

```
[WARNING] Could not connect to 'pcan': Failed to load PEAK driver …
  → Ensure the driver / hardware is installed and connected.
```

The UI remains fully usable in virtual mode regardless.

### How to load a DBC file for signal decoding

1. Install `cantools` (already in `requirements.txt`).
2. In the UI: click **Load DBC …** and select your `.dbc` file.
3. Decoded signals appear in the **Decoded Signals** tab.

CLI: DBC loading is not supported in the CLI self-test path (raw only).

### Validating decode and fault-hint logic without hardware

The virtual self-test sends 3 canonical frames.  After running it:

- **Raw Frames tab**: shows all 3 frames.
- **Decoded Signals tab**: the J1939 frame `0x18DA00F1` appears with its
  PGN extracted automatically (no DBC needed).
  If a DBC is loaded, additional named signals appear for any matching IDs.
- **Fault Hints tab**: normally empty for healthy frames.
  To test fault rules, send an error frame or load a DBC with signals
  that have defined out-of-range thresholds.

### Project structure

```text
.
├── main.py                         Entry point — orchestration only
├── requirements.txt
├── config/
│   └── settings.example.json       Multi-backend config (virtual default)
├── backend/
│   ├── base.py                     CANBackend ABC + _SingleBusBackend
│   ├── virtual.py                  VirtualBackend  (no hardware needed)
│   ├── pcan.py                     PCANBackend     (hardware-ready)
│   ├── vector.py                   VectorBackend   (hardware-ready)
│   └── factory.py                  BackendFactory.create(config)
├── core/
│   ├── receiver.py                 Blocking CAN RX loop
│   ├── transmitter.py              CAN TX — send_frame / send_frames
│   └── self_test.py                Virtual self-test orchestration
├── decode/
│   ├── frame_record.py             DecodedFrame / DecodedSignal dataclasses
│   ├── dbc_decoder.py              DBC-based signal decode (cantools)
│   └── j1939_decoder.py            J1939 PGN extraction + name lookup
├── rules/
│   ├── base_rule.py                FaultHint + FaultRule ABC
│   ├── rule_engine.py              RuleEngine — applies rules to frames
│   └── builtin_rules.py            ErrorFrameRule, SignalOutOfRangeRule, …
├── ui/
│   └── app.py                      Tkinter UI — backend selector, 3 tabs
├── app_logging/
│   └── logger.py                   Console + file logger
└── dbc/
    └── .gitkeep                    Place DBC files here (user-provided)
```

### Status

| Capability                              | Status          |
|-----------------------------------------|-----------------|
| Virtual self-test RX / TX               | ✅ Implemented   |
| Multi-backend architecture              | ✅ Implemented   |
| Backend abstraction layer               | ✅ Implemented   |
| PCAN backend (hardware-ready)           | ✅ Implemented   |
| Vector backend (hardware-ready)         | ✅ Implemented   |
| J1939 PGN decode (no DBC needed)        | ✅ Implemented   |
| DBC signal decode (cantools)            | ✅ Implemented   |
| Fault-hint rule engine                  | ✅ Implemented   |
| Error frame rule                        | ✅ Implemented   |
| Signal out-of-range rule                | ✅ Implemented   |
| UI — backend selector + connect button  | ✅ Implemented   |
| UI — Raw / Decoded / Fault Hints tabs   | ✅ Implemented   |
| Config-driven backend switching         | ✅ Implemented   |

### Out of scope (will not be implemented)

- AI chat / voice
- Full UDS / ISO-TP diagnostics
- Flashing / programming / bootloader
- Security Access
- WriteDataByIdentifier / RoutineControl / ECUReset
- Coding or calibration writing
- Any high-risk ECU control capability

### Intended use

- Static bench testing only
- Authorized ECU test setup only
- Not for real vehicle use
- Not for production use

