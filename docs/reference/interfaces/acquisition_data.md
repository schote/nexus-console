# Acquisition Data

`AcquisitionData` is a frozen (immutable) dataclass that encapsulates the complete result of a successful acquisition: the list of processed `RxData` objects, the acquisition parameters, the PyPulseq sequence object, session path, and extensible metadata. It is the return value of `AcquisitionControl.run()`.

## Fields

| Field | Type | Description |
|---|---|---|
| `receive_data` | `list[RxData]` | One `RxData` entry per ADC event per average, in acquisition order. |
| `acquisition_parameters` | `AcquisitionParameter` | Parameters used for this acquisition (snapshot). |
| `sequence` | `Sequence` | PyPulseq sequence object (from `SequenceProvider.to_pypulseq()`). |
| `session_path` | `str` | Base directory for data output (`~/nexus-console/<date>-session/`). |
| `meta` | `dict` | Automatically populated with version, date/time, acquisition ID, parameter snapshot, and sequence definitions. |

## Saving

`save(user_path=None, overwrite=False)` writes the acquisition to a time-stamped subdirectory:

```
<session_path>/<YYYY-MM-DD-HHmmss-SequenceName>/
├── rx_data.h5     ← HDF5: metadata + processed_data + optional raw_data per RxData
├── meta.json      ← JSON: acquisition metadata
├── sequence.seq   ← PyPulseq .seq file
└── *.npy          ← additional numpy arrays (added via add_data)
```

Processed data for each `RxData` object is stored as a complex-valued dataset under `receive_data/<index>/processed_data`. If `store_unprocessed=True` was passed to `run()`, the pre-decimation raw data is also stored.

## Adding metadata and data

```python
# Append arbitrary JSON-serialisable metadata
acq_data.add_info({
    "sample": "phantom",
    "temperature_C": 20.5,
    "operator": "D. Schote",
})

# Attach additional numpy arrays (stored as .npy files)
acq_data.add_data({"kspace_sorted": kspace_array})
acq_data.save()
```

## ISMRMRD export

`save_ismrmrd(header=None, user_path=None)` writes the acquisition in ISMRMRD (`.mrd`) format. An ISMRMRD header can be provided as an `ismrmrd.xsd.ismrmrdHeader` object, a path to an existing MRD file (the header is read from that file), or `None` (a minimal header is generated automatically). The method populates `measurementInformation`, `experimentalConditions`, and `acquisitionSystemInformation` from the acquisition metadata before writing.

---

::: console.interfaces.acquisition_data.AcquisitionData


