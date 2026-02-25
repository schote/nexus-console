
"""Stateless waveform calculation module."""
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
from scipy.signal import resample

from console.interfaces.acquisition_parameter import AcquisitionParameter

INT16_MAX = np.iinfo(np.int16).max
INT16_MIN = np.iinfo(np.int16).min


@dataclass
class WaveformConfig:
    """Configuration for waveform calculation."""

    spcm_dwell_time: float
    rf_to_mvolt: float
    gpa_gain: tuple[float, float, float]
    grad_eff: tuple[float, float, float]
    gradient_out_limits: tuple[int, int, int]
    rf_out_limit: int
    gamma: float


def calculate_rf(
    block: SimpleNamespace,
    larmor_frequency: float,
    b1_scaling: float,
    config: WaveformConfig,
) -> np.ndarray:
    """Calculate RF sample points to be played by TX card.

    Parameters
    ----------
    block
        Pulseq RF block
    larmor_frequency
        Larmor frequency of RF waveform
    b1_scaling
        Experiment dependent scaling factor of the RF amplitude
    config
        System and hardware configuration

    Returns
    -------
        RF pulse waveform (complex)

    Raises
    ------
    ValueError
        Invalid RF block
    """
    if not block.type == "rf":
        raise ValueError("Sequence block event is not a valid RF event.")
    if not larmor_frequency > 0.0:
        raise ValueError(f"Invalid Larmor frequency: {larmor_frequency}")

    # Calculate the number of RF shape sample points
    num_samples = round(block.shape_dur / config.spcm_dwell_time)

    # RF scaling according to B1 calibration and "device" (translation from pulseq to output voltage)
    envelope_scaled = block.signal * b1_scaling * config.rf_to_mvolt
    if np.abs(np.amax(envelope_scaled)) > config.rf_out_limit:
        raise ValueError(
            "RF magnitude (%s mV) exceeded output limit (%s mV)",
            np.amax(envelope_scaled),
            config.rf_out_limit
        )

    # Apply the static phase offset, defined by RF pulse
    envelope_scaled = envelope_scaled * np.exp(1j * block.phase_offset)
    # Translate to int16
    envelope_scaled *= INT16_MAX / config.rf_out_limit

    # Resampling of scaled complex envelope
    envelope = resample(envelope_scaled, num=num_samples)

    # Calculate carrier
    carrier_time = np.arange(num_samples) * config.spcm_dwell_time
    carrier = np.exp(2j * np.pi * (larmor_frequency + block.freq_offset) * carrier_time)

    return (envelope * carrier).real.astype(np.int16)


def calculate_gradient(
    block: SimpleNamespace,
    fov_scaling: float,
    offset: float,
    output_channel: int,
    config: WaveformConfig,
) -> np.ndarray:
    """Calculate spectrum-card sample points of a pypulseq gradient block event.

    Parameters
    ----------
    block
        Gradient block from pypulseq sequence, type must be grad or trap
    fov_scaling
        Scaling factor to adjust the FoV.
    offset
        Offset value for the gradient channel
    output_channel
        Output channel index (1, 2, or 3)
    config
        System and hardware configuration

    Returns
    -------
        Array with sample points of gradient waveform as int16 values (shifted to uint16)

    Raises
    ------
    ValueError
        Invalid block type, or amplitude exceeds limit
    """
    # Calculate gradient waveform scaling, subtract gain and efficiency index by 1
    # because these lists do not include the RF channel
    idx = output_channel - 1
    # Calculate gradient waveform scaling
    scaling = fov_scaling / (
        config.gamma * 1e-3 * config.gpa_gain[idx] * config.grad_eff[idx]
    )

    if block.type == "grad":
        # Arbitrary gradient waveform
        waveform = block.waveform * scaling
        if np.amax(waveform) > config.gradient_out_limits[idx]:
            raise ValueError(
                "Amplitude of channel %s (%s) exceeded output limit (%s)",
                output_channel,
                np.amax(waveform),
                config.gradient_out_limits[idx]
            )
        # Transfer mV floating point waveform values to int16
        waveform *= INT16_MAX / config.gradient_out_limits[idx]
        # Interpolate waveform on spectrum card time raster
        gradient = np.interp(
            x=np.linspace(
                block.tt[0],
                block.tt[-1],
                round(block.shape_dur / config.spcm_dwell_time),
            ),
            xp=block.tt,
            fp=waveform,
        )
    elif block.type == "trap":
        # Trapezoidal gradient
        flat_amp = block.amplitude * scaling
        if np.amax(flat_amp) > config.gradient_out_limits[idx]:
            raise ValueError(
                "Amplitude of channel %s (%s) exceeded output limit (%s)",
                output_channel,
                np.amax(flat_amp),
                config.gradient_out_limits[idx]
            )
        # Transfer mV floating point waveform values to int16
        flat_amp *= INT16_MAX / config.gradient_out_limits[idx]
        # Interpolate waveform on spectrum card time raster
        rise = np.linspace(0, flat_amp, round(block.rise_time / config.spcm_dwell_time))
        flat = np.full(round(block.flat_time / config.spcm_dwell_time), fill_value=flat_amp)
        fall = np.linspace(flat_amp, 0, round(block.fall_time / config.spcm_dwell_time))
        # Combine rise, flat and fall sections to gradient waveform
        gradient = np.concatenate((rise, flat, fall))
    else:
        raise ValueError("Block is not a valid gradient block")

    # Calculate gradient offset int16 value
    offset_i16 = offset * INT16_MAX / config.gradient_out_limits[idx]
    combined_i16 = gradient + offset_i16

    if np.amax(combined_i16) > INT16_MAX:
        max_strength = (
            np.amax(combined_i16) * config.gradient_out_limits[idx] / INT16_MAX
        )
        raise ValueError(
            f"Amplitude of combined gradient and shim waveforms {max_strength} exceed max gradient amplitude"
        )

    # Shifting gradient waveform to 15 bits
    return gradient.astype(np.int16).view(np.uint16) >> 1


