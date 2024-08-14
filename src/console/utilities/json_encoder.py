"""Implementation of custom JSON encoder."""
import dataclasses
import json
from typing import Any


class JSONEncoder(json.JSONEncoder):
    """JSON Encoder class."""

    def default(self, obj) -> dict[str, Any]:
        """Encode object default method.

        Parameters
        ----------
        o
            Object to encode

        Returns
        -------
            JSON encoded object
        """
        if bool(dataclasses.is_dataclass(obj)) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return super().default(obj)
