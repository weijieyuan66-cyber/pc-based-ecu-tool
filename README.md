# PC-based ECU Communication Tool

A lightweight Python project for **authorized static bench testing only**.

## Current MVP scope

This project currently targets only the following basic capabilities:

- Receive raw CAN / CAN FD messages from an ECU
- Send raw single-frame CAN / CAN FD messages from a PC to an ECU
- Print basic TX/RX logs
- Keep the structure extensible for future additions such as DBC parsing

## Current limitations

This project does **not** implement:

- Full UDS / ISO-TP diagnostics
- Flashing / programming / bootloader features
- Security Access
- WriteDataByIdentifier
- RoutineControl
- ECUReset
- Coding / calibration writing
- Any high-risk ECU control capability

## Intended use

- Static bench testing only
- Authorized ECU test setup only
- Not for real vehicle use
- Not for production use

## Initial project structure

```text
.
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ main.py
├─ core/
│  ├─ __init__.py
│  ├─ receiver.py
│  └─ transmitter.py
├─ app_logging/
│  ├─ __init__.py
│  └─ logger.py
├─ config/
│  └─ settings.example.json
└─ dbc/
   └─ .gitkeep
