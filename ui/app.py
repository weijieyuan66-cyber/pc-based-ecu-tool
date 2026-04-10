"""
ui/app.py
---------
Release 1 — Multi-backend ECU analysis desktop UI.

Layout (top to bottom)
-----------------------
  Backend bar    -- backend selector dropdown + Connect button + status badge
  Action bar     -- Run Self-Test button (virtual only) + status label
  Notebook       -- four tabs:
                    Tab 1 "Raw Frames"      — same treeview as before
                    Tab 2 "Decoded Signals" — J1939 / DBC decoded info
                    Tab 3 "Fault Hints"     — triggered rule alerts
                    Tab 4 "Analysis"        — AI integration reservation
                                              (placeholders only; AI disabled)
  Result badge   -- PASS / FAIL / ERROR (large, colour-coded)
  Log area       -- scrollable read-only log

Design constraints
------------------
- All core logic lives in core/self_test.py, backend/, decode/, rules/.
  This file contains only UI and lightweight glue code.
- Backend switching is driven by the dropdown; no restart required.
- PCAN / Vector connection failure is shown inline (no crash).
- Self-test is available only in virtual mode.
- Decode + rule pipelines run on every received frame regardless of backend.
- Tkinter is stdlib — no extra UI dependency needed.
- The Analysis tab is a UI reservation for future AI integration.
  No AI model connection is implemented.  All analysis buttons are disabled.
"""

import datetime
import os
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
from typing import Optional

from analysis.actions import AnalysisState
from analysis.context import AnalysisContext, SelectedObjectContext
from app_logging.logger import setup_logger
from backend.factory import BackendFactory
from core.self_test import SelfTestResult, run_virtual_self_test
from decode.dbc_decoder import DBCDecoder
from decode.frame_record import DecodedFrame
from decode.j1939_decoder import J1939Decoder
from rules.builtin_rules import create_default_rule_engine
from validation.mock_validation_test import mock_validation_fault_hints, run_mock_validation_test
from main import load_config

DEFAULT_CONFIG_PATH = "config/settings.example.json"

# Severity colours for Fault Hints tab
_SEVERITY_FG = {
    "error":   "#C62828",
    "warning": "#E65100",
    "info":    "#1565C0",
}


