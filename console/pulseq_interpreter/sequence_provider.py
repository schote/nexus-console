"""Sequence provider class."""

import numpy as np
from console.pulseq_interpreter.interface_unrolled_sequence import \
    UnrolledSequence
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample


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
        # larmor_frequency: float = 2e6,
        spcm_dwell_time: float = 1 / 20e6,
        rf_double_precision: bool = True,
        grad_to_volt: float = 1,
        rf_to_volt: float = 1,
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
        
        self._max_amp_per_channel: list[int, int, int, int] | None = None
    
    @property
    def max_amp_per_channel(self) -> list[int, int, int, int] | None:
        return self._max_amp_per_channel

    @max_amp_per_channel.setter
    def max_amp_per_channel(self, amplitudes: list[int, int, int, int]) -> None:
        if not len(amplitudes) == 4:
            raise AttributeError(f"Only {len(amplitudes)} amplitude values are given but 4 are required.")
        self._max_amp_per_channel = amplitudes

    def precalculate_carrier(self) -> None:
        """Pre-calculation of carrier signal.

        Calculation is done for the longest occurring RF event
        Each RF event then reuses the pre-calculated carrier signal.
        Dependent on the specific RF event it might be truncated and modulated.
        """
        rf_durations = []
        for k in self.block_events.keys():
            if (block := self.get_block(k)).rf:
                rf_durations.append(block.rf.shape_dur)

        if len(rf_durations) > 0:
            rf_dur_max = max(rf_durations)
            self.carrier_time = np.arange(start=0, stop=rf_dur_max, step=self.spcm_dwell_time, dtype=self.dtype)
            self.carrier = np.exp(2j * np.pi * self.larmor_freq * self.carrier_time)

    def calculate_rf(self, rf_block, unblanking: np.ndarray, num_total_samples: int) -> np.ndarray:
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

        # TODO: Take into account the phase starting point depending on the end-time of the last RF (!)

        # Calculate zero filling for RF delay
        num_samples_delay = int(rf_block.delay / self.spcm_dwell_time)
        delay = np.zeros(num_samples_delay, dtype=self.dtype)
        
        # Zero filling for RF ringdown (maximum of ringdown time defined in RF event and system)
        ringdown_dur = max(self.system.rf_ringdown_time, rf_block.ringdown_time)
        num_samgles_ringdown = int(ringdown_dur / self.spcm_dwell_time)
        ringdown_time = np.zeros(num_samgles_ringdown, dtype=self.dtype)
        
        # Zero filling for ADC dead-time (maximum of dead time defined in RF event and system)
        dead_dur = max(self.system.rf_dead_time, rf_block.dead_time)
        num_samples_dead = int(dead_dur / self.spcm_dwell_time)
        dead_time = np.zeros(num_samples_dead, dtype=self.dtype)
        
        # Calculate the number of shape sample points
        num_samples = int(rf_block.shape_dur / self.spcm_dwell_time)
        
        # Set unblanking signal
        unblanking[:num_samples_delay + num_samples] = 1

        # Calculate the static phase offset, defined in RF pulse
        phase_offset = np.exp(1j * rf_block.phase_offset)

        # Resampling of complex envelope
        envelope = resample(rf_block.signal, num=num_samples)

        # Calcuate modulated RF signal with precalculated carrier and phase offset
        # >> Precalculating the exponential function saves about 200ms for TSE sequence
        # signal = (envelope * self.carrier[:num_samples] * phase_offset).real

        # Update: Only precalculate carrier time array, calculate carriere here to take into account the
        # frequency offset of an RF block event
        carrier = np.exp(2j * np.pi * (self.larmor_freq + rf_block.freq_offset) * self.carrier_time[:num_samples])
        signal = (envelope * carrier * phase_offset).real

        # Combine signal from delays and rf
        rf_pulse = np.concatenate((delay, signal, ringdown_time, dead_time))

        if (num_signal_samples := len(rf_pulse)) < num_total_samples:
            # Zero-fill rf signal
            rf_pulse = np.concatenate((rf_pulse, np.zeros(num_total_samples - num_signal_samples, dtype=self.dtype)))
        elif num_signal_samples > num_total_samples:
            raise ArithmeticError("Number of signal samples exceeded the total number of block samples.")

        return rf_pulse * self.rf_to_volt

    def calculate_gradient(self, block, num_total_samples: int, amp_offset: float = 0.0) -> np.ndarray:
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
        delay = np.full(int(block.delay / self.spcm_dwell_time), fill_value=amp_offset, dtype=float)

        if block.type == "grad":
            # Arbitrary gradient waveform, interpolate linearly
            waveform = np.interp(
                x=np.linspace(block.tt[0], block.tt[-1], int(block.shape_dur / self.spcm_dwell_time)),
                xp=block.tt,
                fp=block.waveform + amp_offset,
            )
            # gradient = delay + list(waveform)
            gradient = np.concatenate((delay, waveform))

        elif block.type == "trap":
            # Trapezoidal gradient, combine resampled rise, flat and fall sections
            rise = np.linspace(amp_offset, amp_offset + block.amplitude, int(block.rise_time / self.spcm_dwell_time))
            flat = np.full(int(block.flat_time / self.spcm_dwell_time), fill_value=block.amplitude + amp_offset)
            fall = np.linspace(amp_offset + block.amplitude, amp_offset, int(block.fall_time / self.spcm_dwell_time))
            gradient = np.concatenate((delay, rise, flat, fall))

        else:
            raise AttributeError("Block is not a valid gradient block")

        # TODO: Is this a valid assumption? Gradients are zero-filled at the end?
        if (num_gradient_samples := len(gradient)) < num_total_samples:
            # gradient += [gradient[-1]] * (num_total_samples-num_gradient_samples)
            np.concatenate((gradient, np.full(num_total_samples - num_gradient_samples, fill_value=gradient[-1])))
        elif num_gradient_samples > num_total_samples:
            raise ArithmeticError("Number of gradient samples exceeded the total number of block samples.")

        return gradient * self.grad_to_volt

    def add_adc_gate(self, block, gate: np.ndarray) -> None:
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
        gate[delay : delay + adc_len] = 1

    def unroll_sequence(self, return_as_int16: bool = False) -> UnrolledSequence:
        """Unroll a pypulseq sequence object.

        Returns
        -------
            Instance of `UnrolledSequence` which contains a list of numpy arrays containing the block-wise \
                calculated sample points in correct spectrum card order.
                
            The unrolled sequence may already be returned as int16 values. In this case it contains the digital signals \
                for the adc gate signal and the unblanking. 
                
            Independent of the returned sequence datatype, the adc and unblanking signals are returned as list of numpy arrays \
                in the unrolled sequence instance. 
                
            Overall the `UnrolledSequence` instance gathers the following attributes:
                seq: np.ndarray
                adc_gate: np.ndarray
                rf_blanking: np.ndarray
                is_int16: bool
                sample_count: int
                grad_to_volt: float
                rf_to_volt: float
                sample_rate: float
                larmor_frequency: float

        Raises
        ------
        AttributeError
            No sequence loaded
            
        AttributeError
            Error converting sequence to int16: Maximum values per channel not set...
            
        Examples
        ---------
        
        For channels ch0, ch1, ch2, ch3, data values n = 0, 1, ..., N are ordered the following way.

            >>> data = [ch0_0, ch1_0, ch2_0, ch3_0, ch0_1, ch1_1, ..., ch0_n, ..., ch3_N]
            
            Per channel data can be extracted by the following code.
            
            >>> rf = seq[0::4]
            >>> gx = seq[1::4]
            >>> gy = seq[2::4]
            >>> gz = seq[3::4]
            
            If `return_as_int16` flag was set, channel `gx` contains the digital adc gate signal and 
            `gy` the digital unblanking signal. The following example shows, how to extract the digital signals.
            
            >>> adc = 
            >>> unblanking = 
        
        """
        print("Unrolling sequnce...")

        if len(self.block_events) == 0:
            raise AttributeError("No sequence loaded.")
        
        # Raise error if sequence values are to be returned as int16 but no channel max. values are given
        if return_as_int16 and self._max_amp_per_channel is None:
            raise AttributeError("Error converting sequence to int16: Maximum values per channel not set...")

        # Pre-calculate the carrier signal to save computation time
        self.precalculate_carrier()

        # Get all blocks in a list and pre-calculate number of sample points per block
        # to allocate empty sequence array.
        blocks = [self.get_block(k) for k in list(self.block_events.keys())]
        samples_per_block = [int(block.block_duration / self.spcm_dwell_time) for block in blocks]
        _seq = [np.empty(4 * n) for n in samples_per_block]  # empty list of list, 4 channels => 4 times n_samples
        _adc = [np.zeros(n) for n in samples_per_block]
        _unblanking = [np.zeros(n) for n in samples_per_block]

        # Last value of last block is added per channel to the gradient waveform as an offset value.
        # This is needed, since gradients must not be zero at the end of a block.
        gx_const = 0
        gy_const = 0
        gz_const = 0

        # Count the total number of sample points
        sample_count = 0

        # for k, (n_samples, block) in tqdm(enumerate(zip(samples_per_block, blocks))):
        for k, (n_samples, block) in enumerate(zip(samples_per_block, blocks)):
            
            sample_count += n_samples

            # Calculate rf events of current block, zero-fill channels if not defined
            if block.rf:
                rf_tmp = self.calculate_rf(rf_block=block.rf, unblanking=_unblanking[k], num_total_samples=n_samples)
            else:
                rf_tmp = np.zeros(n_samples)

            # TODO: Remember the phase of the last RF signal sample
            # => defines starting point for next RF event by adding a phase offset

            # Calculate gradient events of the current block, zero-fill channels if not defined
            gx_tmp = self.calculate_gradient(block.gx, n_samples, gx_const) if block.gx else np.zeros(n_samples)
            gy_tmp = self.calculate_gradient(block.gy, n_samples, gy_const) if block.gy else np.zeros(n_samples)
            gz_tmp = self.calculate_gradient(block.gz, n_samples, gz_const) if block.gz else np.zeros(n_samples)

            if block.adc:
                self.add_adc_gate(block.adc, _adc[k])

            if return_as_int16:
                # Convert RF to int16
                if np.max(x := rf_tmp / self._max_amp_per_channel[0]) > 1:
                    raise ValueError(f"RF exceeds max. amplitude value configured for channel 0.")
                rf_tmp = (x * np.iinfo(np.int16).max).astype(np.int16)
                
                # Convert x gradient to int16
                if np.max(x := gx_tmp / self._max_amp_per_channel[1]) > 1:
                    raise ValueError(f"Gx exceeds max. amplitude value configured for channel 1.")
                gx_tmp = (x * np.iinfo(np.int16).max).astype(np.int16)
                # Add adc to gx_tmp
                gx_tmp = gx_tmp >> 1 | ((-(2**15)) * _adc[k]).astype(np.int16)
                
                # Convert y gradient to int16
                if np.max(x := gy_tmp / self._max_amp_per_channel[2]) > 1:
                    raise ValueError(f"Gy exceeds max. amplitude value configured for channel 2.")
                gy_tmp = (x * np.iinfo(np.int16).max).astype(np.int16)
                # Add unblanking to gy_tmp
                gy_tmp = gy_tmp >> 1 | ((-(2**15)) * _unblanking[k]).astype(np.int16)
                
                # Convert z gradient to int16
                if np.max(x := gz_tmp / self._max_amp_per_channel[3]) > 1:
                    raise ValueError(f"Gz exceeds max. amplitude value configured for channel 3.")
                gz_tmp = (x * np.iinfo(np.int16).max).astype(np.int16)

                # TODO: Use 15th bit of gz_tmp to store the clock? (simple sequence of 0, 1, 0, 1, ...)
                
            else:
                raise Warning("Sequence data points were unrolled to floats, \
                    but int16 values are required to replay sequence.")

            _seq[k] = np.stack((rf_tmp, gx_tmp, gy_tmp, gz_tmp)).flatten(order="F")

        return UnrolledSequence(
            seq=_seq,
            adc_gate=_adc,
            rf_unblanking=_unblanking,
            is_int16=return_as_int16,
            sample_count=sample_count,
            grad_to_volt=self.grad_to_volt,
            rf_to_volt=self.rf_to_volt,
            dwell_time=self.spcm_dwell_time,
            larmor_frequency=self.larmor_freq
        )
