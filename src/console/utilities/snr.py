import numpy as np


# def snr(signal: np.ndarray) -> float:
#     # Calculate noise by complex standard deviation of the overall signal
#     noise = np.std(signal)

#     # Calculte signal by thresholding
#     signal_win = signal[np.abs(signal) > 0.1 * np.max(np.abs(signal))]
#     peak = np.max(signal_win)

#     return peak / noise

def snr(signal: np.ndarray) -> float:
    # Calculate noise by complex standard deviation of the overall signal
    # noise = np.std(signal)

    # Calculte signal by thresholding
    signal_win = signal[np.abs(signal) > 0.2 * np.max(np.abs(signal))]
    noise_win = signal[np.abs(signal) <= 0.2 * np.max(np.abs(signal))]
    
    peak = np.max(signal_win)
    noise = np.sqrt(np.mean(noise_win**2))

    return peak / noise
