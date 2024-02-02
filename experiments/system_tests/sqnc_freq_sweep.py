"""Constructor for spin-echo spectrum sequence."""
from math import pi
import numpy as np
import pypulseq as pp

system = pp.Opts(
    grad_raster_time=1e-6,
    rf_raster_time=1e-6,
    block_duration_raster=1e-6,
    adc_raster_time=1e-6,
)


def constructor(span: float = 2e6, num_freqs: int = 50, gate_duration: float = 400e-6) -> pp.Sequence:
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "freq-sweep")

    freq = np.linspace(start=-span/2, stop=span/2, num=num_freqs)
    
    for f in freq:

        rf = pp.make_block_pulse(
            system=system, 
            flip_angle=pi / 2, 
            duration=gate_duration,
            freq_offset=f
        )
        adc = pp.make_adc(
            num_samples=int(gate_duration/system.adc_raster_time),
            duration=gate_duration,
            system=system,
        )
        seq.add_block(rf, adc)

        if f != freq[-1]:
            seq.add_block(pp.make_delay(gate_duration))

    return seq, freq
