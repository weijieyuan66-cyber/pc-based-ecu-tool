"""
analysis/adapter.py
-------------------
LLMProviderAdapter — interface definition only.

This abstract base class defines the contract that any future large-language-
model backend must satisfy.  It is intentionally left unimplemented; the body
of each method raises NotImplementedError to make it obvious that no model
connection exists yet.

Future implementations might include:
  - OpenAIAdapter      (GPT-4o / GPT-4 Turbo via REST API)
  - OllamaAdapter      (local open-weight models via Ollama)
  - AnthropicAdapter   (Claude via Anthropic API)
  - MockAdapter        (deterministic stub for automated testing)

Design constraints
------------------
- Do NOT implement any real model call here yet.
- Keep the interface minimal so implementations stay easy to write.
- AnalysisRequest / AnalysisResult are the only coupling points to the
  rest of the codebase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from analysis.actions import AnalysisRequest, AnalysisResult


class LLMProviderAdapter(ABC):
    """
    Abstract interface for a future AI / LLM analysis backend.

    All concrete adapters must implement the three methods below.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. "OpenAI GPT-4o")."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True when the provider is configured and reachable.

        This allows the UI to show a meaningful status without attempting a
        full analysis.  Should be cheap (e.g. check env-var / ping).
        """

    @abstractmethod
    def analyse(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Execute the analysis described by *request* and return the result.

        Parameters
        ----------
        request : AnalysisRequest
            The analysis request (action + context + source).

        Returns
        -------
        AnalysisResult
            Unified result object.  Must never raise; return a result with
            state=FAILED and a populated error field on any exception.
        """
