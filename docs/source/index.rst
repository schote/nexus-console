Spectrum-Console: Fully Digital Open-Source Console for MRI Acquisitions Written in Python
==========================================================================================

Welcome to the documentation of our open-source console application for MRI. 
In collaboration with many excellent partners throughout Europe, we at PTB Berlin are working on a low-field MRI scanner.
The scanner is mobile, affordable, fully open source, and intended for human use.

Low-field MRI comes with two major problems, low signal-to-noise ratio (SNR) and strong field inhomogeneities which can cause geometric distortions in the acquired images if uncorrected.
In order to compensate these effects we started this MRI console application which aims to allow best possible integration of additional sensor technology and machine learning workflows.

The technical documentation sections provides an overview of the architecture but also detailed descriptions of all the components. 
Within the user guide we provide a more practical introduction of how to get started.
The example section contains some hands-on examples and the code documentation is provided in the API section.

.. toctree::
   :maxdepth: 2
   :caption: Content
   
   technical_documentation/index
   user_guide
   code_examples/index
   api