def calculate_block(
    memmap_path: str,
    memmap_shape: tuple,
    memmap_dtype: np.dtype,
    block_idx: int,
    block_pos: int,
    block: SimpleNamespace,
    parameter: AcquisitionParameter,
    config: WaveformConfig,
) -> None:
    """Worker function to calculate waveforms and write to memmap."""
    try:
        # Open memmap
        seq = np.memmap(memmap_path, dtype=memmap_dtype, mode="r+", shape=memmap_shape)
        waveform_start = block_pos * 4

        # RF Calculation
        if hasattr(block, 'rf') and getattr(block, 'rf') is not None:
            rf_waveform = calculate_rf(
                block=block.rf,
                larmor_frequency=parameter.larmor_frequency,
                b1_scaling=parameter.b1_scaling,
                config=config,
            )

            # Calculate the number of delay samples before an RF event (and unblanking)
            # Note that the RF ring-down time is handled implicitly: the block duration used to place the RF waveform
            # already includes the post-pulse dead time, so no additional handling is required.
            # Dead-time is automatically set as delay! Delay accounts for start of RF event
            num_samples_delay = round(max(block.rf.dead_time, block.rf.delay) / config.spcm_dwell_time)

            # Write to memmap
            rf_start = waveform_start + num_samples_delay
            rf_end = rf_start + rf_waveform.size * 4

            # Channel 0: RF
            seq[rf_start:rf_end:4] = rf_waveform

        # Gradient Calculation
        # Map logical axis to physical channel
        # parameter.channel_assignment has fields x, y, z with values 1, 2, 3 (or permuted)
        channel_map = {
            'x': int(parameter.channel_assignment.x),
            'y': int(parameter.channel_assignment.y),
            'z': int(parameter.channel_assignment.z),
        }

        # Iterate over axes
        for axis, physical_channel in channel_map.items():
            # Check if block has this gradient (gx, gy, gz)
            gradient_axis = f"g{axis}"
            if hasattr(block, gradient_axis) and getattr(block, gradient_axis) is not None:
                gradient = getattr(block, gradient_axis)

                # Get scaling and offset
                fov_scaling = getattr(parameter.fov_scaling, axis)

                # Gradient offset is bound to the physical output channel.
                # Channel 1 -> x, Channel 2 -> y, Channel 3 -> z
                # This must not be affected by the channel assignment.
                offset_val = parameter.gradient_offset.to_list()[physical_channel-1]

                waveform = calculate_gradient(
                    block=gradient,
                    fov_scaling=fov_scaling,
                    offset=offset_val,
                    output_channel=physical_channel,
                    config=config,
                )

                delay_samples = round(gradient.delay / config.spcm_dwell_time)
                grad_start = waveform_start + 4 * delay_samples + physical_channel
                grad_end = grad_start + 4 * np.size(waveform)

                # Write to memmap (bitwise OR to preserve digital bits)
                seq[grad_start:grad_end:4] |= waveform

    except Exception as e:
        # Logging in workers is tricky, usually print or re-raise
        print(f"Error in worker {block_idx}: {e}")
        raise e
