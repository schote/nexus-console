Spin Echo Spectrum
==================

The following example shows how to acquire an NMR spectrum with a spin-echo based spectrum sequence written in pypulseq.

The example can essentially be broken down as follows:
1. Create an ``AcquisitionControl`` using the default device configuration from the repository. Here we can also set the log level for the log-file and the console log-output.
2. Construct the spin echo based spectrum sequence. Here we use 20 ms echo time and 200 us RF block pulse duration.
3. Define the most basic ``AcquisitionParameter``, namely the Larmor frequency :math:`f_0` and the decimation factor for DDC.
4. Execute the experiment.
5. Extract the down-sampled raw data.
6. Apply FFT to obtain the spectrum and calculate the associated frequency axis.
7. Plot the magnitude spectrum.
8. Add some note to the meta data of the ``AcquisitionData`` and save the results using the ``write`` method.
9. Delete the acquisition control. This is an important step, as the destructor ``__del__`` of the ``AcquisitionControl`` class disconnects from the measurement cards.


.. literalinclude:: ../../../examples/se_spectrum.py
