---
hide:
  - navigation
  - toc
---

# Nexus Console

**An open-source Python framework for versatile low-field MRI acquisition**

Nexus Console is a hardware-agnostic, open-source software framework that enables direct replay of [PyPulseq](https://github.com/imr-framework/pypulseq) pulse sequences on Spectrum Instrumentation arbitrary-waveform generator (AWG) and digitizer cards, eliminating the need for vendor-specific sequence compilers. The framework directly interprets the pulseq open standard, streams RF and gradient waveforms to the transmit card in real time via FIFO mode, and acquires NMR signals in gated FIFO mode on the receive card. Acquired data are post-processed on the host (demodulation, phase correction, decimation) and exported in [ISMRMRD](https://ismrmrd.github.io/) format for seamless compatibility with Gadgetron and other reconstruction frameworks.

The console has been validated on a 50 mT Halbach-configured low-field MRI scanner and is described in:

> Schote D, Silemek B, Seifert F, et al. *Nexus Console: An Open-Source Python Console for a Versatile Low-Field MRI System.* Magn Reson Med. 2025.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting started**

    ---

    Install the package and run your first acquisition in minutes.

    [:octicons-arrow-right-24: Installation](setup/installation.md)

-   :material-developer-board:{ .lg .middle } **Hardware**

    ---

    Understand the MRI system layout, card pinouts, and port assignments.

    [:octicons-arrow-right-24: System setup](setup/system_setup.md)

-   :material-flask-outline:{ .lg .middle } **Examples**

    ---

    Step-by-step walkthroughs of NMR spectroscopy, T2 mapping, and 3D imaging.

    [:octicons-arrow-right-24: Examples](examples/index.md)

-   :material-code-braces:{ .lg .middle } **Code reference**

    ---

    Full API documentation with narrative explanations and architecture diagrams for every module.

    [:octicons-arrow-right-24: Reference](reference/)

</div>

The project is listed on [opensourceimaging.org](https://www.opensourceimaging.org/project/nexus-console/) and the source code is available on [GitHub](https://github.com/schote/nexus-console).
