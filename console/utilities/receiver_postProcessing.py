
from dataclasses import dataclass
import numpy as np

@dataclass
class ReceiverPostProcessing:
    
    name: str

 
def wind(data: float):
    np.pi = 4.0 * np.arctan(1.0)
    if abs(data) <= 1.0:
        if abs(data) != 0.0:
            wind = np.exp(-1.0 / (1.0 - data*data)) * np.sin(2.073 * np.pi * data) / data
        else:
            wind = np.exp(-1.0 / (1.0 - data*data)) * 2.073 * np.pi
    else:
        wind = 0.0
    return wind