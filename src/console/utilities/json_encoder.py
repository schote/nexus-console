"""Implementation of custom JSON encoder."""
import dataclasses
import json
from pathlib import Path


class JSONEncoder(json.JSONEncoder):
    """JSON Encoder class."""

    def default(self, obj: object) -> object:
        """Encode object default method.

        Parameters
        ----------
        obj
            Object to encode

        Returns
        -------
            JSON encoded object
        """
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)
