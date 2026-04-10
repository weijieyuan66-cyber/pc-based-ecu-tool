"""
analysis/__init__.py
--------------------
AI-integration preparation layer — Release 1 code-layer reservation.

This package defines the data structures and interfaces that will be used
when AI analysis (LLM / rule-based reporting) is added in a future release.
Nothing here is connected to an actual AI model yet.

Modules
-------
context  -- AnalysisContext, SessionSummary, FaultHintSummary,
             SelectedObjectContext
actions  -- AnalysisAction, AnalysisState, AnalysisRequest, AnalysisResult
adapter  -- LLMProviderAdapter (interface only, no implementation)
report   -- ReportBuilder (interface only, no implementation)
"""

from analysis.actions import (
    AnalysisAction,
    AnalysisRequest,
    AnalysisResult,
    AnalysisState,
)
from analysis.adapter import LLMProviderAdapter
from analysis.context import (
    AnalysisContext,
    FaultHintSummary,
    SelectedObjectContext,
    SessionSummary,
)
from analysis.report import ReportBuilder

__all__ = [
    "AnalysisAction",
    "AnalysisContext",
    "AnalysisRequest",
    "AnalysisResult",
    "AnalysisState",
    "FaultHintSummary",
    "LLMProviderAdapter",
    "ReportBuilder",
    "SelectedObjectContext",
    "SessionSummary",
]
