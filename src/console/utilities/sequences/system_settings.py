"""Global definition of system settings to be imported by sequence constructors."""

from pypulseq.opts import Opts

system = Opts(
    # time delay at the end of RF event, SETS RF DELAY!
    rf_dead_time=20e-6,

    # Set raster times to spectrum card frequency (timing checks)
    grad_raster_time=1e-6,
    rf_raster_time=1e-6,
    block_duration_raster=1e-6,
    adc_raster_time=1e-6,

    # Time delay at the beginning of an RF event
    rf_ringdown_time=2e-3,
    # Time delay at the beginning of ADC event
    # adc_dead_time=200e-6,

    # Set maximum slew rate
    max_slew=50,
    slew_unit="T/m/s",

    B0=50e-3,
    gamma=42.576e6
)


# Helper function
def raster(val: float, precision: float) -> float:
    """Fit value to gradient raster.

    Parameters
    ----------
    val
        Time value to be aligned on the raster.
    precision
        Raster precision, e.g. system.grad_raster_time or system.adc_raster_time

    Returns
    -------
        Value wih given time/raster precision
    """
    # return np.round(val / precision) * precision
    gridded_val = round(val / precision) * precision
    return gridded_val
    # decimals = abs(Decimal(str(precision)).as_tuple().exponent)
    # return round(gridded_val, ndigits=decimals)
