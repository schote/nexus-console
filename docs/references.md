---
hide:
  - navigation
---

# References

## Related Publications

1. <a id="ref-1"></a>Schote D, Silemek B, O'Reilly T, Seifert F, Assmy JL, Kolbitsch C, Webb AG, Winter L. Nexus: A versatile console for advanced low-field MRI. *Magn Reson Med.* 2025. [doi:10.1002/mrm.30406](https://doi.org/10.1002/mrm.30406)
2. <a id="ref-2"></a>Layton KJ, Kroboth S, Jia F, Littin S, Yu H, Leupold J, Nielsen JF, Stöcker T, Zaitsev M. Pulseq: A rapid and hardware-independent pulse sequence prototyping framework. *Magn Reson Med.* 2017;77(4):1544–1552. [doi:10.1002/mrm.26235](https://doi.org/10.1002/mrm.26235)
3. <a id="ref-3"></a>Ravi KS, Geethanath S, Vaughan JT. PyPulseq: A Python package for MRI pulse sequence design. *J Open Source Softw.* 2019;4(42):1725. [doi:10.21105/joss.01725](https://doi.org/10.21105/joss.01725)
4. <a id="ref-4"></a>Inati SJ, Naegele JD, Zwart NR, Roopchansingh V, Lizak MJ, Hansen DC, Liu CY, Atkinson D, Kellman P, Kozerke S, Xue H, Campbell-Washburn AE, Sørensen TS, Hansen MS. ISMRM Raw data format: A proposed standard for MRI raw datasets. *Magn Reson Med.* 2017;77(1):411–421. [doi:10.1002/mrm.26089](https://doi.org/10.1002/mrm.26089)
5. <a id="ref-5"></a>Hogenauer EB. An economical class of digital filters for decimation and interpolation. *IEEE Trans Acoust Speech Signal Process.* 1981;29(2):155–162. [doi:10.1109/TASSP.1981.1163535](https://doi.org/10.1109/TASSP.1981.1163535)

## Reference Data

Herthum H, Schote D. OSI²ONE Low-field MRI Reference System Data. *Zenodo.* 2026. [doi:10.5281/zenodo.21807140](https://doi.org/10.5281/zenodo.21807140)

This open dataset (CC BY 4.0) was recorded with a Nexus console on the OSI²ONE low-field reference system, a 48.5 mT Halbach magnet. It contains phantom measurements for quality assurance, T₁, T₂ and B₀ mapping, and PD- and T₂-weighted imaging. Each acquisition includes the raw data in ISMRMRD format, the Pulseq sequence file and the console configuration metadata, together with DICOM images and, where applicable, quantitative maps. The reconstructions can be reproduced with the accompanying Jupyter notebooks.

## Hardware Documentation

Hardware manuals for the measurement card families provided by Spectrum Instrumentation:

- Arbitrary waveform generator family [M2p.65xx manual](https://spectrum-instrumentation.com/dl/m2p_65xx_manual_english.pdf)
- Digitizer family [M2p.59xx manual](https://spectrum-instrumentation.com/dl/m2p_59xx_manual_english.pdf)

### Open Source Imaging Initiative (OSI²)

The [Open Source Imaging Initiative (OSI²)](https://www.opensourceimaging.org/) is a non-profit association that develops open-source hardware and software for MRI, with the aim of making modern imaging accessible to many more people around the world. Its [GitLab group](https://gitlab.com/osii) collects the hardware projects for building a low-field MRI system, from the magnet, gradient and RF components to complete scanners such as the OSI² ONE, as well as phantoms, tools and the Nexus console.

## Related Software Projects

| Project | Use in Nexus |
|---|---|
| [Pulseq](https://pulseq.github.io/) | Open, vendor-independent sequence format |
| [PyPulseq](https://github.com/imr-framework/pypulseq) | Sequence construction and base class of the sequence provider |
| [ISMRMRD](https://ismrmrd.github.io/) | Raw data format of the exported acquisitions |
| [MRpro](https://mrpro.rocks/) | Example reconstruction framework for the exported data |
