Nexus Console
================
Open-Source Python Framework for a Versatile Low-Field MRI Console
------------------------------------------------------------------

Welcome to the documentation for the Nexus console—an open-source software framework for an advanced low-field MRI console. 
This console is driven by measurement cards from Spectrum-Instrumentation and is controlled by open-source software written in Python. 
It offers a cost-effective solution for advanced low-field imaging techniques involving additional sensor information, e.g. for EMI mitigation or B0-field tracking.
Also it serves as a reconstruction system with enough power for deep-learning-based image optimization or model-based reconstruction.
Successfully implemented and tested on a low-field MRI scanner, Nexus demonstrates real-time computed Pulseq sequences with high fidelity compared to measured waveforms. 
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

The console has been presented at ISMRM 2024 in Singapore:

   Schote D, Silemek B, Seifert F, et al. Beyond Boundaries – A versatile Console ­for Advanced Low-Field MRI. In: Proc. Intl. Soc. Mag. Reson. Med. Vol 33. Singapore; 2024.

The project can also be found on `opensourceimaging.org <https://www.opensourceimaging.org/project/nexus-console/>`_.


Content Overview
----------------

.. toctree::
   :maxdepth: 1
   
   quick_start
   user_guide/index
   code_examples/index
   api_reference/index