# 3D turbo spin-echo

A three-dimensional image volume is acquired with a turbo spin-echo (TSE) sequence and reconstructed by a 3D Fourier transform. The data are additionally exported in the ISMRMRD format for reconstruction with external frameworks.

## Sequence

The constructor [`tse_3d.constructor`][console.utilities.sequences.tse.tse_3d.constructor] acquires `etl` phase-encoding steps per excitation (echo train). Key parameters are the number of encoding steps `n_enc` and the field of view `fov` (both [`Dimensions`][console.interfaces.dimensions.Dimensions]), the phase-encoding order `trajectory` (in-out, out-in or linear) and the assignment of readout and phase-encoding directions to the logical gradient axes (`channel_ro`, `channel_pe1`, `channel_pe2`). Setting a phase-encoding dimension of `n_enc` to 1 yields a 2D sequence.

The constructor returns the sequence and an ISMRMRD header with the encoding description. Each ADC event is labelled with its phase-encoding indices (`LIN`, `PAR`), which are used for k-space sorting and in the ISMRMRD export.

## Procedure

1. Construct the sequence and set the number of averages.
2. Unroll the sequence and run the acquisition.
3. Sort the acquired readouts into k-space with [`sort_kspace`][console.utilities.sequences.tse.tse_3d.sort_kspace], which returns an array of shape `(averages, coils, enc_z, enc_y, enc_x)`.
4. Reconstruct the image by a 3D FFT and display the slices.
5. Add k-space and image to the acquisition data, store it with `save()` and export it with `save_ismrmrd(header=header)`.

## Script

```python title="examples/tse_3d.py"
--8<-- "examples/tse_3d.py"
```
