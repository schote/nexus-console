# %%
import numpy as np
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample
from tqdm.auto import tqdm

# Constants
PI2 = np.pi * 2


class SequenceProvider(Sequence):
    """Sequence provider class, inherited from pulseq sequence object."""
    
    def __init__(self, system: Opts = Opts(), larmor_frequency: float = 2e6, spcm_sample_rate: float = 1 / 20e6):
        """Init function for sequence provider class."""
        super().__init__(system=system)
        
        self.spcm_freq = 1 / spcm_sample_rate
        self.spcm_sample_rate = spcm_sample_rate
        self.f0 = larmor_frequency
        
        self.carrier: np.ndarray | None = None
        
    def precalculate_carrier(self) -> None:
        """Pre-calculation of carrier signal for the longest occurring RF event.
        Each RF event reuses the pre-calculated signal.
        Dependent on the specific RF event it might be truncated and modulated.
        """
        rf_durations = []
        for k in self.block_events.keys():
            if (b := self.get_block(k)).rf:
                rf_durations.append(b.rf.shape_dur)
        rf_dur_max = max(rf_durations)
        t = np.arange(start=0, stop=rf_dur_max, step=self.spcm_sample_rate)
        self.carrier = np.exp(1j * PI2 * self.f0 * t)

    def calculate_rf(self, rf_block, num_total_samples: int) -> list[float]:
        """Calculates RF sample points to be played by TX card.

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
        
        if self.carrier is None:
            raise RuntimeError("Missing precalculated carrier signal.")
        
        # TODO: Unused argument: frequency offset (?) -> requires recalculation of carrier signal
        # TODO: Take into account the phase starting point depending on the end-time of the last RF
        
        # Calculate zero filling for RF delay
        delay = [0.] * int(rf_block.delay / self.spcm_sample_rate)
        # Zero filling for RF ringdown (maximum of ringdown time defined in RF event and system)
        ringdown_time = [0.] * int(max(self.system.rf_ringdown_time, rf_block.ringdown_time) / self.spcm_sample_rate)
        # Zero filling for ADC dead-time (maximum of dead time defined in RF event and system)
        dead_time = [0.] * int(max(self.system.rf_dead_time, rf_block.dead_time) / self.spcm_sample_rate)
       
        # Calculate the number of shape sample points
        num_samples = int(rf_block.shape_dur / self.spcm_sample_rate)
        
        # Calculate the static phase offset, defined in RF pulse
        phase_offset = 1    # np.exp(1j * rf_block.phase_offset)
        
        # Resampling of complex envelope
        envelope = resample(rf_block.signal, num=num_samples)
        
        # Calcuate modulated RF signal with precalculated carrier and phase offset
        signal = (envelope * self.carrier[:num_samples] * phase_offset).real

        # Combine signal from delays and rf
        rf = delay + list(signal) + ringdown_time + dead_time
        
        # Zero-fill rf signal
        if (num_signal_samples := len(rf)) < num_total_samples:
            rf += [0.] * (num_total_samples-num_signal_samples)
        elif num_signal_samples > num_total_samples:
            raise ArithmeticError("Number of signal samples exceeded the total number of block samples.")

        return rf


    def calculate_gradient(self, block, num_total_samples: int, amp_offset: float = 0.) -> list[float]:
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
        delay = [amp_offset] * int(block.delay/self.spcm_sample_rate)
        
        if block.type == "grad":
            # Arbitrary gradient waveform, interpolate linearly
            waveform = np.interp(
                x=np.linspace(block.tt[0], block.tt[-1], int(block.shape_dur / self.spcm_sample_rate)),
                xp=block.tt,
                fp=block.waveform+amp_offset
            )
            gradient = delay + list(waveform)
            
        elif block.type == "trap":
            # Trapezoidal gradient, combine resampled rise, flat and fall sections
            rise = np.linspace(0, block.amplitude, int(block.rise_time / self.spcm_sample_rate))
            rise += amp_offset
            flat = [block.amplitude+amp_offset] * int(block.flat_time / self.spcm_sample_rate)
            fall = np.linspace(block.amplitude, 0, int(block.fall_time / self.spcm_sample_rate))
            fall += amp_offset
            gradient = delay + list(rise) + flat + list(fall)
            
        else:
            raise AttributeError("Block is not a valid gradient block")
        
        # TODO: Is this a valid assumption? Gradients are zero-filled at the end?
        if (num_gradient_samples := len(gradient)) < num_total_samples:
            gradient += [gradient[-1]] * (num_total_samples-num_gradient_samples)
        elif num_gradient_samples > num_total_samples:
            raise ArithmeticError("Number of gradient samples exceeded the total number of block samples.")

        return gradient

    def unroll_sequence(self):
        """Unroll a read sequence object.

        Returns
        -------
            List of lists, block-wise calculated sample points in correct order for spectrum card
            and total number of sequence sample points

        Raises
        ------
        AttributeError
            No sequence loaded
        """
        print("Unrolling sequnce...")
        if len(self.block_events) == 0:
            raise AttributeError("No sequence loaded.")

        # Pre-calculate the carrier signal to save computation time
        self.precalculate_carrier()
        _seq = []   # list of list
        
        # Last value of last block is added per channel to the gradient waveform as an offset value.
        # This is needed, since gradients must not be zero at the end of a block.
        gx_const = 0
        gy_const = 0
        gz_const = 0
        
        # Count the total number of sample points
        total_samples = 0

        for k in tqdm(list(self.block_events.keys())):
            
            block = self.get_block(k)
            n_samples = int(block.block_duration / self.spcm_sample_rate)
            total_samples += n_samples
            
            # Calculate rf events of current block, zero-fill channels if not defined
            rf_tmp = self.calculate_rf(block.rf, n_samples) if block.rf else [0.]*n_samples
            # TODO: Remember the phase of the last RF signal sample 
            # => defines starting point for next RF event by adding a phase offset
            
            # Calculate gradient events of the current block, zero-fill channels if not defined
            gx_tmp = self.calculate_gradient(block.gx, n_samples, gx_const) if block.gx else [0.]*n_samples
            gy_tmp = self.calculate_gradient(block.gy, n_samples, gy_const) if block.gy else [0.]*n_samples
            gz_tmp = self.calculate_gradient(block.gz, n_samples, gz_const) if block.gz else [0.]*n_samples
            
            # The new last gradient values are updated here.
            gx_const = gx_tmp[-1]
            gy_const = gy_tmp[-1]
            gz_const = gz_tmp[-1]

            # Append correctly ordered list to sequence 
            _seq += list(np.array([rf_tmp, gx_tmp, gy_tmp, gz_tmp]).flatten(order="F"))

        return _seq, total_samples
