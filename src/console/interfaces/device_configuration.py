"""Implementation of the device configuration models."""
from pathlib import Path
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
    """Transmit card (AWG) configuration, section ``TxConfiguration`` of the device configuration file."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    device_path: str = Field(..., strict=True)
    """Device path of the transmit card, e.g. ``/dev/spcm1``."""

    sampling_rate: int = Field(..., strict=True)
    """Sampling rate in MHz. Must equal the receive card sampling rate, which provides the clock."""

    channel_max_amplitude: tuple[TxAmplitudeType, TxAmplitudeType, TxAmplitudeType, TxAmplitudeType] = Field(...)
    """Output range per channel [RF, gradient 1, gradient 2, gradient 3] in mV (1 to 6000 mV, into 50 Ohm)."""

    channel_filter_type: tuple[FilterTypeInt, FilterTypeInt, FilterTypeInt, FilterTypeInt] = Field(...)
    """Output filter setting per channel (0 to 3, see card manual)."""

    rf_terminated_50ohm: bool = Field(..., strict=True)
    """True if the RF output is terminated into 50 Ohm, False for high impedance (output voltage doubles)."""

    gradients_terminated_50ohm: bool = Field(..., strict=True)
    """True if the gradient outputs are terminated into 50 Ohm, False for high impedance (output voltage doubles)."""

    gradient_efficiency: tuple[float, float, float] = Field(...)
    """Gradient coil efficiency in T/m/A per physical gradient channel."""

    gpa_gain: tuple[float, float, float] = Field(...)
    """Gradient power amplifier transconductance in A/V per physical gradient channel."""

    rf_to_mvolt: float = Field(..., strict=True)
    """Conversion factor from PyPulseq RF amplitude (Hz) to output voltage (mV), i.e. mV per Hz."""

    rf_gain_lut_path: Path | None = Field(default=None)
    """Optional path to an RF power amplifier linearisation lookup table (``.npy``, 65536 int16 values)."""


class RxConfiguration(BaseModel):
    """Receive card (digitizer) configuration, section ``RxConfiguration`` of the device configuration file."""

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    device_path: str = Field(..., strict=True)
    """Device path of the receive card, e.g. ``/dev/spcm0``."""

    sampling_rate: int = Field(..., strict=True)
    """Sampling rate in MHz. The receive card is the clock master and provides this clock to the transmit card."""

    max_available_channels: int = Field(..., strict=True)
    """Number of input channels of the card; length of all channel lists (8 for the M2p.5933-x4)."""

    channel_enable: tuple[bool, ...] = Field(...)
    """Enable flag per channel. The number of enabled channels must be 1, 2, 4 or 8."""

    channel_max_amplitude: tuple[RxAmplitudeType, ...] = Field(...)
    """Input range per channel in mV (200, 500, 1000, 2000, 5000 or 10000)."""

    channel_terminated_50ohm: tuple[bool, ...] = Field(...)
    """Input termination per channel, True for 50 Ohm, False for high impedance."""

    num_processing_workers: int = Field(
        default=1,
        ge=0,
        description=(
            "Number of worker processes for parallel RxData processing. "
            "Set to 0 to always process in the main process (no multiprocessing)."
        ),
    )
    """Number of worker processes for parallel processing of the receive data.
    Set to 0 to process in the main process after the acquisition."""

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
    """MR system limits, section ``SystemLimits`` of the device configuration file.

    Translated into a PyPulseq ``Opts`` object by `get_opts`. All values must be given as floats
    (e.g. ``20.e-6``, not ``20e-6``, which YAML parses as string).
    """

    model_config = {"extra": "ignore"}  # Ignore unknown fields instead of raising an error

    max_grad: float = Field(..., strict=True, gt=0)
    """Maximum gradient amplitude in Hz/m."""

    max_slew: float = Field(..., strict=True, gt=0)
    """Maximum gradient slew rate in Hz/m/s."""

    rf_dead_time: float = Field(..., strict=True, ge=0)
    """Dead time before an RF pulse in s; the RF unblanking signal is set this time before the pulse."""

    rf_ringdown_time: float = Field(..., strict=True, ge=0)
    """Ring-down time after an RF pulse in s."""

    adc_dead_time: float = Field(..., strict=True, ge=0)
    """Dead time around an ADC event in s; the ADC gate is extended by this time on both sides."""

    block_duration_raster: float = Field(..., strict=True, gt=0)
    """Raster time of block durations in s."""

    rf_raster_time: float = Field(..., strict=True, ge=0)
    """Raster time of RF waveforms in s."""

    grad_raster_time: float = Field(..., strict=True, gt=0)
    """Raster time of gradient waveforms in s."""

    adc_raster_time: float = Field(..., strict=True, gt=0)
    """Raster time of ADC dwell times in s."""

    B0: float = Field(default=50e-3, strict=True, gt=0)
    """Static magnetic field strength in T."""

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
            B0=self.B0
        )


class NexusConfiguration(BaseModel):
    """Nexus console device configuration, as loaded from the device configuration YAML file."""

    tx: TxConfiguration = Field(..., alias="TxConfiguration")
    """Transmit card configuration (YAML section ``TxConfiguration``)."""

    rx: RxConfiguration = Field(..., alias="RxConfiguration")
    """Receive card configuration (YAML section ``RxConfiguration``)."""

    system: SystemLimits = Field(..., alias="SystemLimits")
    """MR system limits (YAML section ``SystemLimits``)."""
