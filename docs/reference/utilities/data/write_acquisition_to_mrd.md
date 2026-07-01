# Write Acquisition to MRD

`write_acquisition_to_mrd` creates an ISMRMRD dataset file (`.mrd`) from the list of `RxData` objects produced by an acquisition. It sets acquisition counters (`lin`, `sli`, `seg`, `avg`) and trajectory flags from the PyPulseq labels stored in each `RxData.labels` dictionary, enabling direct reconstruction with Gadgetron.

---

::: console.utilities.data.write_acquisition_to_mrd
