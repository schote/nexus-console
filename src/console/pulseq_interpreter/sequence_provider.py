"""Sequence provider class."""
import logging
import operator
from collections.abc import Callable
from dataclasses import dataclass
from math import floor
from types import SimpleNamespace
from typing import Any

import numpy as np
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import SystemLimits
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence

try:
    from line_profiler import profile
except ImportError:
    def profile(func: Callable[..., Any]) -> Callable[..., Any]:
        """Define placeholder for profile decorator."""
        return func


INT16_MAX = np.iinfo(np.int16).max
INT16_MIN = np.iinfo(np.int16).min

NUM_REFERENCE_SAMPLES = 1000
REFERENCE_FREQUENCY = 1.095e6


@dataclass
class ADCGate:
    """Define precalculated attributes of an ADC gate."""

    start: int
    num_samples_discard: int
    num_samples_raw: int

class SequenceProvider(Sequence):
    """Sequence provider class.

    This object is inherited from pulseq sequence object, so that all methods of the
    pypulseq ``Sequence`` object can be accessed.

    The main functionality of the ``SequenceProvider`` is to unroll a given pulseq sequence.
    Usually the first step is to read a sequence file. The unrolling step can be achieved using
    the ``unroll_sequence()`` function.

    Example
    -------
    >>> seq_provider = SequenceProvider()
    >>> seq_provider.read("./seq_file.seq")
    >>> unrolled = seq_provider.unroll_sequence(acquisition_parameter)
    """

    __name__: str = "SequenceProvider"

    def __init__(
        self,
        gradient_efficiency: tuple[float, float, float],
        gpa_gain: tuple[float, float, float],
        gradient_output_limits: tuple[int, int, int],
        gradients_50ohms: bool,
        rf_output_limit: int,
        rf_50ohms: bool,
        rf_to_mvolt: float,
        spcm_dwell_time: float,
        system_limits: SystemLimits,
    ):
        """Initialize sequence provider class which is used to unroll a pulseq sequence.

        Parameters
        ----------
        gradient_efficiency
            Efficiency of the gradient coils in mT/m/A, e.g. [0.4e-3, 0.4e-3, 0.4e-3].
        gpa_gain
            Gain factor of the GPA per gradient channel, e.g. [4.7, 4.7, 4.7].
        gradient_output_limits
            Integer output limit per gradient channel in mV, e.g. [6000, 6000, 6000].
        gradients_50ohms
            Boolean flag which indicates if the gradient output is terminated into 50 ohms or high impedance.
            If terminated into high impedance, the card output doubles,
            what needs to be considered when calculating the sequence.
        rf_output_limit
            Integer output limit of the RF channel in mV.
        rf_50ohms
            Boolean flag which indicates if the rf output is terminated into 50 ohms (see gradients_50ohms).
        rf_to_mvolt, optional
            Translation of RF waveform from pulseq (Hz) to mV.
        spcm_dwell_time, optional
            Sampling time raster of the output waveform (depends on spectrum card).
        system_limits
            Absolute maximum system limits defined in the device configuration.
            Used to instantiate the pypulseq `Opts()` class.
        """
        super().__init__(
            system=Opts(
                **system_limits.model_dump(),
                B0=50e-3,
                grad_unit="Hz/m",   # system limit is defined in this units
                slew_unit="Hz/m/s",  # system limit is defined in this units
            ),
        )
        self.log = logging.getLogger("SeqProv")

        # Set class instance attributes
        self.rf_to_mvolt = rf_to_mvolt
        self.spcm_dwell_time = spcm_dwell_time
        self.spcm_freq = 1 / spcm_dwell_time
        self.system_limits = system_limits
        self.gpa_gain = gpa_gain
        self.grad_eff = gradient_efficiency

        # Scale output limit dependent on high impedance flags:
        # If output is terminated into high impedance (flag is true), the channel output is doubled.
        # Otherwise, if output is terminated into 50 ohms impedance, output limit remains unchanged.
        self.rf_out_limit = rf_output_limit if rf_50ohms else int(2 * rf_output_limit)
        # Ensure tuple[int, int, int] for mypy typing
        self.gradient_out_limits = (
            gradient_output_limits[0] if gradients_50ohms else int(2 * gradient_output_limits[0]),
            gradient_output_limits[1] if gradients_50ohms else int(2 * gradient_output_limits[1]),
            gradient_output_limits[2] if gradients_50ohms else int(2 * gradient_output_limits[2]),
        )

        # Setup phase reference signal
        time = np.arange(NUM_REFERENCE_SAMPLES) * self.spcm_dwell_time
        signal = np.exp(2j * np.pi * REFERENCE_FREQUENCY * time)
        self.phase_reference = np.zeros(NUM_REFERENCE_SAMPLES, dtype=np.uint16)
        self.phase_reference[signal > 0] = np.uint16(2**15)

    # -------- PyPulseq interface -------- #

    def from_pypulseq(self, seq: Sequence) -> None:
        """Cast a pypulseq ``Sequence`` instance to this ``SequenceProvider``.

        If argument is a valid ``Sequence`` instance, all the attributes of
        ``Sequence`` are set in this ``SequenceProvider`` (inherits from ``Sequence``).

        Parameters
        ----------
        seq
            Pypulseq ``Sequence`` instance

        Raises
        ------
        ValueError
            seq is not a valid pypulseq ``Sequence`` instance
        AttributeError
            Key of Sequence instance not
        """
        try:
            # List of (attribute, comparison function, message operator symbol) to check system limits
            limits = [
                ("max_grad", operator.gt, "<="),
                ("max_slew", operator.gt, "<="),
                ("grad_raster_time", operator.lt, ">="),
                ("adc_raster_time", operator.lt, ">="),
                ("rf_raster_time", operator.lt, ">="),
                ("block_duration_raster", operator.lt, ">="),
                ("adc_dead_time", operator.lt, ">="),
                ("rf_dead_time", operator.lt, ">="),
                ("rf_ringdown_time", operator.lt, ">="),
            ]
            errors = []
            for attr, compare, symbol in limits:
                limit_val = getattr(self.system_limits, attr)
                # Compare can be done without converting gradient/slew-rate values
                # -> internally stored in Hz/m and Hz/m/s
                if compare(system_value := getattr(seq.system, attr), limit_val):
                    errors.append(f"{attr} out of bounds (limit {symbol} {limit_val}) (system value: {system_value})")
            if errors:
                raise ValueError("; ".join(errors))

            if not isinstance(seq, Sequence):
                raise ValueError("Provided object is not an instance of pypulseq Sequence")
            for key, value in seq.__dict__.items():
                # Check if attribute exists
                if not hasattr(self, key):   # dont't overwrite system
                    # raise AttributeError("Attribute %s not found in SequenceProvider" % key)
                    continue
                # Set attribute
                setattr(self, key, value)
        except (ValueError, AttributeError) as exc:
            self.log.exception("Could not set sequence: %s" % exc, exc_info=True)
            raise exc

    def to_pypulseq(self) -> Sequence | None:
        """Slice sequence provider to return pypulseq sequence."""
        seq = Sequence()
        try:
            for key, value in vars(self).items():
                if hasattr(seq, key):
                    setattr(seq, key, value)
        except Exception as exc:
            self.log.error("Could not slice pypulseq sequence from sequence provider.", exc_info=exc)
            return None
        return seq

    # -------- Public interface -------- #

    def dict(self) -> dict:
        """Abstract method which returns variables for logging in dictionary."""
        return {
            "rf_to_mvolt": self.rf_to_mvolt,
            "spcm_freq": self.spcm_freq,
            "spcm_dwell_time": self.spcm_dwell_time,
            "gpa_gain": self.gpa_gain,
            "gradient_efficiency": self.grad_eff,
            "output_limits": self.gradient_out_limits,
        }

    @profile
    def unroll_sequence(self, parameter: AcquisitionParameter) -> UnrolledSequence:
        """Unroll the pypulseq sequence description.

        TODO: Reduce complexity.

        Parameters
        ----------
        parameter
            Instance of AcquisitionParameter containing all necessary parameters to
            calculate the sequence waveforms, i.e. larmor frequency, gradient offsets, etc.

        Returns
        -------
            UnrolledSequence
                Instance of an unrolled sequence object which contains a list of numpy arrays with
                the block-wise calculated sample points in correct spectrum card order (Fortran).

                The list of unrolled sequence arrays is returned as uint16 values which contain a digital
                signal encoded by 15th bit. Only the RF channel does not contain a digital signal.
                In addition, all receive events are described and returned in a list within the unrolled
                sequence object.

        Examples
        --------
        For channels ch0, ch1, ch2, ch3, data values n = 0, 1, ..., N are ordered the following way.

        >>> data = [ch0_0, ch1_0, ch2_0, ch3_0, ch0_1, ch1_1, ..., ch0_n, ..., ch3_N]

        Per channel data can be extracted by the following code.

        >>> rf = seq[0::4]
        >>> gx = (seq[1::4] << 1).astype(np.int16)
        >>> gy = (seq[2::4] << 1).astype(np.int16)
        >>> gz = (seq[3::4] << 1).astype(np.int16)

        All the gradient channels contain a digital signal encoded by the 15th bit.
        - `gx`: ADC gate signal
        - `gy`: Reference signal for phase correction
        - `gz`: RF unblanking signal
        The following example shows, how to extract the digital signals

        >>> adc_gate = seq[1::4].astype(np.uint16) >> 15
        >>> reference = seq[2::4].astype(np.uint16) >> 15
        >>> unblanking = seq[3::4].astype(np.uint16) >> 15

        As the 15th bit is not encoding the sign (as usual for int16), the values are casted to uint16 before shifting.
        """
        try:
            self._check_parameter(parameter)
            self._check_sequence()
        except Exception:
            self.log.exception("Checks not passed")
            raise

        gradient_index: Dimensions = parameter.channel_assignment

        # Get list of all events and list of unique RF and ADC events, since they are frequently reused
        events_list = self.block_events

        # Calculate rf pulse and unblanking waveforms from RF event
        rf_events = [
            (rf_pulse[0], Sequence.rf_from_lib_data(self, rf_pulse[1])) for rf_pulse in self.rf_library.data.items()
        ]
        rf_pulses = {}
        for rf_event in rf_events:
            rf_pulses[rf_event[0]] = self._calculate_rf(
                block=rf_event[1],
                b1_scaling=parameter.b1_scaling,
                larmor_frequency=parameter.larmor_frequency,
            )

        seq_duration, _, _ = self.duration()
        seq_samples = round(seq_duration * self.spcm_freq)

        # Calculate the start time (and sample position) and duration of each block
        block_durations = np.array(
            [self.get_block(block_idx).block_duration for block_idx in list(events_list.keys())],
        )
        block_durations = np.round(block_durations * self.spcm_freq).astype(int)
        block_pos = np.cumsum(block_durations, dtype=np.int64)
        block_pos = np.insert(block_pos, 0, 0)

        if seq_samples != block_pos[-1]:
            msg = "Number of sequence samples does not match total number of block samples"
            raise IndexError(msg)

        # Setup output arrays
        _seq = np.zeros(4 * seq_samples, dtype=np.int16)
        _rx_data = []  # list containing rx data objects for each ADC event

        # Count the total number of sample points and gate signals
        adc_count: int = 0
        labels = {}

        for event_idx, (event_key, event) in enumerate(events_list.items()):
            block = self.get_block(event_key)
            # Calculate gradient waveform start and end positions according to block position
            waveform_start = block_pos[event_idx] * 4

            if block.gx is not None:  # Gx event
                waveform = self._calculate_gradient(
                    block=block.gx,
                    # FoV scaling refers to the sequence, block.gx -> x
                    fov_scaling=parameter.fov_scaling.x,
                    # Offset value are set independent of the sequence orientation,
                    # must be considered with respect to the target output channel!
                    # Offsets mapping: x -> channel 1, y -> channel 2, z -> channel 3
                    offset=parameter.gradient_offset.to_list()[int(gradient_index.x-1)],
                    # Gradient indexing starts at 1 (RF is channel 0)
                    # -> correct indexing to match tuple index
                    output_channel=int(gradient_index.x-1),
                )
                delay = block.gx.delay
                delay_samples = round(delay * self.spcm_freq)
                waveform_start_gx = waveform_start + 4 * delay_samples
                gx_slice = slice(
                    waveform_start_gx + gradient_index.x,
                    waveform_start_gx + 4 * np.size(waveform) + gradient_index.x,
                    4,
                )
                _seq[gx_slice] = waveform

            if block.gy is not None:  # Gy event
                waveform = self._calculate_gradient(
                    block=block.gy,
                    # FoV scaling refers to the sequence, block.gy -> y
                    fov_scaling=parameter.fov_scaling.y,
                    # Offset value are set independent of the sequence orientation,
                    # must be considered with respect to the target output channel!
                    # Offsets mapping: x -> channel 1, y -> channel 2, z -> channel 3
                    offset=parameter.gradient_offset.to_list()[int(gradient_index.y-1)],
                    # Gradient indexing starts at 1 (RF is channel 0)
                    # -> correct indexing to match tuple index
                    output_channel=int(gradient_index.y-1),
                )
                delay = block.gy.delay
                delay_samples = round(delay * self.spcm_freq)
                waveform_start_gy = waveform_start + 4 * delay_samples
                gy_slice = slice(
                    waveform_start_gy + gradient_index.y,
                    waveform_start_gy + 4 * np.size(waveform) + gradient_index.y,
                    4,
                )
                _seq[gy_slice] = waveform

            if block.gz is not None:  # Gz event
                waveform = self._calculate_gradient(
                    block=block.gz,
                    # FoV scaling refers to the sequence, block.gz -> z
                    fov_scaling=parameter.fov_scaling.z,
                    # Offset value are set independent of the sequence orientation,
                    # must be considered with respect to the target output channel!
                    # Offsets mapping: x -> channel 1, y -> channel 2, z -> channel 3
                    offset=parameter.gradient_offset.to_list()[int(gradient_index.z-1)],
                    # Gradient indexing starts at 1 (RF is channel 0)
                    # -> correct indexing to match tuple index
                    output_channel=int(gradient_index.z-1),
                )
                delay = block.gz.delay
                delay_samples = round(delay * self.spcm_freq)
                waveform_start_gz = waveform_start + 4 * delay_samples
                gz_slice = slice(
                    waveform_start_gz + gradient_index.z,
                    waveform_start_gz + 4 * np.size(waveform) + gradient_index.z,
                    4,
                )
                _seq[gz_slice] = waveform

            if block.rf is not None:  # RF event
                # Pre-calculated RF event size can be shorter than the duration of the block since it doesn't
                # consider the post-pulse ring-down time. The RF waveform is placed at the start of the block
                # and the array is then sliced using the duration of the RF waveform to ensure a good fit
                rf_waveform = rf_pulses[event[1]][0].real.astype(np.int16)
                rf_unblanking = rf_pulses[event[1]][1]

                rf_size = np.size(rf_waveform)  # Get size of the RF waveform
                if rf_size > (block_pos[event_idx + 1] - block_pos[event_idx]):
                    msg = "RF waveform size exceeds block size."
                    raise IndexError(msg)

                # Calculate RF waveform start and end positions according to block position
                rf_start = block_pos[event_idx] * 4
                rf_end = (block_pos[event_idx] + rf_size) * 4

                # Add RF waveform
                _seq[rf_start:rf_end:4] = rf_waveform
                # Add unblanking signal to Z gradient
                _seq[rf_start + 3:rf_end + 3:4] = _seq[rf_start + 3:rf_end + 3:4] | rf_unblanking

            if block.label is not None:
                # Update dictionary with current labels
                for label in block.label.values():
                    labels[label.label] = label.value

            if block.adc is not None:  # ADC event
                # Calculate the number of samples to be discarded from the decimated signal
                num_samples_discard = floor(block.adc.dead_time / block.adc.dwell)
                # Calculate the total gate duration, given by number of samples
                # and two times the number of discarded samples for symmetric adc dead time
                # Note: The total gate duration is only increased if the dead time is a multiple of the adc dwell time.
                total_gate_duration = (block.adc.num_samples + 2 * num_samples_discard) * block.adc.dwell
                num_samples_raw = round(total_gate_duration * self.spcm_freq)

                # Remaining delay = dead_time minus pre- and post-sampling fractions
                remaining_delay = block.adc.delay - num_samples_discard * block.adc.dwell
                num_delay_samples = round(remaining_delay * self.spcm_freq)

                adc_start = (block_pos[event_idx] + num_delay_samples) * 4
                adc_end = adc_start + num_samples_raw * 4

                # Add ADC gate to 16th bit of output channel 1 (first gradient channel)
                _seq[adc_start + 1:adc_end + 1:4] |= np.uint16(2**15)

                # Add phase reference signal
                num_samples_reference = min(num_samples_raw, self.phase_reference.size)
                phase_ref_end = adc_start + num_samples_reference * 4
                _seq[adc_start + 2:phase_ref_end + 2:4] |= self.phase_reference[:num_samples_reference]

                _rx_data.append(
                    RxData(
                        index=adc_count,
                        num_samples=block.adc.num_samples,
                        num_samples_raw=num_samples_raw,
                        num_samples_discard=num_samples_discard,
                        dwell_time=block.adc.dwell,
                        dwell_time_raw=self.spcm_dwell_time,
                        phase_offset=block.adc.phase_offset,
                        freq_offset=block.adc.freq_offset,
                        total_averages=parameter.num_averages,
                        ddc_method=parameter.ddc_method,
                        phase_ref_frequency=REFERENCE_FREQUENCY,
                        labels=labels,
                    )
                )
                adc_count += 1
                labels = {}  # Reset labels dict

        self.log.debug(
            "Unrolled sequence; Total sample points: %s; Total block events: %s",
            seq_samples,
            len(block_durations),
        )

        return UnrolledSequence(
            seq=_seq,
            sample_count=seq_samples,
            gpa_gain=self.gpa_gain,
            gradient_efficiency=self.grad_eff,
            rf_to_mvolt=self.rf_to_mvolt,
            dwell_time=self.spcm_dwell_time,
            gradient_output_limits=self.gradient_out_limits,
            rf_output_limit=self.rf_out_limit,
            duration=self.duration()[0],
            adc_count=adc_count,
            parameter=parameter,
            rx_data=_rx_data,
        )

    # -------- Private waveform calculation functions -------- #

    @profile
    def _calculate_rf(
        self,
        block: SimpleNamespace,
        larmor_frequency: float,
        b1_scaling: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Calculate RF sample points to be played by TX card.

        Parameters
        ----------
        block
            Pulseq RF block
        larmor_frequency
            Larmor frequency of RF waveform
        b1_scaling
            Experiment dependent scaling factor of the RF amplitude

        Returns
        -------
            List with the RF pulse in the first element, and the unblanking signal in the second element

        Raises
        ------
        ValueError
            Invalid RF block
        """
        try:
            if not block.type == "rf":
                raise ValueError("Sequence block event is not a valid RF event.")
            if not larmor_frequency > 0.:
                raise ValueError(f"Invalid Larmor frequency: {larmor_frequency}")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Calculate the number of delay samples before an RF event (and unblanking)
        # Note that the RF ring-down time is handled implicitly: the block duration used to place the RF waveform
        # already includes the post-pulse dead time, so no additional handling is required.
        # Dead-time is automatically set as delay! Delay accounts for start of RF event
        num_samples_delay = round(max(block.dead_time, block.delay) * self.spcm_freq)
        # Calculate the number of dead-time samples between unblanking and RF event
        # Delay - dead-time samples account for start of unblanking
        num_samples_dead_time = round(block.dead_time * self.spcm_freq)
        # Calculate the number of RF shape sample points
        num_samples = round(block.shape_dur * self.spcm_freq)

        # Set unblanking signal: 16th bit set to 1 (high)
        rf_unblanking_start = num_samples_delay - num_samples_dead_time
        rf_unblanking_end = num_samples_delay + num_samples
        rf_unblanking = np.zeros(rf_unblanking_end, dtype=np.uint16)
        rf_unblanking[rf_unblanking_start:] = 2**15

        # Calculate the static phase offset, defined by RF pulse
        phase_offset = np.exp(1j * block.phase_offset)

        # Calculate scaled envelope and convert to int16 scale (not datatype, since we use complex numbers)
        # Perform this step here to save computation time, num. of envelope samples << num. of resampled signal
        try:
            # RF scaling according to B1 calibration and "device" (translation from pulseq to output voltage)
            rf_scaling = b1_scaling * self.rf_to_mvolt * phase_offset / self.rf_out_limit
            if np.abs(np.amax(envelope_scaled := block.signal * rf_scaling)) > 1:
                raise ValueError("RF magnitude exceeds output limit.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        envelope_scaled = envelope_scaled * INT16_MAX

        # Resampling of scaled complex envelope
        envelope = resample(envelope_scaled, num=num_samples)

        # Only precalculate carrier time array, calculate carrier here to take into account the
        # frequency and phase offsets of an RF block event
        carrier_time = np.arange(num_samples) * self.spcm_dwell_time
        carrier = np.exp(2j * np.pi * (larmor_frequency + block.freq_offset) * carrier_time)

        try:
            waveform_rf = np.concatenate((np.zeros(num_samples_delay, dtype=complex), (envelope * carrier)))
        except IndexError as err:
            self.log.exception(err, exc_info=True)

        return (waveform_rf, rf_unblanking)

    @profile
    def _calculate_gradient(
        self,
        block: SimpleNamespace,
        fov_scaling: float,
        offset: float,
        output_channel: int,
    ) -> np.ndarray:
        """Calculate spectrum-card sample points of a pypulseq gradient block event.

        Parameters
        ----------
        block
            Gradient block from pypulseq sequence, type must be grad or trap
        unroll_arr
            Section of numpy array which will contain the unrolled gradient event
        fov_scaling
            Scaling factor to adjust the FoV.
            Factor is applied to the whole gradient waveform, exception the amplitude offset.

        Returns
        -------
            Array with sample points of RF waveform as int16 values

        Raises
        ------
        ValueError
            Invalid block type (must be either ``grad`` or ``trap``),
            gradient amplitude exceeds channel maximum output level
        """
        try:
            # Calculate gradient waveform scaling
            scaling = fov_scaling / (
                self.system.gamma * 1e-3 * self.gpa_gain[output_channel] * self.grad_eff[output_channel]
            )

            # Calculate the gradient waveform relative to max output (within the interval [0, 1])
            if block.type == "grad":
                # Arbitrary gradient waveform, interpolate linearly
                # This function requires float input => cast to int16 afterwards
                waveform = block.waveform * scaling / self.gradient_out_limits[output_channel]
                self._check_gradient_amplitude(output_channel, np.abs(np.amax(waveform)))
                # Transfer mV floating point waveform values to int16 if amplitude check passed
                waveform_i16 = waveform * INT16_MAX
                # Interpolate waveform on spectrum card time raster
                gradient = np.interp(
                    x=np.linspace(block.tt[0], block.tt[-1], round(block.shape_dur / self.spcm_dwell_time)),
                    xp=block.tt,
                    fp=waveform_i16,
                )

            elif block.type == "trap":
                # Construct trapezoidal gradient from rise, flat and fall sections
                flat_amp = block.amplitude * scaling / self.gradient_out_limits[output_channel]
                self._check_gradient_amplitude(output_channel, np.abs(np.amax(flat_amp)))
                # Transfer relative floating point flat amplitude to int16 if amplitude check passed
                flat_amp_i16 = flat_amp * INT16_MAX
                # Define rise, flat and fall sections of trapezoidal gradient on spectrum card time raster
                rise = np.linspace(0, flat_amp_i16, round(block.rise_time / self.spcm_dwell_time))
                flat = np.full(round(block.flat_time / self.spcm_dwell_time), fill_value=flat_amp_i16)
                fall = np.linspace(flat_amp_i16, 0, round(block.fall_time / self.spcm_dwell_time))
                # Combine rise, flat and fall sections to gradient waveform
                gradient = np.concatenate((rise, flat, fall))

            else:
                raise ValueError("Block is not a valid gradient block")

            # Calculate gradient offset int16 value from mV
            # Gradient offset is used for calculating output limits but is not added to the waveform
            offset_i16 = offset * INT16_MAX / self.gradient_out_limits[output_channel]
            # This is the combined int16 gradient and offset waveform as float dtype
            combined_i16 = gradient + offset_i16
            if (max_strength_i16 := np.amax(combined_i16)) > INT16_MAX:
                # Report maximum strength in mV
                max_strength = max_strength_i16 * self.gradient_out_limits[output_channel] / INT16_MAX
                msg = f"Amplitude of combined gradient and shim waveforms {max_strength} exceed max gradient amplitude"
                raise ValueError(msg)

            # Shifting gradient waveform to 15 bits already for adding the gate signals later
            return gradient.astype(np.int16).view(np.uint16) >> 1

        except (ValueError, IndexError):
            self.log.exception("Error calculating gradient")
            raise

    # -------- Private validation methods -------- #

    def _check_gradient_amplitude(self, idx: int, rel_value: float) -> None:
        """Raise error if amplitude exceeds output limit."""
        limit = self.gradient_out_limits[idx]
        if np.abs(rel_value) > 1.:
            msg = f"Amplitude of gradient channel {idx+1} ({rel_value*limit}) exceeded output limit ({limit}))"
            raise ValueError(msg)

    def _check_parameter(self, parameter: AcquisitionParameter) -> None:
        """Check acquisition parameter and raise error if invalid."""
        # Check larmor frequency
        f0_limit = self.spcm_freq / 2
        if parameter.larmor_frequency >= f0_limit:
            msg = f"Larmor frequency too high ({parameter.larmor_frequency * 1e-6} MHz), violating sampling theorem"
            raise ValueError(msg)
        if parameter.larmor_frequency <= 0:
            msg = "Larmor frequency invalid (<= 0)."
            raise ValueError(msg)

        # Validate channel assignment
        grad_ch: Dimensions = parameter.channel_assignment
        if not all(isinstance(v, int) for v in (grad_ch.x, grad_ch.y, grad_ch.z)):
            raise TypeError("All channel_assignment values must be integers.")
        if {grad_ch.x, grad_ch.y, grad_ch.z} != {1, 2, 3}:
            msg = f"Invalid channel assignment, must contain each of 1, 2, and 3 exactly once, got: {grad_ch}"
            raise ValueError(msg)

    def _check_sequence(self) -> None:
        """Check sequence."""
        # Check number of block events
        if not len(self.block_events) > 0:
            raise ValueError("No block events found")
        # Perform sequence timing check
        check, seq_err = self.check_timing()
        if not check:
            raise ValueError(f"Sequence timing check failed: {seq_err}")
