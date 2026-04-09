"""
ui/app.py
---------
Phase 4: Minimal Tkinter desktop UI for the virtual CAN self-test.

Layout (top to bottom)
-----------------------
  Config info bar   -- shows current mode / interface / channel / bitrate
  Run Self-Test btn -- triggers the test; disabled while test is running
  Frame table       -- Treeview: Timestamp | CAN ID | DLC | Data | Flags
  PASS / FAIL label -- large, colour-coded result badge
  Log area          -- scrollable read-only text area

Design constraints
------------------
- All core logic lives in core/self_test.py.  This file contains only UI.
- The test runs in a background thread so the UI stays responsive.
- Results are posted back to the main thread via Tk.after(0, callback).
- Tkinter is part of Python's standard library -- no extra dependency needed.
- CLI mode (python main.py) continues to work unchanged.
"""

import datetime
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from app_logging.logger import setup_logger
from core.self_test import SelfTestResult, run_virtual_self_test
from main import load_config

_CONFIG_PATH = "config/settings.example.json"


class SelfTestApp(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("PC-based ECU Tool -- Virtual Self-Test")
        self.resizable(True, True)
        self.minsize(720, 520)

        self._logger = setup_logger("ecu_tool_ui")
        try:
            self._config = load_config(_CONFIG_PATH)
        except FileNotFoundError as exc:
            self._config = {}
            print(f"[WARNING] Config not found: {exc}")

        self._running = False
        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI construction                                                       #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # -- Config info bar ---------------------------------------------- #
        info_frame = tk.Frame(self, bd=1, relief=tk.RIDGE)
        info_frame.pack(fill=tk.X, **pad)

        cfg = self._config
        info_text = (
            f"Mode: {cfg.get('app_mode', 'N/A')}    "
            f"Interface: {cfg.get('interface', 'N/A')}    "
            f"Channel: {cfg.get('channel', 'N/A')}    "
            f"Bitrate: {cfg.get('bitrate', 'N/A')}"
        )
        tk.Label(
            info_frame, text=info_text, anchor="w", font=("Courier", 9)
        ).pack(fill=tk.X, padx=6, pady=4)

        # -- Run button + status label ------------------------------------- #
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, **pad)

        self._btn_run = tk.Button(
            btn_frame,
            text="Run Self-Test",
            font=("TkDefaultFont", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388E3C",
            activeforeground="white",
            command=self._on_run,
        )
        self._btn_run.pack(side=tk.LEFT, padx=(0, 12), ipadx=10, ipady=4)

        self._lbl_status = tk.Label(btn_frame, text="Ready", anchor="w")
        self._lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # -- Frame table -------------------------------------------------- #
        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        columns = ("timestamp", "can_id", "dlc", "data", "flags")
        self._tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=8
        )
        col_cfg = [
            ("timestamp", "Timestamp",  160, tk.W),
            ("can_id",    "CAN ID",      90, tk.CENTER),
            ("dlc",       "DLC",          40, tk.CENTER),
            ("data",      "Data (hex)",  320, tk.W),
            ("flags",     "Flags",        60, tk.CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self._tree.heading(cid, text=heading)
            self._tree.column(cid, width=width, anchor=anchor, stretch=True)

        vsb = ttk.Scrollbar(
            table_frame, orient=tk.VERTICAL, command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # -- PASS / FAIL result label ------------------------------------- #
        self._lbl_result = tk.Label(
            self,
            text="--",
            font=("TkDefaultFont", 16, "bold"),
            width=20,
        )
        self._lbl_result.pack(pady=(0, 4))

        # -- Log area ----------------------------------------------------- #
        tk.Label(self, text="Log", anchor="w").pack(fill=tk.X, padx=8)
        self._log_area = scrolledtext.ScrolledText(
            self,
            height=7,
            state=tk.DISABLED,
            font=("Courier", 9),
        )
        self._log_area.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))

    # ------------------------------------------------------------------ #
    # Button handler                                                        #
    # ------------------------------------------------------------------ #

    def _on_run(self) -> None:
        if self._running:
            return
        self._running = True
        self._btn_run.config(state=tk.DISABLED)
        self._lbl_status.config(text="Running ...")
        self._lbl_result.config(text="--", fg="black")

        # Clear previous results
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._log_clear()
        self._log_append("Starting self-test ...")

        threading.Thread(
            target=self._run_test_thread,
            daemon=True,
            name="ui-self-test",
        ).start()

    # ------------------------------------------------------------------ #
    # Background worker thread                                             #
    # ------------------------------------------------------------------ #

    def _run_test_thread(self) -> None:
        try:
            result = run_virtual_self_test(self._config, self._logger)
        except Exception as exc:
            self.after(0, self._on_test_error, str(exc))
            return
        self.after(0, self._on_test_done, result)

    # ------------------------------------------------------------------ #
    # UI-update callbacks (always executed on the main thread via after()) #
    # ------------------------------------------------------------------ #

    def _on_test_done(self, result: SelfTestResult) -> None:
        for msg in result.received_frames:
            self._add_frame_row(msg)
        for line in result.log_lines:
            self._log_append(line)

        if result.passed:
            self._lbl_result.config(text="PASS", fg="#2E7D32")
        else:
            self._lbl_result.config(
                text=f"FAIL  ({len(result.received_frames)}/{result.sent_count})",
                fg="#C62828",
            )

        summary = (
            f"Done -- {len(result.received_frames)}/{result.sent_count} "
            "frame(s) received"
        )
        self._lbl_status.config(text=summary)
        self._btn_run.config(state=tk.NORMAL)
        self._running = False

    def _on_test_error(self, message: str) -> None:
        self._log_append(f"ERROR: {message}")
        self._lbl_result.config(text="ERROR", fg="#C62828")
        self._lbl_status.config(text="Error -- see log")
        self._btn_run.config(state=tk.NORMAL)
        self._running = False

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _add_frame_row(self, msg: object) -> None:
        """Insert one received CAN frame into the Treeview table."""
        ts = getattr(msg, "timestamp", None)
        if ts is None:
            ts = datetime.datetime.now().timestamp()
        wall = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]

        arb_id = getattr(msg, "arbitration_id", 0)
        ext = getattr(msg, "is_extended_id", False)
        id_str = f"{arb_id:08X}" if ext else f"{arb_id:03X}"

        data_hex = " ".join(f"{b:02X}" for b in getattr(msg, "data", []))
        dlc = getattr(msg, "dlc", 0)

        flags = []
        if ext:
            flags.append("EXT")
        if getattr(msg, "is_fd", False):
            flags.append("FD")
        flags_str = " ".join(flags)

        self._tree.insert(
            "", tk.END, values=(wall, id_str, dlc, data_hex, flags_str)
        )

    def _log_append(self, text: str) -> None:
        self._log_area.config(state=tk.NORMAL)
        self._log_area.insert(tk.END, text + "\n")
        self._log_area.see(tk.END)
        self._log_area.config(state=tk.DISABLED)

    def _log_clear(self) -> None:
        self._log_area.config(state=tk.NORMAL)
        self._log_area.delete("1.0", tk.END)
        self._log_area.config(state=tk.DISABLED)


def launch() -> None:
    """Entry point called by main.py --ui flag."""
    app = SelfTestApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
