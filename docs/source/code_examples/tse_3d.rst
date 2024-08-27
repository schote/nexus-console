3D Fast/Turbo Spin-Echo
=======================

The following example shows how to acquire a 3D image-volume based on fast/turbo spin-echo sequence written in pypulseq.
The example can essentially be broken down as follows. 

#. Create an ``AcquisitionControl`` using the default device configuration from the repository. 
   Here we can also set the log level for the log-file and the console log-output.
#. Construct the sequence

   - TE/TR of 14/600 ms gives a PD weighted image contrast
   - Echo train length (ETL) of 7 with an in-out trajectory to prevent relaxation effects
   - Optionally a number of dummy acquisitions can be set to prevent saturation effects
   - The gradient correction factor adds gradient moment prior to the ADC gate to compensate for eddy currents and center the readout.
   - With the FOV defined in m, we obtain a resolution of 3 x 3 x 6 mm in readout, PE1 and PE2 dimension.
   - The sequence constructor returns the sequence itself and an ISMRMRD header which can be used for reconstruction later on.
   - Note that the returned sequence contains labels which can be used to sort the acquired k-space.
#. We update the decimation rate in the global acquisition parameter instance, assuming that all the other acquisition parameters are set correctly.
#. Calculation and execution of the sequence. Depending on the settings the calculation may take some time, as the whole sequence is calculated before the execution.
#. Extract the down-sampled raw data and sort k-space according to the labels in the sequence usin the ``sort_kspace`` function.
#. Image reconstruction using ``np.fft.fftn``
#. Create an image grid and plot all the magnitude images along the PE2 dimension
#. Add additional information, e.g. a note on the acquisition or the sequence parameters, as well as the sorted k-space and the reconstructed image to the acquisition data and save the results.
#. Delete the acquisition control. This is an important step, as the destructor ``__del__`` of the ``AcquisitionControl`` class disconnects from the measurement cards.

.. literalinclude:: ../../../examples/tse_3d.py
