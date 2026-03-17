"""Implementation of the device configuration models."""
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator
from pypulseq import Opts

# Ensure that max. amplitude is within 1 and 6000 mV (step size 1 mV).
# Limits depend on card version.
TxAmplitudeType = Annotated[int, Field(ge=1, le=6000)]
# RX amplitude must be one of 200, 500, 1000, 2000, 5000 or 10000 (in mV), depends on card version.
RxAmplitudeType = Literal[200, 500, 1000, 2000, 5000, 10000]
# Ensure valid filter type, channel filter type must be 0, 1, 2 or 3.
# See spectrum instrumentation manual for reference, depends on card version.
FilterTypeInt = Annotated[int, Field(ge=0, le=3)]

class TxConfiguration(BaseModel):
    """Transmit device configuration."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    device_path: str = Field(..., strict=True)
    sampling_rate: int = Field(..., strict=True)
    channel_max_amplitude: tuple[TxAmplitudeType, TxAmplitudeType, TxAmplitudeType, TxAmplitudeType] = Field(...)
    channel_filter_type: tuple[FilterTypeInt, FilterTypeInt, FilterTypeInt, FilterTypeInt] = Field(...)
    rf_terminated_50ohm: bool = Field(..., strict=True)
    gradients_terminated_50ohm: bool = Field(..., strict=True)
    gradient_efficiency: tuple[float, float, float] = Field(...)
    gpa_gain: tuple[float, float, float] = Field(...)
    rf_to_mvolt: float = Field(..., strict=True)


class RxConfiguration(BaseModel):
    """Receive device configuration."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    device_path: str = Field(..., strict=True)
    sampling_rate: int = Field(..., strict=True)
    max_available_channels: int = Field(..., strict=True)
    channel_enable: tuple[bool, ...] = Field(...)
    channel_max_amplitude: tuple[RxAmplitudeType, ...] = Field(...)
    channel_terminated_50ohm: tuple[bool, ...] = Field(...)

    @model_validator(mode="after")
    def validate_channel_lengths(self) -> "RxConfiguration":
        """Validate channel lengths.

        This ensures that `max_available_channels` is length of `channel_enable`,
        `channel_max_amplitude` and  `channel_terminated_50ohm`.
        """
        target_len = self.max_available_channels
        dependent_fields = [
            "channel_enable",
            "channel_max_amplitude",
            "channel_terminated_50ohm",
        ]
        errors = []
        for field_name in dependent_fields:
            current_val = getattr(self, field_name)
            if len(current_val) != target_len:
                errors.append(
                    f"{field_name} length ({len(current_val)}) "
                    f"must be exactly {target_len}"
                )
        if errors:
            # Raising ValueError here is the standard Pydantic way
            raise ValueError(" ; ".join(errors))
        return self


class SystemLimits(BaseModel):
    """System limit configuration, used as pypulseq sequence system."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    max_grad: float = Field(..., strict=True, gt=0)
    max_slew: float = Field(..., strict=True, gt=0)
    rf_dead_time: float = Field(..., strict=True, ge=0)
    rf_ringdown_time: float = Field(..., strict=True, ge=0)
    adc_dead_time: float = Field(..., strict=True, ge=0)
    block_duration_raster: float = Field(..., strict=True, gt=0)
    rf_raster_time: float = Field(..., strict=True, ge=0)
    grad_raster_time: float = Field(..., strict=True, gt=0)
    adc_raster_time: float = Field(..., strict=True, gt=0)
    B0: float = Field(default=50e-3, strict=True, gt=0)

    def get_opts(self) -> Opts:
        """Return system limits of the MR scanner as PyPulseq `Opts` object."""
        return Opts(
            max_grad=self.max_grad,
            max_slew=self.max_slew,
            grad_unit="Hz/m",
            slew_unit="Hz/m/s",
            rf_dead_time=self.rf_dead_time,
            rf_ringdown_time=self.rf_ringdown_time,
            adc_dead_time=self.adc_dead_time,
            block_duration_raster=self.block_duration_raster,
            rf_raster_time=self.rf_raster_time,
            grad_raster_time=self.grad_raster_time,
            adc_raster_time=self.adc_raster_time,
            B0=self.B0,
        )


class NexusConfiguration(BaseModel):
    """Nexus console configuration."""

    tx: TxConfiguration = Field(..., alias="TxConfiguration")
    rx: RxConfiguration = Field(..., alias="RxConfiguration")
    system: SystemLimits = Field(..., alias="SystemLimits")
