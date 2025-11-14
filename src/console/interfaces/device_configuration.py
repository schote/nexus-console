"""Implementation of the device configuration models."""
from pydantic import BaseModel, Field, field_validator, model_validator

# Specify the number of gradient channels
NUM_GRADIENTS = 3


class TxConfiguration(BaseModel):
    """Transmit device configuration."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    device_path: str = Field(..., strict=True)
    sampling_rate: int = Field(..., strict=True)
    max_available_channels: int = Field(..., strict=True)
    channel_max_amplitude: list[int] = Field(..., strict=True)
    channel_filter_type: list[int] = Field(..., strict=True)
    channel_terminated_50ohm: list[bool] = Field(..., strict=True)
    gradient_efficiency: list[float] = Field(..., min_length=NUM_GRADIENTS, max_length=NUM_GRADIENTS, strict=True)
    gpa_gain: list[float] = Field(..., min_length=NUM_GRADIENTS, max_length=NUM_GRADIENTS, strict=True)
    rf_to_mvolt: float = Field(..., strict=True)

    @model_validator(mode="after")
    def validate_lists(self) -> "TxConfiguration":
        """Validate the length of device-specific lists."""
        list_fields: dict[str, list[int] | list[bool]] = {
            "channel_max_amplitude": self.channel_max_amplitude,
            "channel_filter_type": self.channel_filter_type,
            "channel_terminated_50ohm": self.channel_terminated_50ohm,
        }
        errors = []
        for name, val in list_fields.items():
            if len(val) < self.max_available_channels:
                _err = f"Field '{name}': \
                    length {len(val)} is less than max_available_channels {self.max_available_channels}"
                errors.append(_err)
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @field_validator("channel_max_amplitude")
    @classmethod
    def validate_max_amplitude(cls, values: list[int]) -> list[int]:
        """Ensure that max. amplitude is within 1 and 6000 mV."""
        if not all(val in range(1, 6001) for val in values):
            msg = "Channel max amplitude must be between 1 and 6000 mV."
            raise ValueError(msg)
        return values

    @field_validator("channel_filter_type")
    @classmethod
    def validate_filter_type(cls, values: list[int]) -> list[int]:
        """Ensure that max. amplitude is within 1 and 6000 mV."""
        if not all(val in range(4) for val in values):
            msg = "Channel filter type must be 0, 1, 2 or 3."
            raise ValueError(msg)
        return values


class RxConfiguration(BaseModel):
    """Receive device configuration."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    device_path: str = Field(..., strict=True)
    sampling_rate: int = Field(..., strict=True)
    max_available_channels: int = Field(..., strict=True)
    channel_enable: list[bool] = Field(..., strict=True)
    channel_max_amplitude: list[int] = Field(..., strict=True)
    channel_terminated_50ohm: list[bool] = Field(..., strict=True)

    @model_validator(mode="after")
    def validate_lists(self) -> "RxConfiguration":
        """Validate the length of device-specific lists."""
        list_fields: dict[str, list[int] | list[bool]] = {
            "channel_max_amplitude": self.channel_max_amplitude,
            "channel_enable": self.channel_enable,
            "channel_terminated_50ohm": self.channel_terminated_50ohm,
        }
        errors = []
        for name, val in list_fields.items():
            if len(val) < self.max_available_channels:
                _err = f"Field '{name}'\
                    length {len(val)} is less than max_available_channels {self.max_available_channels}"
                errors.append(_err)
        if errors:
            raise ValueError("; ".join(errors))
        return self


class SystemLimits(BaseModel):
    """System limit configuration, used as pypulseq sequence system."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    max_grad: float = Field(..., strict=True)
    max_slew: float = Field(..., strict=True)
    rf_dead_time: float = Field(..., strict=True)
    rf_ringdown_time: float = Field(..., strict=True)
    adc_dead_time: float = Field(..., strict=True)
    block_duration_raster: float = Field(..., strict=True)
    rf_raster_time: float = Field(..., strict=True)
    grad_raster_time: float = Field(..., strict=True)
    adc_raster_time: float = Field(..., strict=True)


class NexusConfiguration(BaseModel):
    """Nexus console configuration."""

    tx: TxConfiguration = Field(..., alias="TxConfiguration")
    rx: RxConfiguration = Field(..., alias="RxConfiguration")
    system: SystemLimits = Field(..., alias="SystemLimits")
