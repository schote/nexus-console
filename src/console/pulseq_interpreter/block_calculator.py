"""Stateless waveform calculation and block streaming module."""

from dataclasses import dataclass
from math import floor
from types import SimpleNamespace

import numpy as np
from scipy.signal import resample

from console.interfaces.acquisition_parameter import AcquisitionParameter

# Constants
INT16_MAX = np.iinfo(np.int16).max
INT16_MIN = np.iinfo(np.int16).min
NUM_REFERENCE_SAMPLES = 1000
REFERENCE_FREQUENCY = 1.095e6


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


def get_phase_reference(num_samples: int, frequency: float, dwell_time: float) -> np.ndarray:
    """Return phase reference signal."""
    time = np.arange(num_samples) * dwell_time
    signal = np.exp(2j * np.pi * frequency * time)
    phase_reference = np.zeros(num_samples, dtype=np.uint16)
    phase_reference[signal > 0] = np.uint16(2**15)
    return phase_reference


def calculate_rf(
    block: SimpleNamespace,
    larmor_frequency: float,
    b1_scaling: float,
    config: WaveformConfig,
) -> np.ndarray:
    """Calculate RF sample points to be played by TX card."""
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
            "RF magnitude (%s mV) exceeded output limit (%s mV)", np.amax(envelope_scaled), config.rf_out_limit
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
    """Calculate spectrum-card sample points of a pypulseq gradient block event."""
    idx = output_channel - 1
    scaling = fov_scaling / (config.gamma * 1e-3 * config.gpa_gain[idx] * config.grad_eff[idx])

    if block.type == "grad":
        waveform = block.waveform * scaling
        if np.amax(waveform) > config.gradient_out_limits[idx]:
            raise ValueError(
                "Amplitude of channel %s (%s) exceeded output limit (%s)",
                output_channel,
                np.amax(waveform),
                config.gradient_out_limits[idx],
            )
        waveform *= INT16_MAX / config.gradient_out_limits[idx]
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
        flat_amp = block.amplitude * scaling
        if np.amax(flat_amp) > config.gradient_out_limits[idx]:
            raise ValueError(
                "Amplitude of channel %s (%s) exceeded output limit (%s)",
                output_channel,
                np.amax(flat_amp),
                config.gradient_out_limits[idx],
            )
        flat_amp *= INT16_MAX / config.gradient_out_limits[idx]
        rise = np.linspace(0, flat_amp, round(block.rise_time / config.spcm_dwell_time))
        flat = np.full(round(block.flat_time / config.spcm_dwell_time), fill_value=flat_amp)
        fall = np.linspace(flat_amp, 0, round(block.fall_time / config.spcm_dwell_time))
        gradient = np.concatenate((rise, flat, fall))
    else:
        raise ValueError("Block is not a valid gradient block")

    offset_i16 = offset * INT16_MAX / config.gradient_out_limits[idx]
    combined_i16 = gradient + offset_i16

    if np.amax(combined_i16) > INT16_MAX:
        max_strength = np.amax(combined_i16) * config.gradient_out_limits[idx] / INT16_MAX
        raise ValueError(
            f"Amplitude of combined gradient and shim waveforms {max_strength} exceed max gradient amplitude"
        )

    # Shifting gradient waveform to 15 bits
    return gradient.astype(np.int16).view(np.uint16) >> 1


