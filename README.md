# Nexus Console

**An open-source Python console for versatile low-field MRI acquisition.**

![Python](https://img.shields.io/badge/python-3.13-blue)
[![License](https://img.shields.io/github/license/schote/nexus-console)](https://www.gnu.org/licenses/gpl-3.0.de.html)
[![Docs](https://github.com/schote/nexus-console/actions/workflows/docs-mkdocs.yml/badge.svg)](https://schote.github.io/nexus-console/)
[![Static Tests](https://github.com/schote/nexus-console/actions/workflows/static-tests.yml/badge.svg)](https://github.com/schote/nexus-console/actions/workflows/static-tests.yml)
[![Pytest](https://github.com/schote/nexus-console/actions/workflows/pytest.yml/badge.svg)](https://github.com/schote/nexus-console/actions/workflows/pytest.yml)
![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2Fschote%2F4d47c22492a23337a79400f4859a4c25%2Fraw%2Fcd5263422b929b375047c5b78e145f5cec6197ad%2Fcoverage.json)

## 1. Introduction & Motivation

MRI consoles are traditionally closed, vendor-specific systems: sequences must pass through a proprietary compiler before they reach the hardware, which limits the adaptability and increases the costs of low-field MRI scanners.

Nexus replaces that stack with commercial off-the-shelf PCIe measurement cards operated by the Nexus console software implemented in Python. It interprets the open [pulseq](https://pulseq.github.io/) standard directly using [PyPulseq](https://github.com/imr-framework/pypulseq) and unrolls sequences directly into RF and gradient waveforms, which are streamed to the hardware in real time, with no vendor sequence compiler in between. Acquired data are demodulated, phase-corrected and decimated on the host and written as [ISMRMRD](https://ismrmrd.github.io/), so any reconstruction toolbox (e.g. [MRpro](https://mrpro.rocks/)) can pick them up.

The console was developed and validated on a 50 mT Halbach permanent-magnet scanner, but it is not tied to that field strength. Using a different set of measurement cards, it can be adapted to higher field strengths.

## 2. Hardware Overview

| Component | Part used here | Role |
|---|---|---|
| Transmit card | Spectrum Instrumentation **M2p.6546-x4** (PCIe AWG) | Replays RF (Ch 0) and gradient waveforms (Ch 1–3), digital control signals encoded in bit 15 and mirrored on X1–X3 |
| Receive card | Spectrum Instrumentation **M2p.5933-x4** (PCIe digitizer) | Samples the NMR signal and additional sensor input, clock master for both cards |

→ Full signal chain, pinouts and configuration fields: [System setup](https://schote.github.io/nexus-console/setup/system_setup/) and [Measurement cards](https://schote.github.io/nexus-console/setup/cards/).

## 3. Installation

Requires **Python ≥ 3.13** and an installed [Spectrum Instrumentation driver](https://spectrum-instrumentation.com/support/downloads.php) for the PCIe cards. Use a virtual environment (`conda` or `venv`).

```bash
# Users
pip install nexus-console

# Developers
git clone https://github.com/schote/nexus-console.git
cd nexus-console
pip install -e ".[test,lint,dev]"
```

Optional extras — `test`, `lint`, `dev`, `docs-mkdocs` — cover testing, static analysis, profiling/notebooks and the documentation build; combine them in one bracketed list as above. Verify with `nexus --help`.

Hardware is described by a `device_config.yaml` (see [`examples/example_device_config.yaml`](examples/example_device_config.yaml)), which must be adapted to your system.

→ [Installation guide](https://schote.github.io/nexus-console/setup/installation/)

## Repository Structure

| Path | Contents |
|---|---|
| [`src/console/spcm_control/`](src/console/spcm_control/) | Card drivers (`tx_device`, `rx_device`), the `acquisition_control` orchestrator and the vendor `spcm` register bindings |
| [`src/console/pulseq_interpreter/`](src/console/pulseq_interpreter/) | `sequence_provider` — unrolls PyPulseq sequences into interleaved int16 waveforms |
| [`src/console/interfaces/`](src/console/interfaces/) | Pydantic data models: device configuration, acquisition parameters, acquisition/RX data |
| [`src/console/service/`](src/console/service/) | `nexus` CLI entry point and acquisition manager |
| [`src/console/utilities/`](src/console/utilities/) | Ready-made sequences (spectrometry, calibration, TSE), DDC, SNR, plotting, ISMRMRD export |
| [`examples/`](examples/) | Runnable acquisition scripts and a reference device configuration |
| [`tests/`](tests/) | Pytest suite |
| [`docs/`](docs/) | MkDocs sources for the [project documentation](https://schote.github.io/nexus-console/) |

## Usage

See the [documentation](https://schote.github.io/nexus-console/) for the quick-start guide, worked examples (spin-echo spectrum, T2 relaxation, 3D TSE) and the full API reference.

## Publication

If you find this useful in your work, please [cite](https://doi.org/10.1002/mrm.30406):

> Schote D, Silemek B, O'Reilly T, Seifert F, Assmy JL, Kolbitsch C, Webb AG, Winter L. Nexus: A versatile console for advanced low-field MRI. Magn Reson Med. 2025. doi: 10.1002/mrm.30406.

## Acknowledgments

This work is part of the Metrology for Artificial Intelligence for Medicine (M4AIM) project, funded by the Federal Ministry of Economic Affairs and Climate Action (BMWK) as part of the QI-Digital initiative.

The projects 21NRM05 STASIS and 22HLT02 A4IM have received funding from the European Partnership on Metrology, cofinanced by the European Union's Horizon Europe Research and Innovation Program and by the Participating States.
Partial support is provided by a European Research Council Advanced Grant (PASMAR 101021218).
This work is supported by the Open Source Imaging Initiative (OSI²).
