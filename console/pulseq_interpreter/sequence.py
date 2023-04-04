# %%
import os
import numpy as np
import samplerate

from pypulseq.Sequence.sequence import Sequence
from pypulseq.opts import Opts


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

class SequenceWrapper(Sequence):
    def __init__(self, system: Opts):
        super().__init__(system=system)
        
    def get_block_1(self):
        return self.get_block(1)
    
    def get_modulated_rf_block(self, block_index: int, f0: float = 2.045e6):
        
        block = self.get_block(block_index)
        
        if not hasattr(block, 'rf'):
            raise AttributeError("Block is not an RF block")
        
        data = block.rf.signal
        freq = (f0 + block.rf.freq_offset) * 2
        # phase_offset = block.rf.phase_offset
        duration = (block.block_duration - block.rf.delay) # duration in s
        
        # Resample signal
        dt = duration / len(data)
        ratio = freq/(1/dt)
        converter = 'sinc_best'  # or 'sinc_fastest', ...
        data_resampled = samplerate.resample(data, ratio, converter)
        
        # Modulate signal
        t = np.linspace(start=0, stop=1, endpoint=True, num=len(data_resampled))
        data_modulated = data_resampled * np.sin(2*np.pi*freq*t)
        
        return data_modulated, t*duration*1e6
        