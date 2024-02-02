"""Constructor for spin-echo spectrum sequence."""
from math import pi
import pypulseq as pp

system = pp.Opts(
    grad_raster_time=1e-6,
    rf_raster_time=1e-6,
    block_duration_raster=1e-6,
    adc_raster_time=1e-6,
)


def constructor(gate_duration: float = 1e-6, rf_duration: float = 200e-6) -> pp.Sequence:
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "system-snr")
    
    if gate_duration < rf_duration:
        raise ValueError("Gate duration < RF duration")
    
    rf_delay_time = (gate_duration - rf_duration) / 2
    

    adc = pp.make_adc(
        num_samples=int(gate_duration/system.adc_raster_time),
        duration=gate_duration,
        system=system,
    )
    if rf_duration > 0:
        rf = pp.make_block_pulse(
            system=system, 
            flip_angle=pi / 2, 
            duration=rf_duration,
            delay=rf_delay_time,
        )
        seq.add_block(rf, adc)
    else:
        seq.add_block(adc)

    return seq
