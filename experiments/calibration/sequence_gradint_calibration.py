"""Constructor for gradient calibration."""
import pypulseq as pp

from console.utilities.sequences.system_settings import raster, system


def constructor(fov: float = 0.24, num_samples: int = 120, ramp_duration: float = 200e-6, ro_bandwidth: float = 20e3, delay: float = 0.) -> pp.Sequence:
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "grad-calibration")

    # Make short RF pulse to get unblanking signl as trigger
    adc_duration = num_samples / ro_bandwidth

    grad_x = pp.make_trapezoid(
        channel="x",
        system=system,
        flat_area=num_samples / fov,
        rise_time=ramp_duration,
        fall_time=ramp_duration,
        flat_time=raster(adc_duration, precision=system.grad_raster_time),
    )
    
    grad_y = pp.make_trapezoid(
        channel="y",
        system=system,
        flat_area=num_samples / fov,
        rise_time=ramp_duration,
        fall_time=ramp_duration,
        flat_time=raster(adc_duration, precision=system.grad_raster_time),
    )
        
    grad_z = pp.make_trapezoid(
        channel="z",
        system=system,
        flat_area=num_samples / fov,
        rise_time=ramp_duration,
        fall_time=ramp_duration,
        flat_time=raster(adc_duration, precision=system.grad_raster_time),
    )
    
    grad_duration = pp.calc_duration(grad_x)
    
    adc = pp.make_adc(
        system=system,
        num_samples=int(grad_duration/system.adc_raster_time),
        duration=raster(val=grad_duration, precision=system.adc_raster_time),
    )
    
    seq.add_block(pp.make_delay(raster(delay, precision=system.grad_raster_time)))
    seq.add_block(grad_x, grad_y, grad_z, adc)

    return seq
