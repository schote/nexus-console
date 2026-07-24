"""Implementation of custom JSON encoder."""
import dataclasses
import json
from pathlib import Path


class JSONEncoder(json.JSONEncoder):
    """JSON Encoder class."""

    def default(self, obj) -> object:
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
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)
