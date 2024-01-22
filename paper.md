---
title: 'Spectrum-Console: A versatile Python-based Console for Advanced Low-Field MRI'
tags:
  - Python
  - MRI
  - console
  - data acquisition
  - spectrum instrumentation
authors:
  - name: David Schote
    orcid: 0000-0003-3468-0676
    corresponding: true
    affiliation: 1
  - name: Berk Silemek
    affiliation: 1
  - name: Frank Seifert
    affiliation: 1
affiliations:
 - name: Physikalisch-Technische Bundesanstalt (PTB), Braunschweig and Berlin, Germany
   index: 1
date: 08.01.2024
bibliography: paper.bib
---

# Summary


The emergence of low-field MRI presents a cost-effective and portable solution in magnetic resonance imaging (MRI)[@oreilly:2021; @cooley:2020; @wald:2020; guallart-naval:2023]. Especially [open-source MRI systems](https://www.opensourceimaging.org/2023/01/09/first-open-source-mri-scanner-presented-the-osii-one/) foster transparency and accessibility of this important imaging modality. Usually, an MRI system is build as described in the figure below. One of the key components is the console computer which controls all the different hardware modules. It control the gradient power amplifier, the RF power amplifier and samples the MR signal.

Especially for portable imaging applications, the employment of advanced approaches with local processing is desired. The domain is currently experiencing swift progress, particularly in the integration of auxiliary sensors @srinivas:2023 and the dynamic optimization of imaging parameters through feedback loop analytics @loktyushin:2021.
Most available MRI consoles are not inherently designed to facilitate these complex techniques @negnevitsky:2023 or their proprietary nature poses limitations on the customizability (e.g. limited on-board computing power, extension modules, or number of analog input/output channels).
Our novel approach aims to bridge this gap by providing a versatile, yet powerful console that enables a simple implementation of sophisticated methodologies and is easy to customize. The console is implemented with two measurement cards from Spectrum-Instrumentation, an arbitrary waveform generator (transmit) and a digitizer (receive) module. The console application was implemented with measurement cards that provide 4 analog output channels with 40 Msps (M2p.6546-x4) and 8 single-ended or 4 differential analog input channels with 40 Msps (M2p.5933-x4).

This open-source software package implements a console application which orchestrates the execution of an MRI experiment using measurement cards from Spectrum-Instrumentation as described in the figure below.
An experiment description is contained in a pulse sequence provided by the community-developed standard called Pulseq.
In a first step, the sequence is interpreted and the calculation of the unrolled sample points from its compressed format is performed.
Two instances of an abstract device class manage the replay of the calculated sample points, as well as the acquisition of the MR signal which is phase sensitive and must be timed precicely.
The package implements an acquisition control class which handles all the tasks described below and is yet simple to utilize.
It is implemented in python and can be used stand-alone or as a sub-component for acquisition software which also implements a user interface for instance.
In addition to the execution of an MRI experiment, the package also implements different methods for sequence construction, post-processing and data provisioning.

![alt text](/docs/source/_figures/system_components.png "System Setup")


# Statement of Need

- Advanced approaches in low-field MRI such as EMI, sequence optimization MR-zero or B0-inhomogeneity compensation
- Utilization of additional sensors: e.g. for B0-field supervision, noise-cancelling or GIRF based trajectory corrections
- A modular and easy-to-customize approach, yet delivering the necessary performance
- Combination of console and reconstruction system in a single edge-device capable of real-time data processing
- Direct streaming to GPU for rapid AI-driven data processing, i.e. image reconstruction or real-time adaptive feedback systems
- Versatile Python based open-source software framework
- Console build upon community-developed pulseq standard
- Developed for low-field MRI but easily transferable to ultra-low, mid or high-field MRI through spectrum-instrumentation programming interface

  **Consequence:** Optimize both the sequence execution and the performance of external hardware components, which potentially enhances the image quality and the diagnostic value. Has the potential to significantly enhance the capabilities of low-field MRI systems, propelling the imaging performance beyond its current limits.

# Acknowledgements

This work is part of the Metrology for Artificial Intelligence for Medicine (M4AIM) project that is funded by the Federal Ministry for Economic Affairs and Energy (BMWi) in the frame of the QI-Digital initiative.

The project (21NRM05 and 22HLT02 A4IM) has received funding from the European Partnership on Metrology, co-financed by the European Union’s Horizon Europe Research and Innovation Program and by the Participating States.


# References