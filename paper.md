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

The emergence of low-field MRI presents a cost-effective and portable solution in magnetic resonance imaging [@oreilly:2021; @cooley:2020; @wald:2020; guallart-naval:2023]. Especially for portable imaging applications, the employment of advanced approaches with local processing is desired. The domain is currently experiencing swift progress, particularly in the integration of auxiliary sensors @srinivas:2023 and the dynamic optimization of imaging parameters through feedback loop analytics @loktyushin:2021.

Most available MRI consoles are not inherently designed to facilitate these complex techniques @negnevitsky:2023 or their proprietary nature poses limitations on the customizability (e.g. limited on-board computing power, extension modules, or number of analog input/output channels).

Our novel approach aims to bridge this gap and by providing a versatile, yet powerful console that enables a simple implementation of sophisticated methodologies and is easy to customize. The console is implemented with two measurement cards from Spectrum-Instrumentation, an arbitrary waveform generator (transmit) and a digitizer (receive) module. The console application was implemented with measurement cards that provide 4 analog output channels with 40 Msps (M2p.6546-x4) and 8 single-ended or 4 differental analog input channels with 40 Msps (M2p.5933-x4). In principle the measurement cards


 Especially for portable imaging applications, the employment of advanced approaches, such as EMI suppression @liu:2021 and elaborate reconstruction models for B0 inhomogeneity corrections, has yielded substantial improvements in image fidelity [@schote:2022; @schote:2023; @koolstra:2021]. The domain is currently experiencing swift progress, particularly in the integration of auxiliary sensors @srinivas:2023 and the dynamic optimization of imaging parameters through feedback loop analytics @loktyushin:2021. Nonetheless, most available MRI consoles are not inherently designed to facilitate these complex techniques @negnevitsky:2023 or their proprietary nature poses limitations on customizability (e.g. limited on-board computing power, extension modules, or number of analog input/output channels). Our novel approach aims to bridge this gap and by providing a versatile, yet powerful console that enables a simple implementation of sophisticated methodologies and is easy to customize.

Spectrum-Instrumentation measurement cards serve as the foundational core component of the console. As arbitrary waveform generator the M2p.6546-x4 with additional 16 GPIO ports (FX2 connector) and as digitizer the M2p.5933-x4 were chosen. This allows for a total of 4 analog (16-bit) transmit channels with 40 MS/s. For reception 8 single-ended or 4 differential analog input channels can be used with up to 40 MS/s at 16-bit resolution. Both cards accommodate a 512 MS (1 GB) memory. The measurement-cards were installed via the PCI express slots of the console main board. The console is equipped with a 24 core Intel CPU (6312U) and 256 GB RAM. The configuration is shown in Figure 1.


It serves not only as a console but also as a high-performance reconstruction system enabling real-time data processing steps. It is tailored for advanced techniques and has the potential to significantly enhance the capabilities of low-field MRI systems, propelling the imaging performance beyond its current limits.

# Statement of need

- Advanced approaches in low-field MRI such as EMI, sequence optimization MR-zero or B0-inhomogeneity compensation
- Utilization of additional sensors
- A modular and easy-to-customize approach, yet delivering the necessary performance
- Combination of console and reconstruction system in a single edge-device
- Streaming to CPU/GPU, for AI driven data processing







The presented MR console was successfully implemented and tested on a low-field MRI scanner. The Python-based open-source implementation of the console software, along with the integration of Pulseq compatibility is publicly available and facilitates broad and straightforward adoption across the community for a multitude of applications.
In the current setup, gradient waveforms are replayed through the analog transmission channels capable of driving the GPA directly. Nonetheless, it is also feasible to dispatch these waveforms through the synchronous GPIO channels what would liberate three analog transmission channels. Moreover, the system's ability to synchronize up to eight measurement cards simplifies the expansion to even more transmit and receive channels as necessitated by more demanding applications, like B0-field supervision, noise-cancelling or GIRF based trajectory corrections.
The utilized cards enable direct data streaming to GPU memory, which paves the way for rapid AI-driven image reconstruction techniques and the potential to implement real-time adaptive feedback systems. This could significantly optimize both the sequence execution and the performance of external hardware components, which potentially enhances the image quality and the diagnostic value. Furthermore, the implementation facilitates effortless integration with the web-based acquisition control platform, ScanHub @schote-scanhub:2023.

# Acknowledgements

This work is part of the Metrology for Artificial Intelligence for Medicine (M4AIM) project that is funded by the Federal Ministry for Economic Affairs and Energy (BMWi) in the frame of the QI-Digital initiative.

The project (21NRM05 and 22HLT02 A4IM) has received funding from the European Partnership on Metrology, co-financed by the European Union’s Horizon Europe Research and Innovation Program and by the Participating States.


# References