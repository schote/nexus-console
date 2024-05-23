"""Implementation of custom JSON encoder."""
import dataclasses
import json


class JSONEncoder(json.JSONEncoder):
    """JSON Encoder class."""

    def default(self, o):
        """Encode object default method.

        Parameters
        ----------
        o
            Object to encode

        Returns
        -------
            JSON encoded object
        """
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)
