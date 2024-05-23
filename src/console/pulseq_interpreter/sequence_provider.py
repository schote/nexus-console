"""Sequence provider class."""
import logging
from types import SimpleNamespace
from typing import Any, Callable

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample

import console.spcm_control.globals as glob
from console.interfaces.interface_dimensions import Dimensions
from console.interfaces.interface_unrolled_sequence import UnrolledSequence

try:
    from line_profiler import profile
except ImportError:
    def profile(func: Callable[..., Any]) -> Callable[..., Any]:
        """Define placeholder for profile decorator."""
        return func


INT16_MAX = np.iinfo(np.int16).max
INT16_MIN = np.iinfo(np.int16).min

default_opts: Opts = Opts()
default_fov_scaling: Dimensions = Dimensions(1, 1, 1)
default_fov_offset: Dimensions = Dimensions(0, 0, 0)


class SequenceProvider(Sequence):
    """Sequence provider class.

    This object is inherited from pulseq sequence object, so that all methods of the
    pypulseq ``Sequence`` object can be accessed.

    The main functionality of the ``SequenceProvider`` is to unroll a given pulseq sequence.
    Usually the first step is to read a sequence file. The unrolling step can be achieved using
    the ``unroll_sequence()`` function.

    Example
    -------
    >>> seq = SequenceProvider()
    >>> seq.read("./seq_file.seq")
    >>> sqnc, gate, total_samples = seq.unroll_sequence()
    """

    __name__: str = "SequenceProvider"

    def __init__(
        self,
        gradient_efficiency: list[float],
        gpa_gain: list[float],
        high_impedance: list[bool],
        output_limits: list[int] | None = None,
        spcm_dwell_time: float = 1 / 20e6,
        rf_to_mvolt: float = 1,
        system: Opts = default_opts,
    ):
        """Initialize sequence provider class which is used to unroll a pulseq sequence.

        Parameters
        ----------
        output_limits
            Output limit per channel in mV, includes both, RF and gradients, e.g. [200, 6000, 6000, 6000]
        gradient_efficiency
            Efficiency of the gradient coils in mT/m/A, e.g. [0.4e-3, 0.4e-3, 0.4e-3]
        gpa_gain
            Gain factor of the GPA per gradient channel, e.g. [4.7, 4.7, 4.7]
        spcm_dwell_time, optional
            Sampling time raster of the output waveform (depends on spectrum card), by default 1/20e6
        rf_to_mvolt, optional
            Translation of RF waveform from pulseq (Hz) to mV, by default 1
        system, optional
            System options from pypulseq, by default Opts()
        """
        super().__init__(system=system)

        self.log = logging.getLogger("SeqProv")
        self.rf_to_mvolt = rf_to_mvolt
        self.spcm_freq = 1 / spcm_dwell_time
        self.spcm_dwell_time = spcm_dwell_time

        try:
            if len(gradient_efficiency) != 3:
                raise ValueError("Invalid number of gradient efficiency values, 3 values must be provided")
            if len(gpa_gain) != 3:
                raise ValueError("Invalid number of GPA gain values, 3 values must be provided")
            if isinstance(output_limits, list) and len(output_limits) != 4:
                raise ValueError("Invalid number of output limits, 4 values must be provided.")
            if len(high_impedance) != 4:
                raise ValueError("Invalid number of output impedance indicators, 4 values must be provided.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)

        # Set impedance scaling factor, 0.5 if impedance is high, 1 if impedance is 50 ohms
        # Halve RF scaling factor if impedance is high, because the card output doubles for high impedance
        self.imp_scaling = [0.5 if z else 1 for z in high_impedance]
        self.high_impedance = high_impedance

        self.gpa_gain: list[float] = gpa_gain
        self.grad_eff: list[float] = gradient_efficiency
        self.output_limits: list[int] = output_limits if output_limits is not None else []

        self.larmor_freq: float = float("nan")
        self.sample_count: int = 0
        self._sqnc_cache: list = []

    def dict(self) -> dict:
        """Abstract method which returns variables for logging in dictionary."""
        return {
            "rf_to_mvolt": self.rf_to_mvolt,
            "spcm_freq": self.spcm_freq,
            "spcm_dwell_time": self.spcm_dwell_time,
            "gpa_gain": self.gpa_gain,
            "gradient_efficiency": self.grad_eff,
            "output_limits": self.output_limits,
            "larmor_freq": self.larmor_freq,
            "sample_count": self.sample_count
        }

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
            if not isinstance(seq, Sequence):
                raise ValueError("Provided object is not an instance of pypulseq Sequence")
            for key, value in seq.__dict__.items():
                # Check if attribute exists
                if not hasattr(self, key):
                    # raise AttributeError("Attribute %s not found in SequenceProvider" % key)
                    continue
                # Set attribute
                setattr(self, key, value)
        except (ValueError, AttributeError) as err:
            self.log.exception(err, exc_info=True)
            raise err

    @profile
    def calculate_rf(
        self,
        block: SimpleNamespace,
        unroll_arr: np.ndarray,
        b1_scaling: float,
        unblanking: np.ndarray,
        num_samples_rf_start: int = 0,
    ) -> None:
        """Calculate RF sample points to be played by TX card.

        Parameters
        ----------
        block
            Pulseq RF block
        unroll_arr
            Section of numpy array which will contain unrolled RF event
        b1_scaling
            Experiment dependent scaling factor of the RF amplitude
        unblanking
            Unblanking signal which is updated in-place for the calculated RF event
        num_samples_rf_start
            Number of samples until the first RF event in the sequence.
            This value is important to calculate the correct carrier wave phase offset.

        Returns
        -------
            Array with sample points of RF waveform as int16 values

        Raises
        ------
        ValueError
            Invalid RF block
        """
        try:
            if not block.type == "rf":
                raise ValueError("Sequence block event is not a valid RF event.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Calculate the number of delay samples before an RF event (and unblanking)
        # Dead-time is automatically set as delay! Delay accounts for start of RF event
        num_samples_delay = int(max(block.dead_time, block.delay) * self.spcm_freq)
        # Calculate the number of dead-time samples between unblanking and RF event
        # Delay - dead-time samples account for start of unblanking
        num_samples_dead_time = int(block.dead_time * self.spcm_freq)
        # Calculate the number of ringdown samples at the end of RF pulse
        # num_samgles_ringdown = int(block.ringdown_time * self.spcm_freq)
        # Calculate the number of RF shape sample points
        num_samples = int(block.shape_dur * self.spcm_freq)

        # Set unblanking signal: 16th bit set to 1 (high)
        unblanking_start = num_samples_delay - num_samples_dead_time
        unblanking_end = num_samples_delay + num_samples
        unblanking[unblanking_start:unblanking_end] = 1

        # Calculate the static phase offset, defined by RF pulse
        phase_offset = np.exp(1j * block.phase_offset)

        # Calculate scaled envelope and convert to int16 scale (not datatype, since we use complex numbers)
        # Perform this step here to save computation time, num. of envelope samples << num. of resampled signal
        try:
            # RF scaling according to B1 calibration and "device" (translation from pulseq to output voltage)
            rf_scaling = b1_scaling * self.rf_to_mvolt * self.imp_scaling[0] / self.output_limits[0]
            if np.abs(np.amax(envelope_scaled := block.signal * phase_offset * rf_scaling)) > 1:
                raise ValueError("RF magnitude exceeds output limit.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        envelope_scaled = envelope_scaled * INT16_MAX

        # Resampling of scaled complex envelope
        envelope = resample(envelope_scaled, num=num_samples)

        # Calculate phase offset of RF according to total sample count
        carrier_phase_samples = self.sample_count + num_samples_delay - num_samples_rf_start
        carrier_phase_offset = carrier_phase_samples * self.spcm_dwell_time

        # Only precalculate carrier time array, calculate carriere here to take into account the
        # frequency and phase offsets of an RF block event
        carrier_time = np.arange(num_samples) * self.spcm_dwell_time
        carrier = np.exp(2j * np.pi * ((self.larmor_freq + block.freq_offset) * carrier_time + carrier_phase_offset))

        try:
            # Calculate position indices for unrolled RF event
            idx_signal_end = num_samples_delay + num_samples
            # Check if end index of unrolled signal exceeds available array dimension
            if idx_signal_end > unroll_arr.size:
                raise IndexError("Unrolled RF event exceeds number of block samples")
            # Write unrolled RF event in place
            unroll_arr[num_samples_delay:idx_signal_end] = (envelope * carrier).real.astype(np.int16)
        except IndexError as err:
            self.log.exception(err, exc_info=True)
            raise err

    @profile
    def calculate_gradient(self, block: SimpleNamespace, unroll_arr: np.ndarray, fov_scaling: float) -> None:
        """Calculate spectrum-card sample points of a pypulseq gradient block event.

        Parameters
        ----------
        block
            Gradient block from pypulseq sequence, type must be grad or trap
        unroll_arr
            Section of numpy array which will contain the unrolled gradient event
        fov_scaling
            Scaling factor to adjust the FoV.
            Factor is applied to the whole gradient waveform, excepton the amplitude offset.

        Returns
        -------
            Array with sample points of RF waveform as int16 values

        Raises
        ------
        ValueError
            Invalid block type (must be either ``grad`` or ``trap``),
            gradient amplitude exceeds channel maximum output level
        IndexError
            Unrolled gradient waveform does not fit in unrolled array shape
        """
        # Both gradient types have a delay, calculate delay in number of samples
        samples_delay = int(block.delay * self.spcm_freq)
        # Index of this gradient, dependent on channel designation, offset of 1 to start at channel 1
        idx = ["x", "y", "z"].index(block.channel)

        # Calculate gradient offset int16 value from mV
        # block.channel is either x, y or z and used to obtain correct gradient offset dimension/channel
        offset = getattr(glob.parameter.gradient_offset, block.channel) / INT16_MAX * self.output_limits[idx + 1]

        # Calculat gradient waveform scaling
        scaling = fov_scaling * self.imp_scaling[idx + 1] / (42.58e3 * self.gpa_gain[idx] * self.grad_eff[idx])

        try:
            # Calculate the gradient waveform relative to max output (within the interval [0, 1])
            if block.type == "grad":
                # Arbitrary gradient waveform, interpolate linearly
                # This function requires float input => cast to int16 afterwards
                if np.amax(waveform := block.waveform * scaling) + offset > self.output_limits[idx + 1]:
                    raise ValueError(
                        "Amplitude of %s (%s) gradient exceeded output limit (%s)"
                        % (
                            block.channel,
                            np.amax(waveform),
                            self.output_limits[idx + 1],
                        )
                    )
                # Trasnfer mV floating point waveform values to int16 if amplitude check passed
                waveform *= INT16_MAX / self.output_limits[idx + 1]

                gradient = np.interp(
                    x=np.linspace(
                        block.tt[0],
                        block.tt[-1],
                        int(block.shape_dur / self.spcm_dwell_time),
                    ),
                    xp=block.tt,
                    fp=waveform,
                ).astype(np.int16)

            elif block.type == "trap":
                # Construct trapezoidal gradient from rise, flat and fall sections
                if np.amax(flat_amp := block.amplitude * scaling) + offset > self.output_limits[idx + 1]:
                    raise ValueError(
                        f"Amplitude of {block.channel} gradient exceeded max. amplitude {self.output_limits[idx + 1]}."
                    )

                # Trasnfer mV floating point flat amplitude to int16 if amplitude check passed
                flat_amp = np.int16(flat_amp * INT16_MAX / self.output_limits[idx + 1])

                rise = np.linspace(
                    0,
                    flat_amp,
                    int(block.rise_time / self.spcm_dwell_time),
                    dtype=np.int16,
                )
                flat = np.full(
                    int(block.flat_time / self.spcm_dwell_time),
                    fill_value=flat_amp,
                    dtype=np.int16,
                )
                fall = np.linspace(
                    flat_amp,
                    0,
                    int(block.fall_time / self.spcm_dwell_time),
                    dtype=np.int16,
                )

                gradient = np.concatenate((rise, flat, fall))

            else:
                raise ValueError("Block is not a valid gradient block")

            # Check if gradient waveform fits into unroll array space
            if (index_end := samples_delay + gradient.size) > unroll_arr.size:
                raise IndexError("Unrolled gradient event exceeds number of block samples")

            # Add gradient waveform (trapezoid or arbitrary) in place
            unroll_arr[samples_delay:index_end] = gradient

        except (ValueError, IndexError) as err:
            self.log.exception(err, exc_info=True)
            raise err

    @profile
    def add_adc_gate(self, block: SimpleNamespace, gate: np.ndarray, clk_ref: np.ndarray) -> None:
        """Add ADC gate signal and reference signal during gate inplace to gate and reference arrays.

        Parameters
        ----------
        block
            ADC event of sequence block.
        gate
            Gate array, predefined by zeros. If ADC event is present, the corresponding range is set to one.
        clk_ref
            Phase reference array, predefined by zeros. Digital signal during ADC which encodes the signal phase.
        """
        delay = max(int(block.delay * self.spcm_freq), int(block.dead_time * self.spcm_freq))
        adc_dur = block.num_samples * block.dwell
        adc_len = round(adc_dur * self.spcm_freq)
        # Gate signal
        gate[delay : delay + adc_len] = 1

        # Calculate reference signal with phase offset (dependent on total number of samples at beginning of adc)
        offset = self.sample_count * self.spcm_dwell_time
        ref_time = np.arange(clk_ref.size) * self.spcm_dwell_time

        # Time consuming operation, if computed over the whole gate
        # Instead limit to max(clk_ref.size, 2000) to use at most the first 2000 samples for phase synchronization
        # 2000 samples == 0.1 ms, at 2 MHz this still covers 200 cycles
        ref_signal = np.exp(2j * np.pi * (self.larmor_freq * ref_time + offset))
        # Digital reference signal, sin > 0 is high, 16th bit set to 1 (high)
        clk_ref[ref_signal > 0] = 1

    @profile
    def unroll_sequence(self) -> UnrolledSequence:
        """Unroll the pypulseq sequence description.

        TODO: Update this docstring

        Parameters
        ----------
        larmor_freq
            (Larmor) frequency of the carrier RF waveform
        b1_scaling, optional
            Factor for the RF waveform, which is to be calibrated per coil and phantom (load), by default 1.0
        fov_scaling, optional
            Per channel factor for the gradient waveforms to scale the field of fiew (FOV),
            by default Dimensions(1.0, 1.0, 1.0)

        Returns
        -------
            UnrolledSequence
                Instance of an unrolled sequence object which contains a list of numpy arrays with
                the block-wise calculated sample points in correct spectrum card order (Fortran).

                The list of unrolled sequence arrays is returned as uint16 values which contain a digital
                signal encoded by 15th bit. Only the RF channel does not contain a digital signal.
                In addition, the adc and unblanking signals are returned as list of numpy arrays in the
                unrolled sequence instance.

        Raises
        ------
        ValueError
            Larmor frequency too large
        ValueError
            No block events defined
        ValueError
            Sequence timing check failed
        ValueError
            Amplitude limits not provided

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
        if self._sqnc_cache:
            self._sqnc_cache = []

        try:
            # Check larmor frequency
            if glob.parameter.larmor_frequency > 10e6:
                raise ValueError(f"Larmor frequency is above 10 MHz: {glob.parameter.larmor_frequency * 1e-6} MHz")
            self.larmor_freq = glob.parameter.larmor_frequency

            # Check if sequence has block events
            if not len(self.block_events) > 0:
                raise ValueError("No block events found")

            # Sequence timing check
            check, seq_err = self.check_timing()
            if not check:
                raise ValueError(f"Sequence timing check failed: {seq_err}")

        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Get all blocks in a list and pre-calculate number of sample points per block
        # to allocate empty sequence array.
        blocks = [self.get_block(k) for k in list(self.block_events.keys())]
        samples_per_block = [round(block.block_duration / self.spcm_dwell_time) for block in blocks]

        # Internal list of arrays to store sequence and digital signals
        # Empty list of list, 4 channels => 4 times n_samples
        # Sequence, ADC events, unblanking and reference signal (for phase synchronization)
        _seq = [np.zeros(4 * n, dtype=np.int16) for n in samples_per_block]
        _adc = [np.zeros(n, dtype=np.int16) for n in samples_per_block]
        _unblanking = [np.zeros(n, dtype=np.int16) for n in samples_per_block]
        _ref = [np.zeros(n, dtype=np.int16) for n in samples_per_block]

        # Count the total number of sample points and gate signals
        self.sample_count = 0
        adc_count: int = 0
        rf_start_sample_pos: int | None = None

        for k, (n_samples, block) in enumerate(zip(samples_per_block, blocks, strict=True)):

            if block.rf is not None and block.rf.signal.size > 0:
                # Every 4th value in _seq starting at index 0 belongs to RF
                if rf_start_sample_pos is None:
                    rf_start_sample_pos = self.sample_count
                self.calculate_rf(
                    block=block.rf,
                    unroll_arr=_seq[k][0::4],
                    unblanking=_unblanking[k],
                    b1_scaling=glob.parameter.b1_scaling,
                    num_samples_rf_start=rf_start_sample_pos,
                )

            if block.adc is not None:
                self.add_adc_gate(block.adc, _adc[k], _ref[k])
                adc_count += 1

            if block.gx is not None:
                # Every 4th value in _seq starting at index 1 belongs to x gradient
                self.calculate_gradient(
                    block=block.gx, unroll_arr=_seq[k][1::4], fov_scaling=glob.parameter.fov_scaling.x
                )
            if block.gy is not None:
                # Every 4th value in _seq starting at index 2 belongs to y gradient
                self.calculate_gradient(
                    block=block.gy, unroll_arr=_seq[k][2::4], fov_scaling=glob.parameter.fov_scaling.y
                )
            if block.gz is not None:
                # Every 4th value in _seq starting at index 3 belongs to z gradient
                self.calculate_gradient(
                    block=block.gz, unroll_arr=_seq[k][3::4], fov_scaling=glob.parameter.fov_scaling.z
                )

            # Bitwise operations to merge gx with adc and gy with unblanking
            _seq[k][1::4] = _seq[k][1::4].view(np.uint16) >> 1 | (_adc[k] << 15)
            _seq[k][2::4] = _seq[k][2::4].view(np.uint16) >> 1 | (_ref[k] << 15)
            _seq[k][3::4] = _seq[k][3::4].view(np.uint16) >> 1 | (_unblanking[k] << 15)

            # Count the total amount of samples (for one channel) to keep track of the phase
            self.sample_count += n_samples

        self.log.debug(
            "Unrolled sequence; Total sample points: %s; Total block events: %s",
            self.sample_count,
            len(blocks),
        )

        # Save unrolled sequence in class
        self._sqnc_cache = _seq

        return UnrolledSequence(
            seq=_seq,
            adc_gate=_adc,
            rf_unblanking=_unblanking,
            sample_count=self.sample_count,
            gpa_gain=self.gpa_gain,
            gradient_efficiency=self.grad_eff,
            rf_to_mvolt=self.rf_to_mvolt,
            dwell_time=self.spcm_dwell_time,
            larmor_frequency=self.larmor_freq,
            duration=self.duration()[0],
            adc_count=adc_count,
        )

    def plot_unrolled(
            self, time_range: tuple[int, int] = (0, -1)
        ) -> tuple[matplotlib.figure.Figure, np.ndarray]:
        """Plot unrolled waveforms for replay.

        Parameters
        ----------
        time_range, default = (0, -1)
            Specify the time range of the plot in seconds.
            If the second value is smaller then the first or -1, the whole sequence is plotted.

        Returns
        -------
            Matplotlib figure and axis
        """
        fig, axis = plt.subplots(5, 1, figsize=(16, 9))

        if not self._sqnc_cache:
            print("No unrolled sequence...")
            return fig, axis

        seq_start = int(time_range[0] * self.spcm_freq)
        seq_end = int(time_range[1] * self.spcm_freq) if time_range[1] > time_range[0] else -1
        samples = np.arange(self.sample_count, dtype=float)[seq_start:seq_end] * self.spcm_dwell_time * 1e3

        sqnc = np.concatenate(self._sqnc_cache)
        rf_signal = sqnc[0::4][seq_start:seq_end]
        gx_signal = sqnc[1::4][seq_start:seq_end]
        gy_signal = sqnc[2::4][seq_start:seq_end]
        gz_signal = sqnc[3::4][seq_start:seq_end]

        # Get digital signals
        adc_gate = gx_signal.astype(np.uint16) >> 15
        unblanking = gz_signal.astype(np.uint16) >> 15

        # Get gradient waveforms
        rf_signal = rf_signal / np.abs(np.iinfo(np.int16).min)
        gx_signal = (np.uint16(gx_signal) << 1).astype(np.int16) / np.abs(np.iinfo(np.int16).min)
        gy_signal = (np.uint16(gy_signal) << 1).astype(np.int16) / np.abs(np.iinfo(np.int16).min)
        gz_signal = (np.uint16(gz_signal) << 1).astype(np.int16) / np.abs(np.iinfo(np.int16).min)

        axis[0].plot(samples, self.output_limits[0] * rf_signal)
        axis[1].plot(samples, self.output_limits[1] * gx_signal)
        axis[2].plot(samples, self.output_limits[2] * gy_signal)
        axis[3].plot(samples, self.output_limits[3] * gz_signal)
        axis[4].plot(samples, adc_gate, label="ADC gate")
        axis[4].plot(samples, unblanking, label="RF unblanking")

        axis[0].set_ylabel("RF [mV]")
        axis[1].set_ylabel("Gx [mV]")
        axis[2].set_ylabel("Gy [mV]")
        axis[3].set_ylabel("Gz [mV]")
        axis[4].set_ylabel("Digital")
        axis[4].legend(loc="upper right")

        _ = [ax.grid(axis="x") for ax in axis]

        axis[4].set_xlabel("Time [ms]")

        return fig, axis
