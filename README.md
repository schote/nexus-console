# Nexus Console

**An open-source Python console for versatile low-field MRI acquisition.**

![Python](https://img.shields.io/badge/python-3.13-blue)
[![License](https://img.shields.io/github/license/schote/nexus-console)](https://www.gnu.org/licenses/gpl-3.0.de.html)
[![Docs](https://github.com/schote/nexus-console/actions/workflows/docs-mkdocs.yml/badge.svg)](https://schote.github.io/nexus-console/)
[![Static Tests](https://github.com/schote/nexus-console/actions/workflows/static-tests.yml/badge.svg)](https://github.com/schote/nexus-console/actions/workflows/static-tests.yml)
[![Pytest](https://github.com/schote/nexus-console/actions/workflows/pytest.yml/badge.svg)](https://github.com/schote/nexus-console/actions/workflows/pytest.yml)
![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2Fschote%2F4d47c22492a23337a79400f4859a4c25%2Fraw%2Fcd5263422b929b375047c5b78e145f5cec6197ad%2Fcoverage.json)

<!-- --8<-- [start:summary] -->
Nexus replaces the proprietary spectrometer of an MRI system by two commercial PCIe measurement cards from Spectrum Instrumentation, an arbitrary waveform generator (transmit) and a digitizer (receive), operated by an open-source Python software. Pulse sequences are defined in the open [Pulseq](https://pulseq.github.io/) format using [PyPulseq](https://github.com/imr-framework/pypulseq) and unrolled directly into RF and gradient waveforms, which are streamed to the transmit card without a vendor-specific sequence compiler. Received signals are demodulated, phase-corrected and decimated on the host and exported in the [ISMRMRD](https://ismrmrd.github.io/) format for reconstruction with any compatible framework.

The console was developed and validated on a 50 mT low-field MRI system. It is not tied to a specific field strength or hardware setup: amplifiers, coils and system limits are described in a configuration file.
<!-- --8<-- [end:summary] -->

## Documentation

The [documentation](https://schote.github.io/nexus-console/) includes a quick start guide, system guide, examples, API reference and a list of related references.

To build the documentation locally, install the `docs-mkdocs` extra and start the development server:

```bash
pip install -e ".[docs-mkdocs]"
mkdocs serve --watch src
```

## Installation

Requires Python ≥ 3.13 and the [Spectrum Instrumentation driver](https://spectrum-instrumentation.com/support/downloads.php) for the measurement cards.

```bash
pip install nexus-console
```

See the [Installation](https://schote.github.io/nexus-console/setup/installation/) for the development installation and the device configuration.

## Repository structure

| Path | Contents |
|---|---|
| [`src/console/`](src/console/) | Python package: card control, sequence unrolling, data interfaces, processing, built-in sequences |
| [`examples/`](examples/) | Acquisition scripts and a reference device configuration |
| [`tests/`](tests/) | Test suite |
| [`docs/`](docs/) | Documentation sources (MkDocs) |

<!-- --8<-- [start:citation] -->
## Citation

If you use Nexus in your work, please cite:

> Schote D, Silemek B, O'Reilly T, Seifert F, Assmy JL, Kolbitsch C, Webb AG, Winter L. Nexus: A versatile console for advanced low-field MRI. *Magn Reson Med.* 2025. [doi:10.1002/mrm.30406](https://doi.org/10.1002/mrm.30406)
<!-- --8<-- [end:citation] -->

<!-- --8<-- [start:acknowledgments] -->
## Acknowledgments

This work is part of the Metrology for Artificial Intelligence for Medicine (M4AIM) project, funded by the Federal Ministry of Economic Affairs and Climate Action (BMWK) as part of the QI-Digital initiative.
The projects 21NRM05 STASIS and 22HLT02 A4IM have received funding from the European Partnership on Metrology, cofinanced by the European Union's Horizon Europe Research and Innovation Program and by the Participating States.
Partial support is provided by a European Research Council Advanced Grant (PASMAR 101021218).
This work is supported by the Open Source Imaging Initiative (OSI²).
<!-- --8<-- [end:acknowledgments] -->
