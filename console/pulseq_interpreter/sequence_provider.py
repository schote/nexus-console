"""Sequence provider class."""
import warnings
from types import SimpleNamespace

import numpy as np
from line_profiler import profile
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence


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
        rf_double_precision: bool = True,
        grad_to_volt: float = 1,
        rf_to_volt: float = 1,
        max_amp_per_channel: list[int] | None = None,
        system: Opts = Opts(),
    ):
        """Init function for sequence provider class."""
        super().__init__(system=system)

        self.grad_to_volt = grad_to_volt
        self.rf_to_volt = rf_to_volt

        self.spcm_freq = 1 / spcm_dwell_time
        self.spcm_dwell_time = spcm_dwell_time
        self.larmor_freq = self.system.B0 * self.system.gamma

        self.dtype = np.double if rf_double_precision else np.single

        self.carrier_time: np.ndarray | None = None
        self.carrier: np.ndarray | None = None

        if not max_amp_per_channel:
            self._amp_per_ch = [1000, 1000, 1000, 1000]
            warnings.warn(
                "Maximum amplitudes per channel not provided. \
                Default value for maximum amplitude set to 1000 mV per channel."
            )
        else:
            self._amp_per_ch = max_amp_per_channel

        self.int16_max = np.iinfo(np.int16).max

    @property
    def max_amp_per_channel(self) -> list[int]:
        """Property getter.

        Maximum amplitude per channel in mV

        Returns
        -------
            List of amplitude values in mV
        """
        return self._amp_per_ch

    @max_amp_per_channel.setter
    def max_amp_per_channel(self, amplitudes: list[int]) -> None:
        """Property setter.

        Maximum amplitude per channel in mV

        Parameters
        ----------
        amplitudes
            List of integer amplitude values in mV

        Raises
        ------
        AttributeError
            Raises error if less or more then 4 amplitude values are provided
        """
        if not len(amplitudes) == 4:
            raise AttributeError(f"Only {len(amplitudes)} amplitude values are given but 4 are required.")
        self._amp_per_ch = amplitudes

    def precalculate_carrier(self) -> None:
        """Pre-calculation of carrier signal.

        Calculation is done for the longest occurring RF event
        Each RF event then reuses the pre-calculated carrier signal.
        Dependent on the specific RF event it might be truncated and modulated.
        """
        rf_durations = []
        for block_id in self.block_events.keys():
            if (block := self.get_block(block_id)).rf:
                rf_durations.append(block.rf.shape_dur)

        if len(rf_durations) > 0:
            rf_dur_max = max(rf_durations)
            self.carrier_time = np.arange(start=0, stop=rf_dur_max, step=self.spcm_dwell_time, dtype=self.dtype)
            self.carrier = np.exp(2j * np.pi * self.larmor_freq * self.carrier_time)

    # @profile
    def calculate_rf(self, rf_block: SimpleNamespace, unblanking: np.ndarray, num_total_samples: int) -> np.ndarray:
        """Calculate RF sample points to be played by TX card.

        Parameters
        ----------
        rf_block
            Pulseq RF block

        Returns
        -------
            List of RF samples

        Raises
        ------
        AttributeError
            Invalid RF block
        """
        if not rf_block.type == "rf":
            raise AttributeError("Block is not a valid RF block.")

        if self.carrier_time is None:
            raise RuntimeError("Missing precalculated carrier time raster.")

        # > Take into account the phase starting point depending on the end-time of the last RF?
        # This is done by the sequence programmer, by adding a frequency/phase offset to an RF pulse

        # Calculate zero filling for RF delay
        num_samples_delay = int(rf_block.delay / self.spcm_dwell_time)
        delay = np.zeros(num_samples_delay, dtype=np.int16)

        # Zero filling for RF dead-time (maximum of dead time defined in RF event and system)
        # Time between start of unblanking and start of RF
        dead_dur = max(self.system.rf_dead_time, rf_block.dead_time)
        num_samples_dead = int(dead_dur / self.spcm_dwell_time)
        dead_time = np.zeros(num_samples_dead, dtype=np.int16)

        # Zero filling for RF ringdown (maximum of ringdown time defined in RF event and system)
        ringdown_dur = max(self.system.rf_ringdown_time, rf_block.ringdown_time)
        num_samgles_ringdown = int(ringdown_dur / self.spcm_dwell_time)
        ringdown_time = np.zeros(num_samgles_ringdown, dtype=np.int16)

        # Calculate the number of shape sample points
        num_samples = int(rf_block.shape_dur / self.spcm_dwell_time)

        # Set unblanking signal
        # The set value corresponds to 15th bit set to 1 >> 1000 0000 0000 0000
        unblanking[num_samples_delay : -(num_samgles_ringdown + 1)] = -(2**15)

        # Calculate the static phase offset, defined in RF pulse
        phase_offset = np.exp(1j * rf_block.phase_offset)

        # Calculate scaled envelope and convert to int16 scale (not datatype, since we use complex numbers)
        # Perform this step here to save computation time, num. of envelope samples << num. of resampled signal
        if np.amax(envelope_scaled := rf_block.signal * phase_offset * self.rf_to_volt / self._amp_per_ch[0]) > 1:
            raise ValueError("RF amplitude exceeded max. amplitude of channel 0.")
        envelope_scaled = envelope_scaled * self.int16_max

        # Resampling of scaled complex envelope
        envelope = resample(envelope_scaled, num=num_samples)

        # Calcuate modulated RF signal with precalculated carrier and phase offset
        # >> Precalculating the exponential function saves about 200ms for TSE sequence
        # Problem: When precalculating the carrier signal we cannot consider frequency offsets
        # signal = (envelope * self.carrier[:num_samples] * phase_offset).real

        # Only precalculate carrier time array, calculate carriere here to take into account the
        # frequency offset of an RF block event
        carrier = np.exp(2j * np.pi * (self.larmor_freq + rf_block.freq_offset) * self.carrier_time[:num_samples])
        signal = np.int16((envelope * carrier).real)

        # Combine signal from delays and rf
        rf_pulse = np.concatenate((delay, dead_time, signal, ringdown_time))

        if (num_signal_samples := len(rf_pulse)) < num_total_samples:
            # Zero-fill rf signal
            rf_pulse = np.concatenate((rf_pulse, np.zeros(num_total_samples - num_signal_samples, dtype=np.int16)))
        elif num_signal_samples > num_total_samples:
            raise ArithmeticError("Number of signal samples exceeded the total number of block samples.")

        return rf_pulse

    @profile
    def calculate_gradient(
        self, block: SimpleNamespace, num_total_samples: int, amp_offset: np.int16 = np.int16(0)
    ) -> np.ndarray:
        """Calculate spectrum-card sample points of a gradient waveform.

        Parameters
        ----------
        block
            Gradient block from sequence, type must be grad or trap
        num_total_samples
            Total number of block samples points to verify calculation
        amp_offset, optional
            Amplitude offset, last value of last gradient, by default 0.

        Returns
        -------
            List of gradient waveform values

        Raises
        ------
        AttributeError
            Block type is not grad or trap
        ArithmeticError
            Number of calculated sample points is greater then number of block sample points
        """
        # Both gradient types have a delay
        # delay = [amp_offset] * int(block.delay/self.spcm_sample_rate)
        delay = np.full(int(block.delay / self.spcm_dwell_time), fill_value=amp_offset, dtype=np.int16)

        idx = ["x", "y", "z"].index(block.channel)
        offset = amp_offset / self.int16_max

        if block.type == "grad":
            if np.amax(waveform := block.waveform * self.grad_to_volt / self._amp_per_ch[idx] + offset) > 1:
                raise ValueError(f"Amplitude of {block.channel} gradient exceeded max. amplitude of channel {idx}.")
            waveform *= self.int16_max

            # Arbitrary gradient waveform, interpolate linearly
            # This function requires float input => cast to int16 afterwards
            waveform = np.interp(
                x=np.linspace(block.tt[0], block.tt[-1], int(block.shape_dur / self.spcm_dwell_time)),
                xp=block.tt,
                fp=waveform,
            )
            gradient = np.concatenate((delay, np.int16(waveform)))

        elif block.type == "trap":
            # Check and scale trapezoid flat amplitude (including offset)
            # At this point, only a single value needs to be scaled
            if np.amax(flat_amp := block.amplitude * self.grad_to_volt / self._amp_per_ch[idx] + offset) > 1:
                raise ValueError(f"Amplitude of {block.channel} gradient exceeded max. amplitude of channel {idx}.")
            flat_amp = np.int16(flat_amp * self.int16_max)

            # Trapezoidal gradient, combine resampled rise, flat and fall sections
            rise = np.linspace(amp_offset, flat_amp, int(block.rise_time / self.spcm_dwell_time), dtype=np.int16)
            flat = np.full(int(block.flat_time / self.spcm_dwell_time), fill_value=flat_amp, dtype=np.int16)
            fall = np.linspace(flat_amp, amp_offset, int(block.fall_time / self.spcm_dwell_time), dtype=np.int16)
            gradient = np.concatenate((delay, rise, flat, fall))

        else:
            raise AttributeError("Block is not a valid gradient block")

        # TODO: Is this a valid assumption? Gradients are zero-filled at the end?
        if (num_gradient_samples := len(gradient)) < num_total_samples:
            # gradient += [gradient[-1]] * (num_total_samples-num_gradient_samples)
            np.concatenate((gradient, np.full(num_total_samples - num_gradient_samples, fill_value=gradient[-1])))
        elif num_gradient_samples > num_total_samples:
            raise ArithmeticError("Number of gradient samples exceeded the total number of block samples.")

        return gradient

    def add_adc_gate(self, block: SimpleNamespace, gate: np.ndarray) -> None:
        """Add ADC gate signal inplace to gate array.

        Parameters
        ----------
        block
            ADC event of sequence block.
        gate
            Gate array, predefined by zeros. If ADC event is present, the corresponding range is set to one.
        """
        delay = int(block.delay / self.spcm_dwell_time)
        # dead_dur = max(self.system.adc_dead_time, block.dead_time)
        # dead_time = int(dead_dur / self.spcm_sample_rate)
        adc_len = int(block.num_samples * block.dwell / self.spcm_dwell_time)
        gate[delay : delay + adc_len] = -(2**15)  # this value equals 15th bit set to 1 >> 1000 0000 0000 0000

    @profile
    def unroll_sequence(self, larmor_freq: float | None = None) -> UnrolledSequence:
        """Unroll a pypulseq sequence object.

        Returns
        -------
        UnrolledSequence
            Instance of an unrolled sequence object which contains a list of numpy arrays with
            the block-wise calculated sample points in correct spectrum card order.

            The unrolled sequence may already be returned as int16 values. In this case it contains the
            digital signals for the adc gate signal and the unblanking.

            Independent of the returned sequence datatype, the adc and unblanking signals are returned as
            list of numpy arrays in the unrolled sequence instance.

        Raises
        ------
        AttributeError
            No sequence loaded

        AttributeError
            Error converting sequence to int16: Maximum values per channel not set...

        Examples
        --------
        For channels ch0, ch1, ch2, ch3, data values n = 0, 1, ..., N are ordered the following way.

        >>> data = [ch0_0, ch1_0, ch2_0, ch3_0, ch0_1, ch1_1, ..., ch0_n, ..., ch3_N]

        Per channel data can be extracted by the following code.

        >>> rf = seq[0::4]
        >>> gx = seq[1::4]
        >>> gy = seq[2::4]
        >>> gz = seq[3::4]

        Channel `gx` contains the digital adc gate signal and `gy` the digital unblanking signal.
        The following example shows, how to extract the gradients and digital signals in this case.

        >>> gx = seq[1::4] << 1
        >>> gy = seq[2::4] << 1
        >>> adc = -1 * (seq[1::4] >> 15)
        >>> unblanking = -1 * (seq[2::4] >> 15)

        The last two lines convert the digital signal from 15th bit value to 1 or 0 respectively.
        """
        print("Unrolling sequnce...")

        if larmor_freq is not None:
            self.larmor_freq = larmor_freq

        if len(self.block_events) == 0:
            raise AttributeError("No sequence loaded.")

        if self._amp_per_ch is None:
            raise ValueError("Max. amplitudes per channel is not defined.")

        # Pre-calculate the carrier signal to save computation time
        self.precalculate_carrier()

        # Get all blocks in a list and pre-calculate number of sample points per block
        # to allocate empty sequence array.
        blocks = [self.get_block(k) for k in list(self.block_events.keys())]
        samples_per_block = [int(block.block_duration / self.spcm_dwell_time) for block in blocks]

        # Internal list of arrays to store sequence and digital signals
        _seq = [
            np.zeros(4 * n, dtype=np.int16) for n in samples_per_block
        ]  # empty list of list, 4 channels => 4 times n_samples
        _adc = [np.zeros(n, dtype=np.int16) for n in samples_per_block]
        _unblanking = [np.zeros(n, dtype=np.int16) for n in samples_per_block]

        # Last value of last block is added per channel to the gradient waveform as an offset value.
        # This is needed, since gradients must not be zero at the end of a block.
        grad_x_const = 0
        grad_y_const = 0
        grad_z_const = 0

        # Count the total number of sample points
        sample_count = 0

        # for k, (n_samples, block) in tqdm(enumerate(zip(samples_per_block, blocks))):
        for k, (n_samples, block) in enumerate(zip(samples_per_block, blocks)):
            sample_count += n_samples

            # Calculate rf events of current block, zero-fill channels if not defined
            if block.rf:
                # Every 4th value in _seq starting at index 0 belongs to RF
                _seq[k][0::4] = self.calculate_rf(
                    rf_block=block.rf, unblanking=_unblanking[k], num_total_samples=n_samples
                )

            if block.adc:
                self.add_adc_gate(block.adc, _adc[k])

            if grad_x := block.gx:
                # Every 4th value in _seq starting at index 1 belongs to x gradient
                _seq[k][1::4] = self.calculate_gradient(grad_x, n_samples, grad_x_const)
            if grad_y := block.gy:
                # Every 4th value in _seq starting at index 2 belongs to y gradient
                _seq[k][2::4] = self.calculate_gradient(grad_y, n_samples, grad_y_const)
            if grad_z := block.gz:
                # Every 4th value in _seq starting at index 3 belongs to z gradient
                _seq[k][3::4] = self.calculate_gradient(grad_z, n_samples, grad_z_const)

            # Bitwise operations to merge gx with adc and gy with unblanking
            _seq[k][1::4] = _seq[k][1::4] >> 1 | _adc[k]
            _seq[k][2::4] = _seq[k][2::4] >> 1 | _unblanking[k]

        return UnrolledSequence(
            seq=_seq,
            adc_gate=_adc,
            rf_unblanking=_unblanking,
            sample_count=sample_count,
            grad_to_volt=self.grad_to_volt,
            rf_to_volt=self.rf_to_volt,
            dwell_time=self.spcm_dwell_time,
            larmor_frequency=self.larmor_freq,
        )