class ECUToolApp(tk.Tk):
    """Main application window — Release 1."""

    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        super().__init__()
        self.title("PC-based ECU Tool — Release 1")
        self.resizable(True, True)
        self.minsize(820, 600)

        self._logger = setup_logger("ecu_tool_ui")
        try:
            self._config = load_config(config_path)
        except FileNotFoundError as exc:
            self._config = {"backend": "virtual", "backends": {"virtual": {"channel": "test_channel"}}}
            self._logger.warning("Config not found: %s — using defaults.", exc)

        # ── decode / rules pipeline ──────────────────────────────────────
        self._dbc_decoder = DBCDecoder()
        self._j1939_decoder = J1939Decoder()
        self._rule_engine = create_default_rule_engine()

        # ── backend state ────────────────────────────────────────────────
        self._backend = None
        self._running = False

        # ── analysis reservation state ───────────────────────────────────
        # These counters are updated on every processed frame so that the
        # Analysis tab always shows an up-to-date context snapshot.
        self._analysis_state = AnalysisState.DISABLED
        self._analysis_frame_count = 0
        self._analysis_decoded_count = 0
        self._analysis_fault_count = 0

        self._build_ui()
        self._sync_backend_ui()
        self._update_analysis_tab()

    # ================================================================== #
    # UI construction                                                       #
    # ================================================================== #

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # ── Backend selector bar ─────────────────────────────────────────
        backend_frame = tk.Frame(self, bd=1, relief=tk.RIDGE)
        backend_frame.pack(fill=tk.X, **pad)

        tk.Label(backend_frame, text="Backend:", font=("TkDefaultFont", 10)).pack(
            side=tk.LEFT, padx=(6, 4), pady=4
        )

        self._backend_var = tk.StringVar(value=self._config.get("backend", "virtual"))
        backend_cb = ttk.Combobox(
            backend_frame,
            textvariable=self._backend_var,
            values=BackendFactory.available_backends(),
            state="readonly",
            width=10,
        )
        backend_cb.pack(side=tk.LEFT, padx=(0, 8), pady=4)
        backend_cb.bind("<<ComboboxSelected>>", lambda _e: self._sync_backend_ui())

        self._btn_connect = tk.Button(
            backend_frame,
            text="Connect",
            font=("TkDefaultFont", 10),
            command=self._on_connect,
            width=10,
        )
        self._btn_connect.pack(side=tk.LEFT, padx=(0, 8), pady=4)

        self._btn_disconnect = tk.Button(
            backend_frame,
            text="Disconnect",
            font=("TkDefaultFont", 10),
            command=self._on_disconnect,
            state=tk.DISABLED,
            width=10,
        )
        self._btn_disconnect.pack(side=tk.LEFT, padx=(0, 12), pady=4)

        self._lbl_conn_status = tk.Label(
            backend_frame,
            text="● Not connected",
            anchor="w",
            font=("Courier", 9),
        )
        self._lbl_conn_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # ── DBC file loader ──────────────────────────────────────────────
        dbc_frame = tk.Frame(self, bd=1, relief=tk.RIDGE)
        dbc_frame.pack(fill=tk.X, **pad)

        tk.Label(dbc_frame, text="DBC file:", font=("TkDefaultFont", 10)).pack(
            side=tk.LEFT, padx=(6, 4), pady=4
        )
        self._lbl_dbc = tk.Label(
            dbc_frame,
            text="(none loaded — J1939 ID decode only)",
            anchor="w",
            font=("Courier", 9),
            fg="#555",
        )
        self._lbl_dbc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)

        tk.Button(
            dbc_frame,
            text="Load DBC …",
            command=self._on_load_dbc,
        ).pack(side=tk.RIGHT, padx=6, pady=4)

        # ── Action bar ───────────────────────────────────────────────────
        action_frame = tk.Frame(self)
        action_frame.pack(fill=tk.X, **pad)

        self._btn_run = tk.Button(
            action_frame,
            text="▶  Run Self-Test",
            font=("TkDefaultFont", 11, "bold"),
            bg="#4CAF50",
            fg="white",
            activebackground="#388E3C",
            activeforeground="white",
            command=self._on_run_self_test,
        )
        self._btn_run.pack(side=tk.LEFT, padx=(0, 8), ipadx=10, ipady=4)

        self._btn_validate = tk.Button(
            action_frame,
            text="✔  Validate (Mock)",
            font=("TkDefaultFont", 11, "bold"),
            bg="#1565C0",
            fg="white",
            activebackground="#0D47A1",
            activeforeground="white",
            command=self._on_run_validation_test,
        )
        self._btn_validate.pack(side=tk.LEFT, padx=(0, 12), ipadx=10, ipady=4)

        self._lbl_status = tk.Label(action_frame, text="Ready", anchor="w")
        self._lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Notebook tabs ────────────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self._tab_raw = tk.Frame(nb)
        self._tab_decoded = tk.Frame(nb)
        self._tab_faults = tk.Frame(nb)
        self._tab_analysis = tk.Frame(nb)
        nb.add(self._tab_raw, text="Raw Frames")
        nb.add(self._tab_decoded, text="Decoded Signals")
        nb.add(self._tab_faults, text="Fault Hints")
        nb.add(self._tab_analysis, text="Analysis")

        self._build_raw_tab()
        self._build_decoded_tab()
        self._build_faults_tab()
        self._build_analysis_tab()

        # ── PASS / FAIL badge ────────────────────────────────────────────
        self._lbl_result = tk.Label(
            self,
            text="--",
            font=("TkDefaultFont", 16, "bold"),
            width=24,
        )
        self._lbl_result.pack(pady=(0, 4))

        # ── Log area ─────────────────────────────────────────────────────
        tk.Label(self, text="Log", anchor="w").pack(fill=tk.X, padx=8)
        self._log_area = scrolledtext.ScrolledText(
            self,
            height=6,
            state=tk.DISABLED,
            font=("Courier", 9),
        )
        self._log_area.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))

    def _build_raw_tab(self) -> None:
        columns = ("timestamp", "can_id", "dlc", "data", "flags")
        self._tree_raw = ttk.Treeview(
            self._tab_raw, columns=columns, show="headings", height=10
        )
        col_cfg = [
            ("timestamp", "Timestamp",   160, tk.W),
            ("can_id",    "CAN ID",        90, tk.CENTER),
            ("dlc",       "DLC",           40, tk.CENTER),
            ("data",      "Data (hex)",   300, tk.W),
            ("flags",     "Flags",         60, tk.CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self._tree_raw.heading(cid, text=heading)
            self._tree_raw.column(cid, width=width, anchor=anchor, stretch=True)

        vsb = ttk.Scrollbar(self._tab_raw, orient=tk.VERTICAL, command=self._tree_raw.yview)
        self._tree_raw.configure(yscrollcommand=vsb.set)
        self._tree_raw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_decoded_tab(self) -> None:
        columns = ("timestamp", "can_id", "pgn", "pgn_name", "signal", "value", "unit", "source")
        self._tree_decoded = ttk.Treeview(
            self._tab_decoded, columns=columns, show="headings", height=10
        )
        col_cfg = [
            ("timestamp", "Timestamp",    140, tk.W),
            ("can_id",    "CAN ID",         80, tk.CENTER),
            ("pgn",       "PGN",            60, tk.CENTER),
            ("pgn_name",  "PGN / Name",    220, tk.W),
            ("signal",    "Signal",        130, tk.W),
            ("value",     "Value",          70, tk.CENTER),
            ("unit",      "Unit",           50, tk.CENTER),
            ("source",    "Source",         60, tk.CENTER),
        ]
        for cid, heading, width, anchor in col_cfg:
            self._tree_decoded.heading(cid, text=heading)
            self._tree_decoded.column(cid, width=width, anchor=anchor, stretch=True)

        vsb = ttk.Scrollbar(self._tab_decoded, orient=tk.VERTICAL, command=self._tree_decoded.yview)
        self._tree_decoded.configure(yscrollcommand=vsb.set)
        self._tree_decoded.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_faults_tab(self) -> None:
        columns = ("severity", "rule_id", "frame_id", "signal", "message")
        self._tree_faults = ttk.Treeview(
            self._tab_faults, columns=columns, show="headings", height=10
        )
        col_cfg = [
            ("severity", "Severity",   70, tk.CENTER),
            ("rule_id",  "Rule",       180, tk.W),
            ("frame_id", "Frame ID",    80, tk.CENTER),
            ("signal",   "Signal",      100, tk.W),
            ("message",  "Message",    400, tk.W),
        ]
        for cid, heading, width, anchor in col_cfg:
            self._tree_faults.heading(cid, text=heading)
            self._tree_faults.column(cid, width=width, anchor=anchor, stretch=True)

        vsb = ttk.Scrollbar(self._tab_faults, orient=tk.VERTICAL, command=self._tree_faults.yview)
        self._tree_faults.configure(yscrollcommand=vsb.set)
        self._tree_faults.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_analysis_tab(self) -> None:
        """
        Build the Analysis tab — AI integration reservation (placeholders only).

        All interactive elements are disabled.  No AI model is connected.
        This tab is intentionally minimal; a full chat / report panel will be
        added in a future release once AI integration is implemented.
        """
        pad = {"padx": 10, "pady": 4}

        # ── AI status row ────────────────────────────────────────────────
        status_row = tk.Frame(self._tab_analysis, bd=1, relief=tk.GROOVE)
        status_row.pack(fill=tk.X, **pad)

        tk.Label(
            status_row,
            text="AI Status:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 4), pady=6)

        self._lbl_ai_status = tk.Label(
            status_row,
            text="⬤  AI disabled — placeholder only",
            font=("Courier", 9),
            fg="#888",
            anchor="w",
        )
        self._lbl_ai_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6)

        # ── Analysis context status row ──────────────────────────────────
        ctx_row = tk.Frame(self._tab_analysis, bd=1, relief=tk.GROOVE)
        ctx_row.pack(fill=tk.X, **pad)

        tk.Label(
            ctx_row,
            text="Context:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 4), pady=6)

        self._lbl_analysis_ctx = tk.Label(
            ctx_row,
            text="frames: 0   decoded: 0   faults: 0",
            font=("Courier", 9),
            anchor="w",
            fg="#555",
        )
        self._lbl_analysis_ctx.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6)

        # ── Selected object info row ─────────────────────────────────────
        sel_row = tk.Frame(self._tab_analysis, bd=1, relief=tk.GROOVE)
        sel_row.pack(fill=tk.X, **pad)

        tk.Label(
            sel_row,
            text="Selected:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(8, 4), pady=6)

        self._lbl_selected_obj = tk.Label(
            sel_row,
            text="(nothing selected)",
            font=("Courier", 9),
            anchor="w",
            fg="#555",
        )
        self._lbl_selected_obj.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6)

        # ── Disabled action buttons ──────────────────────────────────────
        btn_row = tk.Frame(self._tab_analysis)
        btn_row.pack(fill=tk.X, **pad)

        for label in (
            "Analyze Current Session",
            "Explain Selected Fault",
            "Generate Report",
        ):
            tk.Button(
                btn_row,
                text=label,
                state=tk.DISABLED,
                font=("TkDefaultFont", 10),
                width=24,
            ).pack(side=tk.LEFT, padx=(0, 8), pady=4)

        tk.Label(
            btn_row,
            text="(buttons enabled when AI is configured)",
            font=("TkDefaultFont", 8),
            fg="#999",
        ).pack(side=tk.LEFT, padx=4)

        # ── Analysis output area ─────────────────────────────────────────
        tk.Label(
            self._tab_analysis,
            text="Analysis Output",
            anchor="w",
            font=("TkDefaultFont", 9, "bold"),
        ).pack(fill=tk.X, padx=10, pady=(8, 0))

        self._analysis_output = scrolledtext.ScrolledText(
            self._tab_analysis,
            height=10,
            state=tk.DISABLED,
            font=("Courier", 9),
            bg="#F5F5F5",
            fg="#555",
        )
        self._analysis_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))
        self._set_analysis_output(
            "Analysis output will appear here.\n\n"
            "AI integration is not yet implemented.\n"
            "This panel is reserved for a future release."
        )

    def _set_analysis_output(self, text: str) -> None:
        """Replace the contents of the analysis output area."""
        self._analysis_output.config(state=tk.NORMAL)
        self._analysis_output.delete("1.0", tk.END)
        self._analysis_output.insert(tk.END, text)
        self._analysis_output.config(state=tk.DISABLED)

    def _update_analysis_tab(self) -> None:
        """Refresh the dynamic labels in the Analysis tab from current state."""
        ctx_text = (
            f"frames: {self._analysis_frame_count}   "
            f"decoded: {self._analysis_decoded_count}   "
            f"faults: {self._analysis_fault_count}"
        )
        self._lbl_analysis_ctx.config(text=ctx_text)

    # ================================================================== #
    # Backend connection                                                    #
    # ================================================================== #

    def _sync_backend_ui(self) -> None:
        """Update action bar state based on the selected backend."""
        selected = self._backend_var.get()
        if selected == "virtual":
            self._btn_run.config(state=tk.NORMAL)
        else:
            self._btn_run.config(state=tk.DISABLED)

    def _on_connect(self) -> None:
        if self._running:
            return
        # Disconnect previous backend if any
        if self._backend is not None:
            self._backend.disconnect()
            self._backend = None

        selected = self._backend_var.get()
        # Temporarily update config to use selected backend
        self._config["backend"] = selected
        try:
            self._backend = BackendFactory.create(self._config)
        except ValueError as exc:
            self._log_append(f"[ERROR] {exc}")
            return

        self._log_append(f"Connecting to '{selected}' backend ...")
        self._btn_connect.config(state=tk.DISABLED)

        threading.Thread(
            target=self._connect_thread,
            daemon=True,
            name="ui-connect",
        ).start()

    def _connect_thread(self) -> None:
        ok = self._backend.connect()
        self.after(0, self._on_connect_done, ok)

    def _on_connect_done(self, ok: bool) -> None:
        self._btn_connect.config(state=tk.NORMAL)
        if ok:
            name = self._backend.backend_name
            self._lbl_conn_status.config(
                text=f"● Connected  [{name}]", fg="#2E7D32"
            )
            self._btn_disconnect.config(state=tk.NORMAL)
            self._log_append(f"Connected to '{name}' backend.")
            self._sync_backend_ui()
        else:
            err = self._backend.connection_error or "Unknown error"
            self._lbl_conn_status.config(
                text=f"● Hardware not available", fg="#C62828"
            )
            self._log_append(
                f"[WARNING] Could not connect to '{self._backend.backend_name}': {err}"
            )
            self._log_append(
                "  → Ensure the driver / hardware is installed and connected."
            )

    def _on_disconnect(self) -> None:
        if self._backend is not None:
            self._backend.disconnect()
            self._backend = None
        self._lbl_conn_status.config(text="● Not connected", fg="black")
        self._btn_disconnect.config(state=tk.DISABLED)
        self._log_append("Disconnected.")
        self._sync_backend_ui()

    # ================================================================== #
    # DBC loader                                                            #
    # ================================================================== #

    def _on_load_dbc(self) -> None:
        path = filedialog.askopenfilename(
            title="Select DBC file",
            filetypes=[("DBC files", "*.dbc"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._dbc_decoder.load(path)
            self._lbl_dbc.config(text=os.path.basename(path), fg="#2E7D32")
            self._log_append(f"DBC loaded: {path}")
        except (ImportError, ValueError, FileNotFoundError) as exc:
            self._log_append(f"[ERROR] DBC load failed: {exc}")

    # ================================================================== #
    # Self-test                                                             #
    # ================================================================== #

    def _on_run_self_test(self) -> None:
        if self._running:
            return
        self._running = True
        self._btn_run.config(state=tk.DISABLED)
        self._lbl_status.config(text="Running ...")
        self._lbl_result.config(text="--", fg="black")

        for tree in (self._tree_raw, self._tree_decoded, self._tree_faults):
            for row in tree.get_children():
                tree.delete(row)

        # Reset analysis context counters for the new run
        self._analysis_frame_count = 0
        self._analysis_decoded_count = 0
        self._analysis_fault_count = 0
        self._update_analysis_tab()

        self._log_clear()
        self._log_append("Starting virtual self-test ...")

        threading.Thread(
            target=self._self_test_thread,
            daemon=True,
            name="ui-self-test",
        ).start()

    def _self_test_thread(self) -> None:
        try:
            result = run_virtual_self_test(self._config, self._logger)
        except Exception as exc:
            self.after(0, self._on_test_error, str(exc))
            return
        self.after(0, self._on_self_test_done, result)

    def _on_self_test_done(self, result: SelfTestResult) -> None:
        for msg in result.received_frames:
            self._process_frame(msg)

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
            f"Done — {len(result.received_frames)}/{result.sent_count} "
            "frame(s) received"
        )
        self._lbl_status.config(text=summary)
        self._btn_run.config(state=tk.NORMAL)
        self._running = False

    def _on_test_error(self, message: str) -> None:
        self._log_append(f"ERROR: {message}")
        self._lbl_result.config(text="ERROR", fg="#C62828")
        self._lbl_status.config(text="Error — see log")
        self._btn_run.config(state=tk.NORMAL)
        self._running = False

    # ================================================================== #
    # Mock validation test                                                  #
    # ================================================================== #

    def _on_run_validation_test(self) -> None:
        """Trigger the mock validation test and display results."""
        if self._running:
            return
        self._running = True
        self._btn_validate.config(state=tk.DISABLED)
        self._lbl_status.config(text="Running validation test ...")
        self._lbl_result.config(text="--", fg="black")

        # Clear only the Fault Hints tab for a fresh view of deviations.
        for row in self._tree_faults.get_children():
            self._tree_faults.delete(row)

        self._log_clear()
        self._log_append("Starting mock validation test ...")

        threading.Thread(
            target=self._validation_test_thread,
            daemon=True,
            name="ui-validation-test",
        ).start()

    def _validation_test_thread(self) -> None:
        try:
            summary = run_mock_validation_test()
        except Exception as exc:
            self.after(0, self._on_validation_error, str(exc))
            return
        self.after(0, self._on_validation_done, summary)

    def _on_validation_done(self, summary) -> None:
        from validation.validator import ExpectationValidator
        hints = ExpectationValidator.to_fault_hints(summary.deviations)

        self._log_append(
            f"Validation scenario : '{summary.scenario_name}'"
        )
        self._log_append(
            f"Total deviations    : {summary.total_deviations}"
        )
        for dtype, count in summary.by_type.items():
            self._log_append(f"  {dtype}: {count}")

        for hint in hints:
            self._add_fault_row(hint)
            self._logger.warning(
                "[Validation] [%s] %s — %s",
                hint.severity.upper(), hint.rule_id, hint.message,
            )

        if summary.passed:
            self._lbl_result.config(text="PASS", fg="#2E7D32")
            self._log_append("Result: PASS — no deviations detected.")
        else:
            self._lbl_result.config(
                text=f"DEVIATIONS  ({summary.total_deviations})",
                fg="#C62828",
            )
            self._log_append(
                f"Result: FAIL — {summary.total_deviations} deviation(s) found."
            )

        self._lbl_status.config(
            text=f"Validation done — {summary.total_deviations} deviation(s)"
        )

        # Update analysis context counters
        self._analysis_fault_count += len(hints)
        self._update_analysis_tab()

        self._btn_validate.config(state=tk.NORMAL)
        self._running = False

    def _on_validation_error(self, message: str) -> None:
        self._log_append(f"ERROR: {message}")
        self._lbl_result.config(text="ERROR", fg="#C62828")
        self._lbl_status.config(text="Validation error — see log")
        self._btn_validate.config(state=tk.NORMAL)
        self._running = False

    # ================================================================== #
    # Frame processing pipeline (decode + rules)                           #
    # ================================================================== #

    def _process_frame(self, msg) -> None:
        """Run raw frame through decode + rules pipeline and update all tabs."""
        frame = DecodedFrame(raw=msg)

        # DBC decode (if loaded)
        self._dbc_decoder.decode(frame)
        # J1939 ID decode (always available for extended IDs)
        self._j1939_decoder.decode(frame)
        # Fault rules
        hints = self._rule_engine.evaluate(frame)

        self._add_raw_row(frame)
        self._add_decoded_rows(frame)
        for hint in hints:
            self._add_fault_row(hint)

        # Keep analysis context counters up to date
        self._analysis_frame_count += 1
        if frame.signals or frame.pgn is not None:
            self._analysis_decoded_count += 1
        self._analysis_fault_count += len(hints)
        self._update_analysis_tab()

    # ================================================================== #
    # Tab row builders                                                      #
    # ================================================================== #

    def _add_raw_row(self, frame: DecodedFrame) -> None:
        msg = frame.raw
        ts = msg.timestamp if msg.timestamp is not None else datetime.datetime.now().timestamp()
        wall = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
        id_str = f"{msg.arbitration_id:08X}" if msg.is_extended_id else f"{msg.arbitration_id:03X}"
        data_hex = " ".join(f"{b:02X}" for b in msg.data)
        flags = []
        if msg.is_extended_id:
            flags.append("EXT")
        if getattr(msg, "is_fd", False):
            flags.append("FD")
        if msg.is_error_frame:
            flags.append("ERR")
        self._tree_raw.insert(
            "", tk.END,
            values=(wall, id_str, msg.dlc, data_hex, " ".join(flags)),
        )

    def _add_decoded_rows(self, frame: DecodedFrame) -> None:
        msg = frame.raw
        ts = msg.timestamp if msg.timestamp is not None else datetime.datetime.now().timestamp()
        wall = datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
        id_str = f"{msg.arbitration_id:08X}" if msg.is_extended_id else f"{msg.arbitration_id:03X}"
        pgn_str = f"0x{frame.pgn:04X}" if frame.pgn is not None else ""
        pgn_name = frame.pgn_name or ""

        if frame.signals:
            for sig in frame.signals:
                self._tree_decoded.insert(
                    "", tk.END,
                    values=(wall, id_str, pgn_str, pgn_name,
                            sig.name, sig.value, sig.unit, frame.decode_source),
                )
        elif frame.pgn is not None:
            # J1939 ID identified but no SPN signals decoded (no DBC)
            self._tree_decoded.insert(
                "", tk.END,
                values=(wall, id_str, pgn_str, pgn_name,
                        "(no signals)", "", "", frame.decode_source),
            )

    def _add_fault_row(self, hint) -> None:
        frame_id_str = ""
        if hint.frame_id is not None:
            frame_id_str = f"0x{hint.frame_id:03X}"
        tag = hint.severity
        self._tree_faults.insert(
            "", tk.END,
            values=(
                hint.severity.upper(),
                hint.rule_id,
                frame_id_str,
                hint.signal_name or "",
                hint.message,
            ),
            tags=(tag,),
        )
        fg = _SEVERITY_FG.get(hint.severity, "black")
        self._tree_faults.tag_configure(tag, foreground=fg)

    # ================================================================== #
    # Log helpers                                                           #
    # ================================================================== #

    def _log_append(self, text: str) -> None:
        self._log_area.config(state=tk.NORMAL)
        self._log_area.insert(tk.END, text + "\n")
        self._log_area.see(tk.END)
        self._log_area.config(state=tk.DISABLED)

    def _log_clear(self) -> None:
        self._log_area.config(state=tk.NORMAL)
        self._log_area.delete("1.0", tk.END)
        self._log_area.config(state=tk.DISABLED)


def launch(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """Entry point called by main.py --ui flag."""
    app = ECUToolApp(config_path=config_path)
    app.mainloop()


if __name__ == "__main__":
    launch()
