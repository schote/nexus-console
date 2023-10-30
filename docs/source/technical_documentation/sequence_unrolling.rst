Sequence Unrolling
==================

The sequence unrolling is performed by the `SequenceProvider` class which inherits from the pypulseq `Sequence` class.
After a new instance of the `SequenceProvider` has been created, a sequence can either be loaded from file or set from a `Sequence` instance.
For sequence unrolling the larmor frequency must be provided, as the algorithm calculates the modulated RF waveform including the carrier signal.
Both, gradient and RF waveforms are unrolled at identical sample rate because they are replayed synchronously.
We use a sampling rate of 20 Msps what corresponds to an oversampling factor of approximately 10 for the RF signal.

Gradient Unrolling
------------------

A pulseq sequence can have two different types of gradient events, a trapezoidal or an arbitrary gradient.
The arbitrary gradient contains a waveform and the corresponding time points, which is interpolated during the unrolling routine.
The trapezoidal gradient event is defined by flat amplitude, rise time, fall time and duration.
Before calculating the waveform, the overall maximum amplitude is calculated and compared against the channel limit.
Due to the high sampling rate for the gradient waveforms, unrolling must be computationally efficient.
Thus, all the checks are performed using the compressed gradient information from the pulseq definition.
The unrolled waveform is added to the unrolled sequence array. 
The waveform must be added as the array may already contain a static offset value for the channel.
The gradient delay is calculated in sample points and defines the offset of the starting point in the unrolled array.

RF Unrolling
------------

Using frequency and phase offset values from the pulseq RF block description the carrier wave is calculated for the larmor frequency provided by the user.
The phase evolution during transmit is accounted by a phase offset of the carrier wave, which depends on the number of sample points since the very first RF event.
The RF pulse envelope is resampled and multiplied to the carrier signal to obtain the amplitude modulated RF signal.
As for the gradient unrolling the delay, dead times and ringdown time is accounted by a position offset in the unrolled sequence array.

Digital Signals
---------------

Three digital signals are required to control the acquisition - RF unblanking, adc gate and phase reference signal.
All the digital signals are encoded by the 16th bit of one of the analog signals. 
To obtain the full resolution of the RF signal, we use the 16th bit of the gradient channels to encode the three digital signals.
When combining analog and digital signal, the MSB of the gradient waveform is the 15th bit.
The RF unblanking signal is set within the RF unrolling method.
The ADC event is a standalone event and is set together with the reference signal by a separate method.