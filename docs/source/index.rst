Spectrum-Console
================
Fully Digital Open-Source Console for MRI Acquisitions Written in Python
------------------------------------------------------------------------

Welcome to the documentation for the Spectrum Console—an open-source MRI console 
designed for low-field magnetic resonance imaging (MRI). 
This console, driven by Spectrum-Instrumentation measurement cards and Python-based software, 
offers a cost-effective and portable solution for exploring sophisticated low-field imaging techniques. 
Successfully implemented and tested on a low-field MRI scanner, 
the Spectrum-Console demonstrates real-time computed Pulseq sequences 
with high fidelity compared to measured waveforms. 
The console's design holds the potential to enhance the capabilities of low-field MRI systems, fostering opportunities for advanced techniques in the field.
Explore the documentation to delve into the technical details and possibilities offered by the Spectrum-Console.
The documentation provides insights, including quick-start guide, user guide, hands-on examples and the API reference.

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: :fas:`rocket; fa-xl` Quick Start Guide

      This guide provides a quick introduction and explains which requirements must be met, 
      how the software can be installed and what an example program looks like.
      
      .. button-ref:: quick-start
         :expand:
         :color: primary
         :click-parent:

         To the quick start guide

   .. grid-item-card:: :fas:`box-open; fa-xl` Examples

      Examples that show how the package is used. A prerequisite is a successful installation.

      .. button-ref:: examples
         :expand:
         :color: primary
         :click-parent:
         
         To the examples

   .. grid-item-card:: :fas:`book-open; fa-xl` User Guide

      The key concept guide contains general information about the package components and their functionality.
      The concept guide contains more general information independent of the implementation.

      .. button-ref:: user-guide
         :expand:
         :color: primary
         :click-parent:

         To the concepts

   .. grid-item-card:: :fas:`code; fa-xl` API Reference

      The API reference guide contains a detailed description of
      the Spectrum-Console API. The reference describes how the methods work and which parameters can
      be used. It assumes that you have an understanding of the key concepts.

      .. button-ref:: api
         :expand:
         :color: primary
         :click-parent:

         To the reference


Content Overview
----------------

.. toctree::
   :maxdepth: 2
   
   quick_start/index
   user_guide/index
   code_examples/index
   api_reference/index