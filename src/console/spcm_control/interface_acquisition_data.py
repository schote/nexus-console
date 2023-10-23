"""Interface class for acquisition parameters."""
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter
from dataclasses import dataclass
from console.pulseq_interpreter.sequence_provider import SequenceProvider, Sequence
import json
import numpy as np
import os
from datetime import datetime, timezone


@dataclass(slots=True, frozen=True)
class AcquisitionData:
    """Parameters which define an acquisition."""

    raw: np.ndarray
    """Demodulated, down-sampled and filtered complex-valued raw MRI data."""
    
    signal: np.ndarray | None = None
    """Unprocessed real-valued signal data without demodulation, sampled at RX card sample-rate."""
    
    reference: np.ndarray | None = None
    """Reference signal generated during ADC gate window to compensate phase."""
    
    acquisition_parameters: AcquisitionParameter
    """Acquisition parameters."""
    
    sequence: SequenceProvider | Sequence
    """Sequence object used for the acquisition acquisition."""
    
    dwell_time: float
    """Dwell time of down-sampled raw data in seconds."""
    
    def __post_init__(self) -> None:
        """Post init method to create meta data object."""
        self.meta = {
            "date_time": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
            "raw_data_shape": self.raw.shape,
            "sig_data_shape": self.sig.shape if self.sig is not None else False,
            "ref_data_shape": self.ref.shape if self.ref is not None else False,
        }
    
    
    def save_data(self, data_path: str) -> None:
        """Save all the acquisition data to a given data path.

        Parameters
        ----------
        data_path
            Directory the acquisition data is written to.
            This path is unique for each acquisition.
        """
        # Add trailing slash and make dir
        data_path = os.path.join(data_path, "")
        os.makedirs(data_path, exist_ok=True)
        
        # Save acquisition parameters
        with open(f"{data_path}acquisition_parameter.json", "w") as fp:
            json.dump(self.acquisition_parameters, fp=fp)
            
        # Save meta data
        with open(f"{data_path}meta.json", "w") as fp:
            json.dump(self.meta, fp=fp)
        
        # Write sequence .seq file
        self.sequence.write(f"{data_path}sequence.seq")
        
        # Save raw data as numpy array
        np.save(f"{data_path}raw_data.npy", self.raw)
        
        if self.sig is not None:
            # Save raw data as numpy array
            np.save(f"{data_path}signal_data.npy", self.signal)
            
        if self.ref is not None:
            # Save raw data as numpy array
            np.save(f"{data_path}reference_signal.npy", self.reference)
