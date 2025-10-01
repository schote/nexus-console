"""Load nexus device configuration from file."""
import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from console.interfaces.device_configuration import NexusConfiguration, SystemLimits

log = logging.getLogger("Config")


def load_nexus_config(path: str | Path) -> NexusConfiguration:
    """Load nexus device configuration."""
    data = yaml.safe_load(Path(path).read_text())
    try:
        return NexusConfiguration.model_validate(data)
    except ValidationError as exc:
        log.exception("Nexus device configuration is invalid.", exc_info=exc)
        raise


def load_system_limits(path: str | Path) -> SystemLimits:
    """Load system limits from device configuration."""
    data = yaml.safe_load(Path(path).read_text())
    try:
        return SystemLimits.model_validate(data["SystemLimits"], strict=True)
    except ValidationError as exc:
        log.exception("System limit configuration is invalid.", exc_info=exc)
        raise
