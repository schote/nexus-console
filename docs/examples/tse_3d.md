# 3D Turbo Spin-Echo Imaging

This example acquires a three-dimensional image volume using a turbo spin-echo (TSE, also known as RARE or fast spin-echo) sequence. The reconstructed image is obtained by applying a 3D FFT to the sorted k-space data.

## Sequence overview

The `tse_3d.constructor` function generates a 3D TSE sequence with configurable echo train length (ETL), k-space trajectory, and phase encoding dimensions. TSE accelerates acquisition relative to a conventional spin-echo sequence by acquiring multiple k-space lines per repetition, each refocused by a successive 180° pulse. The number of refocusing pulses per TR is the echo train length (ETL); the total acquisition time is reduced by a factor of ETL compared to a single-echo protocol.

### Key sequence parameters

| Parameter | Description |
|---|---|
| `echo_time` | Effective echo time TE (s) — determines image contrast |
| `repetition_time` | Repetition time TR (s) |
| `etl` | Echo train length — number of 180° pulses per TR |
| `rf_duration` | Duration of excitation and refocusing pulses (s) |
| `gradient_correction` | Gradient moment correction factor for eddy-current compensation |
| `fov` | Field of view in the readout dimension (m) |
| `pe_steps` | Number of phase encoding steps in PE1 and PE2 dimensions |
| `trajectory` | k-space trajectory: `"in-out"`, `"out-in"`, or `"linear"` |
| `num_dummies` | Number of dummy TRs to reach steady-state magnetisation |
| `system` | PyPulseq `Opts` system limits |

The constructor returns a tuple `(sequence, header)`, where `header` is an ISMRMRD XML header pre-populated with encoding information.

### k-Space trajectory

The default **in-out** trajectory acquires the centre of k-space near the middle of the echo train, where signal intensity is highest and T2 decay is minimal. This minimises blurring artefacts compared to a linear trajectory. Sequence labels (`lin`, `sli`, `seg`) are embedded in the PyPulseq `label` block events and used by `sort_kspace` to reorder the acquired data into the correct k-space position.

## Step-by-step breakdown

1. **Instantiate `AcquisitionControl`** with the device configuration.
2. **Construct the 3D TSE sequence** with the desired imaging parameters. The constructor returns both the sequence and an ISMRMRD header.
3. **Update the decimation rate** in the global acquisition parameter to match the desired readout resolution.
4. **Unroll and execute** — sequence calculation may take several seconds for long sequences.
5. **Extract and sort k-space** — the raw `processed_data` is in acquisition order. The `sort_kspace` function reads the PyPulseq labels from each `RxData` object and places each readout at its correct `(lin, sli)` position in a pre-allocated k-space array.
6. **Reconstruct** — apply a 3D FFT (`np.fft.fftn` with fftshift) to the sorted k-space array.
7. **Visualise** — plot all slices along the PE2 dimension.
8. **Save** — append the sorted k-space and reconstructed image to the acquisition data and export to HDF5. Optionally export to ISMRMRD for Gadgetron reconstruction.

## Example script

```python title="examples/tse_3d.py"
--8<-- "examples/tse_3d.py"
```

## Resolution and contrast

With the default parameters (FoV = 100 mm, pe_steps = 32 × 8, ETL = 7), the nominal isotropic resolution is approximately 3 × 3 × 6 mm. The TE/TR ratio of 14/600 ms yields proton-density weighting at 50 mT. Adjusting TE towards longer values increases T2 weighting.

## ISMRMRD export

The sequence constructor returns a pre-populated ISMRMRD header. Passing this header to `save_ismrmrd` exports the acquisition in a format compatible with the Gadgetron reconstruction framework:

```python
mrd_path = acq_data.save_ismrmrd(header=header)
```
