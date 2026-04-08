"""cc-manager event handler protocol."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Handler:
    """A validated, loaded event handler.

    Replaces the informal module-level convention (EVENT, TIMEOUT_MS, handle)
    with an explicit object that validates at load time rather than at
    dispatch time during a live Claude session.
    """
    event: str
    timeout_ms: int
    fn: Callable[[dict, Any], dict]

    @classmethod
    def from_module(cls, module_path: str) -> "Handler":
        """Import a handler module and validate it has the required attributes.

        Raises AttributeError if EVENT or handle() are missing.
        """
        module = importlib.import_module(module_path)
        event = getattr(module, "EVENT", None)
        if event is None:
            raise AttributeError(
                f"Handler module {module_path!r} is missing the EVENT attribute."
            )
        fn = getattr(module, "handle", None)
        if fn is None or not callable(fn):
            raise AttributeError(
                f"Handler module {module_path!r} is missing a callable handle() function."
            )
        timeout_ms = getattr(module, "TIMEOUT_MS", 5000)
        return cls(event=event, timeout_ms=timeout_ms, fn=fn)
