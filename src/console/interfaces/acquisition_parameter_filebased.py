"""Interface class for acquisition parameters."""

import json
import os
import threading
import pickle  # noqa: S403
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from console.interfaces.dimensions import Dimensions
from console.interfaces.enums import DDCMethod

DEFAULT_STATE_FILE_PATH = os.path.join(Path.home(), "nexus-console", "acquisition-parameter.state")
DEFAULT_FOV_SCALING = Dimensions(x=1., y=1., z=1.)
DEFAULT_GRADIENT_OFFSET = Dimensions(x=0., y=0., z=0.)
FILENAME_STATE = "acquisition-parameter.state"


class ConfigFileError(Exception):
    """Custom exception for configuration file errors."""
    pass


@dataclass
class AcquisitionParameter:
    _filepath: str
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self):
        """Ensure the JSON file exists and contains valid JSON with default values."""
        self._ensure_file()

    def _ensure_file(self):
        """Create the file if it does not exist or is invalid."""
        default_values = {
            "f0": 1.5e6,
            "b1": 0.5,
            "grad_amp": 10.0,
            "averages": 1,
            "delay": 0.01,
        }
        try:
            with open(self._filepath, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        # Ensure all default keys exist
        for key, value in default_values.items():
            data.setdefault(key, value)

        self._save(data)  # Save default config if necessary

    def _load(self) -> dict:
        """Load the latest configuration from the file."""
        with self._lock:
            try:
                with open(self._filepath, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise ConfigFileError(f"Invalid JSON format: {e}")

    def _save(self, data: dict):
        """Save the given data to the file."""
        with self._lock:
            with open(self._filepath, "w") as f:
                json.dump(data, f, indent=4)

    def _get(self, key: str):
        """Generic getter for configuration attributes."""
        return self._load().get(key)

    def _set(self, key: str, value):
        """Generic setter for configuration attributes."""
        data = self._load()
        data[key] = value
        self._save(data)

    # Properties for each configuration parameter
    @property
    def larmor_frequency(self) -> float:
        return self._get("larmor_frequency")

    @larmor_frequency.setter
    def larmor_frequency(self, value: float):
        self._set("larmor_frequency", value)

    @property
    def b1_scaling(self) -> float:
        return self._get("b1_scaling")

    @b1_scaling.setter
    def b1_scaling(self, value: float):
        self._set("b1_scaling", value)

    @property
    def gradient_offset(self) -> Dimensions:
        return Dimensions(self._get("gradient_offset"))

    @gradient_offset.setter
    def gradient_offset(self, value: Dimensions):
        self._set("gradient_offset", value)

    @property
    def fov_scaling(self) -> Dimensions:
        return Dimensions(self._get("fov_scaling"))

    @fov_scaling.setter
    def fov_scaling(self, value: Dimensions):
        self._set("fov_scaling", value)

    @property
    def ddc_method(self) -> float:
        return self._get("decimation")

    @ddc_method.setter
    def ddc_method(self, value: float):
        self._set("decimation", value)

    @property
    def ddc_method(self) -> float:
        return self._get("ddc_method")

    @ddc_method.setter
    def ddc_method(self, value: float):
        self._set("ddc_method", value)

    @property
    def num_averages(self) -> int:
        return self._get("num_averages")

    @num_averages.setter
    def num_averages(self, value: int):
        self._set("num_averages", value)

    @property
    def ddc_method(self) -> float:
        return self._get("averaging_delay")

    @ddc_method.setter
    def ddc_method(self, value: float):
        self._set("averaging_delay", value)

    def to_dict(self) -> dict:
        """Return the full configuration as a dictionary."""
        return self._load()


# # Example Usage
# if __name__ == "__main__":
#     config = Config("config.json")

#     # Get values
#     print(config.f0)  # Output: Default value (1.5e6) if file is empty

#     # Set values (auto-saved to file)
#     config.f0 = 1.4e6
#     config.b1 = 0.6
#     config.grad_amp = 12.5
#     config.averages = 4
#     config.delay = 0.02

#     # Check saved values
#     print(config.to_dict())  # Output: Updated dictionary with new values
