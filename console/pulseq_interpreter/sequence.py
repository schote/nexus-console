# %%
import os

import numpy as np
import samplerate
from pydantic import BaseModel
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample
from tqdm.auto import tqdm

# # %%
# # Read sequence
# seq = pp.Sequence()
# seq_path = os.path.normpath("/Users/schote01/code/spectrum-pulseq/console/pulseq_interpreter/seq/fid.seq")
# seq.read("./seq/tse_pypulseq.seq")

# # Read sequence blocks as dict
# blocks = seq.dict_block_events
# # Print specific block from sequence object
# print(seq.get_block(1))

# %%


class Channel:
    def __init__(self):
        self.time_points: np.array = np.array([])
        self.waveform: np.array = np.array([])

    def append(self, time: np.array, waveform: np.array) -> None:
        t0 = self.time_points[-1] if len(self.time_points) > 0 else 0
        self.time_points = np.append(self.time_points, time + t0)
        self.waveform = np.append(self.waveform, waveform)


class UnrolledSequence:
    def __init__(self):
        self.rf: Channel = Channel()
        self.gx: Channel = Channel()
        self.gy: Channel = Channel()
        self.gz: Channel = Channel()
        self.adc: Channel = Channel()


class SequenceProvider(Sequence):
    def __init__(self, system: Opts, raster_time: float = 1 / 4e6):
        super().__init__(system=system)

        self.spcm_freq = 1 / raster_time

    def get_unrolled_rf(self, rf_block) -> list[np.array]:
        if not rf_block.type == "rf":
            raise AttributeError("Block is not a valid RF block")

        # phase_offset = block.rf.phase_offset
        # Get current rf signal sample raster
        n_samples = int(rf_block.shape_dur * self.spcm_freq)

        # Resample real and imaginary part
        # envelope = samplerate.resample(rf_block.signal.real, ratio=freq/freq_shape, converter_type='sinc_best')
        envelope = resample(rf_block.signal.real, num=n_samples)

        # Modulate signal
        t = np.arange(n_samples) / self.spcm_freq
        data_modulated = envelope * np.sin(2 * np.pi * self.spcm_freq * t)

        # TODO: Calculate total waveform: delay -> waveform -> ringdown_time -> dead_time

        return (t, data_modulated)

    def get_unrolled_grad(self, grad_block) -> list[np.array]:
        if grad_block.type == "grad":
            n_samples = int(grad_block.shape_dur * self.spcm_freq)
            return resample(grad_block.waveform, num=n_samples, t=grad_block.tt)

        elif grad_block.type == "trap":
            total_duration = (
                grad_block.delay
                + grad_block.rise_time
                + grad_block.flat_time
                + grad_block.fall_time
            )
            n_samples = int(total_duration * self.spcm_freq)
            waveform = [0.0, 0.0, grad_block.amplitude, grad_block.amplitude, 0.0]
            time = [
                0.0,
                grad_block.delay,
                grad_block.delay + grad_block.rise_time,
                grad_block.delay + grad_block.rise_time + grad_block.flat_time,
                total_duration,
            ]
            return resample(np.array(waveform), num=n_samples, t=np.array(time))

        else:
            raise AttributeError("Block is not a valid gradient block")

    def unroll_sequence(self) -> UnrolledSequence:
        print("Unrolling sequnce...")

        _seq = UnrolledSequence()

        for k, duration in tqdm(enumerate(self.block_durations)):
            block = self.get_block(k + 1)

            if block.rf:
                t, wf = self.get_unrolled_rf(block.rf)
                _seq.rf.append(time=t, waveform=wf)
            if block.gx:
                t, wf = self.get_unrolled_grad(block.gx)
                _seq.gx.append(time=t, waveform=wf)
            if block.gy:
                t, wf = self.get_unrolled_grad(block.gy)
                _seq.gy.append(time=t, waveform=wf)
            if block.gz:
                t, wf = self.get_unrolled_grad(block.gz)
                _seq.gz.append(time=t, waveform=wf)

        return _seq
