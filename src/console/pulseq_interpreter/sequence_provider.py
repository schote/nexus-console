"""Sequence provider class."""
import logging
from types import SimpleNamespace

import numpy as np
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.spcm_control.interface_acquisition_parameter import Dimensions

# from line_profiler import profile


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

    def __init__(
        self,
        spcm_dwell_time: float = 1 / 20e6,
        grad_to_volt: float = 1,
        rf_to_volt: float = 1,
        output_limits: list[int] | None = None,
        system: Opts = Opts(),
    ):
        """Init function for sequence provider class."""
        super().__init__(system=system)

        self.log = logging.getLogger("SeqProv")

        self.grad_to_volt = grad_to_volt
        self.rf_to_volt = rf_to_volt
        self.spcm_freq = 1 / spcm_dwell_time
        self.spcm_dwell_time = spcm_dwell_time
        self.larmor_freq = self.system.B0 * self.system.gamma
        self.sample_count: int = 0
        self.int16_max = np.iinfo(np.int16).max
        self.output_limits: list[int] = [] if output_limits is None else output_limits

    # @profie
    def calculate_rf(
        self, rf_block: SimpleNamespace, b1_scaling: float, unblanking: np.ndarray, num_total_samples: int
    ) -> np.ndarray:
        """Calculate RF sample points to be played by TX card.

        Parameters
        ----------
        rf_block
            Pulseq RF block
        b1_scaling
            Experiment dependent scaling factor of the RF amplitude
        unblanking
            Unblanking signal which is updated in-place for the calculated RF event

        Returns
        -------
            Array with sample points of RF waveform as int16 values

        Raises
        ------
        ValueError
            Invalid RF block
        """
        # TODO: Write RF waveform in place
        try:
            if not rf_block.type == "rf":
                raise ValueError("Sequence block event is not a valid RF event.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Calculate zero filling for RF delay
        num_samples_delay = int(rf_block.delay * self.spcm_freq)
        delay = np.zeros(num_samples_delay, dtype=np.int16)

        # Zero filling for RF dead-time (maximum of dead time defined in RF event and system)
        # Time between start of unblanking and start of RF
        dead_dur = max(self.system.rf_dead_time, rf_block.dead_time)
        num_samples_dead = int(dead_dur * self.spcm_freq)
        dead_time = np.zeros(num_samples_dead, dtype=np.int16)

        # Zero filling for RF ringdown (maximum of ringdown time defined in RF event and system)
        ringdown_dur = max(self.system.rf_ringdown_time, rf_block.ringdown_time)
        num_samgles_ringdown = int(ringdown_dur * self.spcm_freq)
        ringdown_time = np.zeros(num_samgles_ringdown, dtype=np.int16)

        # Calculate the number of shape sample points
        num_samples = int(rf_block.shape_dur * self.spcm_freq)

        # Set unblanking signal
        # 16th bit set to 1 (high)
        unblanking[num_samples_delay : -(num_samgles_ringdown + 1)] = 1

        # Calculate the static phase offset, defined by RF pulse
        phase_offset = np.exp(1j * rf_block.phase_offset)

        # RF scaling according to B1 calibration and "device" (translation from pulseq to output voltage)
        rf_scaling = b1_scaling * self.rf_to_volt / self.output_limits[0]

        # Calculate scaled envelope and convert to int16 scale (not datatype, since we use complex numbers)
        # Perform this step here to save computation time, num. of envelope samples << num. of resampled signal
        try:
            if np.amax(envelope_scaled := rf_block.signal * phase_offset * rf_scaling) > 1:
                raise ValueError("RF amplitude exceeded max. amplitude of channel 0.")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        envelope_scaled = envelope_scaled * self.int16_max

        # Resampling of scaled complex envelope
        envelope = resample(envelope_scaled, num=num_samples)

        # Calculate phase offset of RF according to total sample count
        # TODO: Substract samples to first RF event
        phase_offset = (self.sample_count + num_samples_delay + num_samples_dead) * self.spcm_dwell_time

        # Only precalculate carrier time array, calculate carriere here to take into account the
        # frequency and phase offsets of an RF block event
        carrier_time = np.arange(num_samples) * self.spcm_dwell_time
        carrier = np.exp(2j * np.pi * ((self.larmor_freq + rf_block.freq_offset) * carrier_time + phase_offset))
        signal = (envelope * carrier).real.astype(np.int16)

        # Combine signal from delays and rf
        rf_pulse = np.concatenate((delay, dead_time, signal, ringdown_time)).astype(np.int16)

        try:
            if (num_signal_samples := len(rf_pulse)) < num_total_samples:
                # Zero-fill rf signal
                rf_pulse = np.concatenate((rf_pulse, np.zeros(num_total_samples - num_signal_samples, dtype=np.int16)))
            elif num_signal_samples > num_total_samples:
                raise ArithmeticError("Number of signal samples exceeded the total number of block samples.")
        except ArithmeticError as err:
            self.log.exception(err, exc_info=True)
            raise err

        return rf_pulse

    # @profile
    def calculate_gradient(
        self, block: SimpleNamespace, fov_scaling: float, num_total_samples: int, amp_offset: int | float = 0
    ) -> np.ndarray:
        """Calculate spectrum-card sample points of a pypulseq gradient block event.

        Parameters
        ----------
        block
            Gradient block from pypulseq sequence, type must be grad or trap
        num_total_samples
            Total number of block samples points to verify calculation
        amp_offset, optional
            Amplitude offset, last value of last gradient, by default 0.

        Returns
        -------
            Array with sample points of RF waveform as int16 values

        Raises
        ------
        ValueError
            Block type is not grad or trap
        ArithmeticError
            Number of calculated sample points is greater then number of block sample points
        """
        # TODO: Write gradient waveform in place
        # Both gradient types have a delay
        delay = np.full(int(block.delay / self.spcm_dwell_time), fill_value=amp_offset, dtype=np.int16)
        idx = ["x", "y", "z"].index(block.channel)
        offset = np.int16(amp_offset / self.int16_max)
        # Calculate scaling factor of gradient amplitude
        grad_scaling = fov_scaling * self.grad_to_volt / self.output_limits[idx]

        try:
            if block.type == "grad":
                try:
                    if np.amax(waveform := block.waveform * grad_scaling + offset) > 1:
                        raise ValueError(
                            f"Amplitude of {block.channel} gradient exceeded max. amplitude of channel {idx}."
                        )
                except ValueError as err:
                    self.log.exception(err, exc_info=True)
                    raise err

                waveform *= self.int16_max

                # Arbitrary gradient waveform, interpolate linearly
                # This function requires float input => cast to int16 afterwards
                waveform = np.interp(
                    x=np.linspace(block.tt[0], block.tt[-1], int(block.shape_dur / self.spcm_dwell_time)),
                    xp=block.tt,
                    fp=waveform,
                ).astype(np.int16)
                gradient = np.concatenate((delay, waveform))

            elif block.type == "trap":
                # Check and scale trapezoid flat amplitude (including offset)
                # At this point, only a single value needs to be scaled
                try:
                    if np.amax(flat_amp := block.amplitude * grad_scaling + offset) > 1:
                        raise ValueError(
                            f"Amplitude of {block.channel} gradient exceeded max. amplitude of channel {idx}."
                        )
                except ValueError as err:
                    self.log.exception(err, exc_info=True)
                    raise err

                flat_amp = np.int16(flat_amp * self.int16_max)

                # Trapezoidal gradient, combine resampled rise, flat and fall sections
                rise = np.linspace(amp_offset, flat_amp, int(block.rise_time / self.spcm_dwell_time), dtype=np.int16)
                flat = np.full(int(block.flat_time / self.spcm_dwell_time), fill_value=flat_amp, dtype=np.int16)
                fall = np.linspace(flat_amp, amp_offset, int(block.fall_time / self.spcm_dwell_time), dtype=np.int16)
                gradient = np.concatenate((delay, rise, flat, fall))

            else:
                raise ValueError("Block is not a valid gradient block")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        try:
            if (num_gradient_samples := len(gradient)) < num_total_samples:
                gradient = np.concatenate(
                    (gradient, np.full(num_total_samples - num_gradient_samples, fill_value=gradient[-1]))
                )
            elif num_gradient_samples > num_total_samples:
                raise ArithmeticError("Number of gradient samples exceeded the total number of block samples.")
        except ArithmeticError as err:
            self.log.exception(err, exc_info=True)
            raise err

        return gradient

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
        adc_len = int(adc_dur * self.spcm_freq)
        # Gate signal
        gate[delay : delay + adc_len] = 1

        # Calculate reference signal with phase offset (dependent on total number of samples at beginning of adc)
        offset = self.sample_count * self.spcm_dwell_time
        ref_time = np.arange(clk_ref.size) * self.spcm_dwell_time
        ref_signal = np.exp(2j * np.pi * (self.larmor_freq * ref_time + offset))
        # Digital reference signal, sin > 0 is high
        # 16th bit set to 1 (high)
        clk_ref[ref_signal > 0] = 1

    # @profile
    def unroll_sequence(
        self, larmor_freq: float, b1_scaling: float = 1.0, fov_scaling: Dimensions = Dimensions(1.0, 1.0, 1.0)
    ) -> UnrolledSequence:
        """Unroll the pypulseq sequence description.

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
        try:
            # Check larmor frequency
            if larmor_freq > 10e6:
                raise ValueError(f"Larmor frequency is above 10 MHz: {larmor_freq*1e-6} MHz")
            self.larmor_freq = larmor_freq

            # Check if sequence has block events
            if not len(self.block_events) > 0:
                raise ValueError("No block events found")

            # Sequence timing check
            check, seq_err = self.check_timing()
            if not check:
                raise ValueError(f"Sequence timing check failed: {seq_err}")

            # Check if output limits are defined
            if not self.output_limits:
                raise ValueError("Amplitude output limits are not provided")

        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Get all blocks in a list and pre-calculate number of sample points per block
        # to allocate empty sequence array.
        blocks = [self.get_block(k) for k in list(self.block_events.keys())]
        samples_per_block = [int(block.block_duration / self.spcm_dwell_time) for block in blocks]

        # Internal list of arrays to store sequence and digital signals
        # Empty list of list, 4 channels => 4 times n_samples
        # Sequence, ADC events, unblanking and reference signal (for phase synchronization)
        _seq = [np.zeros(4 * n, dtype=np.int16) for n in samples_per_block]
        _adc = [np.zeros(n, dtype=np.int16) for n in samples_per_block]
        _unblanking = [np.zeros(n, dtype=np.int16) for n in samples_per_block]
        _ref = [np.zeros(n, dtype=np.int16) for n in samples_per_block]

        # Last value of last block is added per channel to the gradient waveform as an offset value.
        # This is needed, since gradients must not be zero at the end of a block.
        grad_offset = Dimensions(x=0, y=0, z=0)

        # Count the total number of sample points and gate signals
        self.sample_count = 0
        adc_count: int = 0

        for k, (n_samples, block) in enumerate(zip(samples_per_block, blocks)):
            # Calculate rf events of current block, zero-fill channels if not defined
            if block.rf is not None and block.rf.signal.size > 0:
                # Every 4th value in _seq starting at index 0 belongs to RF
                _seq[k][0::4] = self.calculate_rf(
                    rf_block=block.rf, unblanking=_unblanking[k], num_total_samples=n_samples, b1_scaling=b1_scaling
                )

            if block.adc is not None:
                self.add_adc_gate(block.adc, _adc[k], _ref[k])
                adc_count += 1

            if block.gx is not None:
                # Every 4th value in _seq starting at index 1 belongs to x gradient
                _seq[k][1::4] = self.calculate_gradient(block.gx, fov_scaling.x, n_samples, grad_offset.x)
            if block.gy is not None:
                # Every 4th value in _seq starting at index 2 belongs to y gradient
                _seq[k][2::4] = self.calculate_gradient(block.gy, fov_scaling.y, n_samples, grad_offset.y)
            if block.gz is not None:
                # Every 4th value in _seq starting at index 3 belongs to z gradient
                _seq[k][3::4] = self.calculate_gradient(block.gz, fov_scaling.z, n_samples, grad_offset.z)

            # Bitwise operations to merge gx with adc and gy with unblanking
            _seq[k][1::4] = _seq[k][1::4].view(np.uint16) >> 1 | (_adc[k] << 15)
            _seq[k][2::4] = _seq[k][2::4].view(np.uint16) >> 1 | (_ref[k] << 15)
            _seq[k][3::4] = _seq[k][3::4].view(np.uint16) >> 1 | (_unblanking[k] << 15)

            # Count the total amount of samples (for one channel) to keep track of the phase
            self.sample_count += n_samples

        self.log.debug(
            "Unrolled sequence; Total sample points: %s; Total block events: %s", self.sample_count, len(blocks)
        )

        return UnrolledSequence(
            seq=_seq,
            adc_gate=_adc,
            rf_unblanking=_unblanking,
            sample_count=self.sample_count,
            grad_to_volt=self.grad_to_volt,
            rf_to_volt=self.rf_to_volt,
            dwell_time=self.spcm_dwell_time,
            larmor_frequency=self.larmor_freq,
            duration=self.duration()[0],
            adc_count=adc_count,
        )
