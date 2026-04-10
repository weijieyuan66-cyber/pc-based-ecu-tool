"""
analysis/report.py
------------------
ReportBuilder — interface definition only.

This abstract base class defines the contract for a future session report
generator.  It is intentionally left unimplemented; the body of each method
raises NotImplementedError.

Future implementations might produce:
  - Plain-text summaries
  - JSON export files
  - PDF / HTML engineering reports

Design constraints
------------------
- Do NOT implement any report rendering here yet.
- Keep the interface minimal.
- AnalysisResult and AnalysisContext are the only coupling points.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from analysis.actions import AnalysisResult
from analysis.context import AnalysisContext


class ReportBuilder(ABC):
    """
    Abstract interface for a future session report generator.
    """

    @property
    @abstractmethod
    def report_format(self) -> str:
        """Human-readable output format name (e.g. "JSON", "PDF", "text")."""

    @abstractmethod
    def build(self, context: AnalysisContext, result: AnalysisResult) -> Dict[str, Any]:
        """
        Build a structured report dictionary from *context* and *result*.

        Parameters
        ----------
        context : AnalysisContext
            The analysis context at the time the report was requested.
        result : AnalysisResult
            The analysis result to include in the report.

        Returns
        -------
        dict
            Serialisable report payload.  The exact schema is defined by
            each concrete implementation.
        """

    @abstractmethod
    def export(self, report: Dict[str, Any], path: str) -> None:
        """
        Persist *report* to the file at *path*.

        Parameters
        ----------
        report : dict
            The report payload produced by build().
        path : str
            Destination file path (including extension).
        """
