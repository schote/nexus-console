Pulseq Sequence Interpreter
===========================

The pulseq sequence interpreter consists of two sub-components. 
The `SequenceProvider` reads all the events from a pulseq sequence and calculates RF and gradient waveform.
The unrolled pulse sequence is provided as `UnrolledSequence` which contains the unrolled waveforms and some additional data.

Sequence Provider
-----------------

.. automodule:: console.pulseq_interpreter.sequence_provider
   :members:
   :undoc-members:
   :show-inheritance:


.. _unrolled-sequence:

Unrolled Sequence
-----------------

.. automodule:: console.pulseq_interpreter.interface_unrolled_sequence
   :members:
   :undoc-members:
   :show-inheritance:

