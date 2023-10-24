Pulseq Sequence Provider
========================

This console application fully relies on MRI sequences provided by pulseq. The pulseq language or sequence format is not per default understandable by
all the different MRI systems or consoles respectively. Typically, each console has its own interface and professionals which would like to work with
pulseq need to concern themselves with a compiler to translates the pulseq file for their specific console. 

However, with this console application we've decided to implemnt native pulseq support. The replay sample points of this console are directly calculated from 
the provided pulseq sequence. The following sequence provider class is an extension of a pulseq sequence object and gathers all the methods 
required to calculate the waveforms, which are replayable by our console.

.. autoclass:: console.pulseq_interpreter.sequence_provider.SequenceProvider
   :members:
   :undoc-members:
   :show-inheritance:

Once a pulseq sequence was unrolled, the replayable sequence data is provided by the following interface.

.. autoclass:: console.pulseq_interpreter.interface_unrolled_sequence.UnrolledSequence   
   :members:
   :undoc-members:
   :show-inheritance: