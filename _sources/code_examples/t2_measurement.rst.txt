T2 Measurement
==============

The following example shows how to perform a T2 measurement and fit the T2 decay to get the T2 value.
The example can essentially be broken down as follows:

#. Create an ``AcquisitionControl`` using the default device configuration from the repository. Here we can also set the log level for the log-file and the console log-output.
#. Construct the T2 relaxation sequence. 
   The range of echo times used for the measurement is given as a tuple. 
   The number of experiments in between is defined by ``num_steps``. The repetition time (TR) between each spin-echo experiments can also be specified.
   Note that this sequence constructor also returns a list of TE values used in the experiment.
#. Define ``AcquisitionParameter``, namely Larmor frequency :math:`f_0`, b1 scaling factor and the DDC decimation factor.
#. Execute the experiment and extract the raw data. The data for the different TE values is stored in the phase encoding dimension.
   E.g. if ``num_steps = 50``, the second last dimension of the raw data should be 50.
#. Extract the maximum of the complex signal in time domain for each echo time.
#. Define the T2 model given by :math:`A + B e^{- \frac{\text{TE}}{C}}` and fit the determined maximum values using the TE values from the sequence.
#. The fitted parameters are used to calculate the decay for a larger echo-time-space and the result is plotted along with the measured data points.
#. Add some note to the meta data of the ``AcquisitionData`` and save the results using the ``write`` method.
#. Delete the acquisition control. This is an important step, as the destructor ``__del__`` of the ``AcquisitionControl`` class disconnects from the measurement cards.


.. literalinclude:: ../../../examples/t2_measurement.py
