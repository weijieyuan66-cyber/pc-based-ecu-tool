"""
backend/factory.py
------------------
BackendFactory: creates the correct CANBackend from a configuration dict.

This is the single call-site for backend construction.  All callers
(main.py, ui/app.py) should use BackendFactory.create(config) rather than
importing concrete backend classes directly.

Supported backend keys (config["backend"])
------------------------------------------
  "virtual"   --> VirtualBackend
  "pcan"      --> PCANBackend
  "vector"    --> VectorBackend

Raises ValueError for unknown backend keys.
"""

from __future__ import annotations

from backend.base import CANBackend


class BackendFactory:
    """Factory that creates a CANBackend from a configuration dict."""

    @staticmethod
    def create(config: dict) -> CANBackend:
        """
        Instantiate and return the backend named in config["backend"].

        Parameters
        ----------
        config : dict
            Application config dict.  Must contain a "backend" key with
            one of: "virtual", "pcan", "vector".

        Returns
        -------
        CANBackend
            A concrete backend instance.  Not yet connected; callers must
            call backend.connect() before sending or receiving.

        Raises
        ------
        ValueError
            If config["backend"] is missing or unrecognised.
        """
        # Lazy imports keep vendor-specific modules out of memory when not used
        name = config.get("backend", "").lower()

        if name == "virtual":
            from backend.virtual import VirtualBackend
            return VirtualBackend(config)

        if name == "pcan":
            from backend.pcan import PCANBackend
            return PCANBackend(config)

        if name == "vector":
            from backend.vector import VectorBackend
            return VectorBackend(config)

        raise ValueError(
            f"Unknown backend '{name}'. "
            "Supported values: 'virtual', 'pcan', 'vector'."
        )

    @staticmethod
    def available_backends() -> list:
        """Return the list of supported backend name strings."""
        return ["virtual", "pcan", "vector"]
