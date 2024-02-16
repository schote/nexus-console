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

The emergence of low-field MRI presents a cost-effective and portable solution in magnetic resonance imaging (MRI)[@oreilly:2021; @cooley:2020; @wald:2020; guallart-naval:2023]. Especially [open-source MRI systems](https://www.opensourceimaging.org/2023/01/09/first-open-source-mri-scanner-presented-the-osii-one/) foster transparency and accessibility of this important imaging modality. A very notable low-field system utilizes permament magnets in Halbach configuration to generate the required static magnetic field with a mean magnetic field strength of approximately 50 mT what leads to a Larmor-frequency of $\approx 2 \; \text{MHz}$. Radiofrequency pulses at Larmor frequency are used to generate transversal magnetization and the spatial signal encoding is achieved by superimposing linear gradient fields along the three spatial dimensions. All of these signals are controlled by a console-computer.

Currently the domain is experiencing a swift progress, particularly in the integration of auxiliary sensors @srinivas:2023 and the dynamic optimization of imaging parameters through feedback loop analytics @loktyushin:2021. Nonetheless, most available MRI consoles are not inherently designed to facilitate these complex techniques @negnevitsky:2023 or their proprietary nature poses limitations on customizability (e.g. limited on-board computing power, extension modules, or number of analog input/output channels). Our novel approach aims to bridge this gap and by providing a versatile, yet powerful console that enables a simple implementation of sophisticated methodologies and is easy to customize. It serves not only as a console but also as a high-performance reconstruction system enabling real-time data processing steps. It is tailored for advanced techniques and has the potential to significantly enhance the capabilities of low-field MRI systems, propelling the imaging performance beyond its current limits.


# Statement of Need

Especially for portable imaging applications, the employment of advanced approaches with local processing is desired. The console is implemented with two measurement cards from Spectrum-Instrumentation, an arbitrary waveform generator (transmit) and a digitizer (receive) module. The console application was implemented with measurement cards that provide 4 analog output channels with 40 Msps (M2p.6546-x4) and 8 single-ended or 4 differential analog input channels with 40 Msps (M2p.5933-x4).
However, the software is not limited to these specific modules, so that also modules with higher sampling rates can be controlled. Due to the high flexibility of the spectrum-cards, the number of transmit and receive channels can even be further extended by synchronizing additional measurement cards. Since the cards can be integrated on a standard motherboard, any other component like GPU, CPU or memory can be selected according to the individual needs what offers maximum flexibility and the delivery of the necessary performance.

The console is implemented as a versatile Python-based open-source software and build upon standards developed by the MRI community, i.e. it is inherently designed to process MRI sequences defined with pulseq. The software was developed and tested with a low-field MRI system, but dependent on the hardware modules, it can also be used to operate systems at ultralow- or mid-field strength.

Some of the applications which require this advanced setup are listed below.

**Electromagnetic Interference (EMI)** can be measured by placing sensing coils in the vicinity of the MRI system. The signals which are acquired by the sensing coils can be used to calculate and cancel the EMI noise from the received MR signal. By precisely sampling multiple analog receive channels in parallel the console allows correct assessment of EMI noise data.

**Real-time sequence updates** can be used to optimize the sequence, i.e. the gradient and RF activities at runtime. This allows subject specific optimization of the MRI acquisition and requires real-time sequence calculations. By block-wise calculation of the exact waveforms prior to the execution, these adjustments can be applied easily.

**B0-field** variations are caused by material imperfections and temperature dependencies. With additional sensors that measure the static magnetic B0-field locally, changes of the B0-field inhomogeneity can be detected. The consoles general purpose digital I/O ports allow to read data from such sensors. Based on the sensor data, the B0-field-map can be estimated and used to correct for image distortions caused by B0-field inhomogeneities.

**AI-driven data processing** is enabled by directly streaming the acquired data to a GPU. This not only allows fast digital down conversion of the high sampling-rate, but also the direct application of AI-models for further post-processing of the data extending the console to a powerful reconstruction system in a single edge-device. Sensor data can be directly incorporated in an advanced reconstruction model what reduces an overhead from data transfer.

**Trajectory corrections** are required to compensate hardware imperfections. The gradient power amplifier (GPA) translates the gradient waveform into a current which drives the gradient coils which are used for spatial encoding. The capability to process real-time feedback from the amplifier allows GIRF-based trajectory corrections for instance, which in turn improve the imaging performance.

There is a huge potential to optimize the performance and robustness in low-field imaging. By optimizing the sequence execution and maximizing the information obtainable from the system, the overall system performance can be improved what potentially enhances the image quality and the diagnostic value.

# Overview (Functionalities and Features)

This open-source software package implements a console application which orchestrates the execution of an MRI experiment using measurement cards from Spectrum-Instrumentation as described in the figure below.
An experiment description is contained in a pulse sequence provided by the community-developed standard called Pulseq.
In a first step, the sequence is interpreted and the calculation of the unrolled sample points from its compressed format is performed.
Two instances of an abstract device class manage the replay of the calculated sample points, as well as the acquisition of the MR signal which is phase sensitive and must be timed precicely. The package implements an acquisition control class which handles all the tasks described below and is yet simple to utilize. An overview of all the components involved in an acquisition is depicted below.

![Overview of the MRI system, which performs an image acquisition based on a given pulseq file; The calculated sequence is replayed by spectrum-instrumentation measurement cards, which control gradient and RF signals; Up to 8 channels can be configured for data acquisition, the sampled data is down-converted and provided as numpy array.\label{fig:overview}](/docs/source/_figures/system_components.png)

The console-software is implemented in python and can be used stand-alone or as a sub-component for acquisition software which implements a user interface for instance. In addition to the execution of an MRI experiment, the package also implements different methods for sequence construction, post-processing and data provisioning.


# Documentation and Testing

The repository features a complete documentation which incorporates a setup guide, api documentation, description of the software architecture and examples. Please note, that a concrete MRI experiment might differ from the experiments that can be found under examples, as true experiments always depend on the local setup and the concrete application. This is why, experiments are usually kept in a separate repository. The documentation is always up to date with the latest code changes and is updated by an automated deployment pipeline, when changes are pushed to the repository. The repository also implements tests which guarantee the main functionalities of the package. Please note, that the tests do not cover all functions of the code, as they are running on a virtual machine within the continuous integration.

# Acknowledgements

This work is part of the Metrology for Artificial Intelligence for Medicine (M4AIM) project that is funded by the Federal Ministry for Economic Affairs and Energy (BMWi) in the frame of the QI-Digital initiative.

The project (21NRM05 and 22HLT02 A4IM) has received funding from the European Partnership on Metrology, co-financed by the European Union’s Horizon Europe Research and Innovation Program and by the Participating States.


# References