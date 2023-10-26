import numpy as np
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter

def tx_fit(self, x, a, b, c):
    return abs(a * np.sin(b * x) + c)

def tx_adjust(x: np.ndarray, flip_angles: np.ndarray, acq_params: AcquisitionParameter) -> np.ndarray:
    
    if not len(x.shape) == 4:
        raise ValueError("Invalid input data shape") 
    
    # Reduce average and coil dimension
    x = x[0, 0, ...]
    
    x = np.abs(np.fft.fftshift(np.fft.fft(x, norm="ortho")))
    
    # Truncate spectrum center to 100 pixels:
    n_samples = 100
    window_start = int(x.shape[-1] / 2 - n_samples / 2)
    x = x[..., window_start : window_start + n_samples]
    amplitudes = np.max(x, axis=-1)
    
    init = [np.max(amplitudes), 0.05, np.min(amplitudes)]
    
    # Fit parameters
    params, params_cov = curve_fit(tx_fit, flip_angles, amplitudes, init, method='lm')
    
    flip_angle_fit = np.arange(flip_angles[0], flip_angles[-1] + 0.1, 0.1)
    amplitudes_fit = tx_fit(x, params[0], params[1], params[2])
    
    return np.stack([flip_angle_fit, amplitudes_fit], axis=0)