def calculate_block(
    payload: tuple[int, SimpleNamespace],
    parameter: AcquisitionParameter,
    config: WaveformConfig,
) -> np.ndarray:
    """Calculate the waveforms and digital signals of a block, returning an interleaved int16 array."""
    try:
        index, block = payload
        # Create a zero-initialized array for the block: 4 channels of int16
        block_samples = np.round(block.block_duration / config.spcm_dwell_time).astype(int)
        seq_block = np.zeros(block_samples * 4, dtype=np.int16)

        # 1. Analog Signals
        # RF Calculation
        if hasattr(block, "rf") and getattr(block, "rf") is not None:
            rf_waveform = calculate_rf(
                block=block.rf,
                larmor_frequency=parameter.larmor_frequency,
                b1_scaling=parameter.b1_scaling,
                config=config,
            )

            # Delay accounts for start of RF event
            num_samples_delay = round(max(block.rf.dead_time, block.rf.delay) / config.spcm_dwell_time)
            rf_start = num_samples_delay * 4
            rf_end = rf_start + rf_waveform.size * 4

            # Channel 0: RF
            seq_block[rf_start:rf_end:4] = rf_waveform

        # Gradient Calculation
        channel_map = {
            "x": int(parameter.channel_assignment.x),
            "y": int(parameter.channel_assignment.y),
            "z": int(parameter.channel_assignment.z),
        }

        for axis, physical_channel in channel_map.items():
            gradient_axis = f"g{axis}"
            if hasattr(block, gradient_axis) and getattr(block, gradient_axis) is not None:
                gradient = getattr(block, gradient_axis)
                fov_scaling = getattr(parameter.fov_scaling, axis)
                offset_val = parameter.gradient_offset.to_list()[physical_channel - 1]

                waveform = calculate_gradient(
                    block=gradient,
                    fov_scaling=fov_scaling,
                    offset=offset_val,
                    output_channel=physical_channel,
                    config=config,
                )

                delay_samples = round(gradient.delay / config.spcm_dwell_time)
                grad_start = delay_samples * 4 + physical_channel
                grad_end = grad_start + 4 * np.size(waveform)

                # Write to block (bitwise OR to preserve digital bits)
                seq_block[grad_start:grad_end:4] |= waveform.view(np.int16)

        # 2. Digital Signals
        # ADC gate
        if hasattr(block, "adc") and getattr(block, "adc") is not None:
            num_samples_discard = floor(block.adc.dead_time / block.adc.dwell)
            total_gate_duration = (block.adc.num_samples + 2 * num_samples_discard) * block.adc.dwell
            num_samples_raw = round(total_gate_duration / config.spcm_dwell_time)

            remaining_delay = block.adc.delay - num_samples_discard * block.adc.dwell
            num_delay_samples = round(remaining_delay / config.spcm_dwell_time)

            adc_start = num_delay_samples * 4
            adc_end = adc_start + num_samples_raw * 4

            # Add ADC gate to 16th bit of output channel 1 (first gradient channel)
            seq_block[adc_start + 1 : adc_end + 1 : 4] |= np.uint16(2**15).view(np.int16)

            # Add phase reference signal to 16th bit of output channel 2 (second gradient channel)
            phase_reference = get_phase_reference(
                num_samples=min(num_samples_raw, NUM_REFERENCE_SAMPLES),
                frequency=REFERENCE_FREQUENCY,
                dwell_time=config.spcm_dwell_time,
            )
            phase_ref_end = adc_start + phase_reference.size * 4
            seq_block[adc_start + 2 : phase_ref_end + 2 : 4] |= phase_reference[:phase_reference.size].view(np.int16)

        # RF unblanking
        if hasattr(block, "rf") and getattr(block, "rf") is not None:
            num_samples_delay = round(max(block.rf.dead_time, block.rf.delay) / config.spcm_dwell_time)
            num_samples_dead_time = round(block.rf.dead_time / config.spcm_dwell_time)
            num_samples = round(block.rf.shape_dur / config.spcm_dwell_time)

            rf_unblanking_start = num_samples_delay - num_samples_dead_time
            rf_unblanking_end = num_samples_delay + num_samples

            abs_start = rf_unblanking_start * 4
            abs_end = rf_unblanking_end * 4

            # Add RF unblanking to 16th bit of output channel 4 (last gradient channel)
            seq_block[abs_start + 3 : abs_end + 3 : 4] |= np.uint16(2**15).view(np.int16)

        return seq_block

    except Exception as e:
        print(f"Error in worker {index}: {e}")
        raise e
