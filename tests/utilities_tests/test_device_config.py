"""Tests for loading nexus device configuration."""
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from pypulseq import Opts

from console.interfaces.device_configuration import NexusConfiguration, RxConfiguration, SystemLimits, TxConfiguration
from console.utilities.load_configuration import load_nexus_config, load_system_limits


def test_nexus_configuration() -> None:
    """Load nexus device configuration test."""
    config_file = Path("examples/example_device_config.yaml")
    config: NexusConfiguration = load_nexus_config(config_file)

    assert isinstance(config.rx, RxConfiguration)
    assert isinstance(config.tx, TxConfiguration)
    assert isinstance(config.system, SystemLimits)

    opts = Opts(**config.system.model_dump())
    assert isinstance(opts, Opts)

    sys_limits: SystemLimits = load_system_limits(config_file)
    assert sys_limits == config.system


def test_nexus_configuration_sampling_rate_mismatch() -> None:
    """Different transmit and receive sampling rates are not supported yet and must be rejected."""
    data = yaml.safe_load(Path("examples/example_device_config.yaml").read_text())
    data["TxConfiguration"]["sampling_rate"] = data["RxConfiguration"]["sampling_rate"] // 2

    with pytest.raises(ValidationError, match="sampling rate"):
        NexusConfiguration.model_validate(data)
