"""Implementation of function to save unprocessed data as numpy array."""
# %%
import os
import sys

import numpy as np

# %%
# Load raw data
brain_phantom = "/Users/davidschote/Projects/data/2023-11-01-session/2023-11-01-103607-2d_tse_v1/"


def unprocessed_to_array(acquisition_path: str, max_rx_amplitude: float = 200):
    """Read unprocessed raw data to numpy array.

    Unprocessed array is saved has an object as it conains acquisition data with variable sizes.

    Parameters
    ----------
    acquisition_path
        Path to unprocessed acquisition data.
    max_rx_amplitude, optional
        Maximum receive amplitude, required for correct scaling, by default 200
    """
    acquisition_path = os.path.join(acquisition_path, "")

    print("Loading numpy object...")
    unprocessed = np.load(f"{acquisition_path}unprocessed_data.npy", allow_pickle=True)

    # Object to numpy array
    print("Analysing dimensions of unprocessed data...")

    rx_scaling = np.iinfo(np.int16).max * max_rx_amplitude
    num_averages: int = len(unprocessed)
    num_gates: int = len(unprocessed[0])

    # Extract the length of all gates
    rx_data_size = []
    for average in unprocessed:
        for gate in average:
            rx_data_size.append(len(gate[0]))

    print("Smallest number of readout samples: ", min(rx_data_size))
    print("Largest number of readout samples: ", max(rx_data_size))

    # Extract data and write to array
    data_array = np.empty((num_averages, 2, num_gates, min(rx_data_size)))

    print(f"Extracting {min(rx_data_size)} sample points per readout...")
    for avg_index, avg_data in enumerate(unprocessed):
        for gate_index, gate_data in enumerate(avg_data):
            ref = (np.array(gate_data[0]).astype(np.uint16) >> 15).astype(float)
            raw = (np.array(gate_data[0]) << 1).astype(np.int16) * rx_scaling

            data_array[avg_index, 0, gate_index, :] = ref[: min(rx_data_size)]
            data_array[avg_index, 1, gate_index, :] = raw[: min(rx_data_size)]

    print(
        "Arranged unprocessed data in array [Averages, ref/raw data, phase encoding, readout]:\n",
        data_array.shape,
    )

    file_name = "unprocessed_data_array.npy"
    print("Writing array to numpy file...")
    np.save(acquisition_path + file_name, data_array)
    print("Done.")
    print("File path:\n", acquisition_path + file_name)


# %%
if __name__ == "__main__":
    if not len(sys.argv) > 1:
        print("Not enough arguments: Path to acquisition folder (required), max. RX amplitude (optional)")

    acq_path = sys.argv[1]

    if len(sys.argv) > 2:
        max_amp = sys.argv[2]
        unprocessed_to_array(acquisition_path=acq_path, max_rx_amplitude=max_amp)
    else:
        unprocessed_to_array(acquisition_path=acq_path)
