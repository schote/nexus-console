# Hardware

This page lists the components required to set up a Nexus console and describes the installation of the measurement cards. The exact configuration depends on the target MRI system and its intended use. The values given below are reference values, not requirements of the software.

## Components

### Console

| Component | Requirement | Reference |
|---|---|---|
| Transmit card | Spectrum Instrumentation M2p.65xx AWG with 4 analog channels and 3 multi-purpose digital lines | M2p.6546-x4 |
| Receive card | Spectrum Instrumentation M2p.59xx digitizer, clock output, external trigger input, multi-purpose line X2 | M2p.5933-x4 (8 channels) |
| Host computer | Two free PCIe slots for the cards; see [Host computer](#host-computer) | Workstation |
| Operating system | Windows or Linux with the Spectrum driver installed | |
| Cables | Coaxial cables for clock, ADC gate and phase reference (see [Wiring](wiring.md)) | |

The software checks the card family on connection: the transmit card must be of type `M2p.65xx`, the receive card of type `M2p.59xx`. Other models of these families can be used if the channel count and the voltage ranges given in the [device configuration](configuration.md) are supported.

### MRI system

| Component | Function | Interface to the console |
|---|---|---|
| RF power amplifier (RFPA) | Amplifies the transmit RF waveform | Analog input from TX channel 0; digital unblanking input from TX X3 |
| Gradient power amplifier (GPA) | Converts the gradient control voltages into coil currents | Three analog inputs from TX channels 1–3; gain in A/V |
| Gradient coils | Spatial encoding | Efficiency in T/m/A |
| T/R switch, preamplifier | Protects the receive chain during transmission and amplifies the MR signal | Analog output to RX channel 0 |
| RF coil, magnet | Excitation and detection | |

Gain and efficiency values of the amplifiers and coils are part of the device configuration and are used to scale the sequence waveforms (see [Sequence unrolling](sequence-unrolling.md#gradients)).

### Host computer

The host computer runs the waveform calculation, the data streaming of both cards and the processing of the receive data. The following points determine its specification:

| Aspect | Consideration | Reference value |
|---|---|---|
| PCIe | One slot per card, according to the card's PCIe interface | 2 free slots |
| CPU | Sequence unrolling and RX processing run on the host; RX processing is distributed over `num_processing_workers` processes | Multi-core workstation CPU |
| Memory | Each card uses a DMA buffer of up to 1 GiB; the unrolled sequence (8 bytes per sample, i.e. 160 MB/s at 20 MHz) and the raw data are held in memory | ≥ 64 GB, ECC recommended |
| Storage | Acquisition data are written to `<home>/nexus-console` | NVMe SSD |
| GPU | Not used by the console; optional for image reconstruction | Optional |

## Installation of the measurement cards

1. Install both cards in free PCIe slots of the host computer (power off).
2. Install the Spectrum Instrumentation driver for the operating system; drivers and manuals are available from the [Spectrum Instrumentation download area](https://spectrum-instrumentation.com/support/downloads.php) [[6]](../references.md#ref-6). The Python package loads the driver library `spcm_win64.dll` (Windows) or `libspcm_linux.so` (Linux).
3. Verify that both cards are detected, e.g. with the Spectrum Control Center, and note their device paths (`/dev/spcm0`, `/dev/spcm1`, ...).
4. Connect the cards as described in [Wiring](wiring.md).
5. Enter the device paths and the hardware parameters in the [device configuration](configuration.md).
6. Install the Python package as described in the [Quickstart](../getting-started/quickstart.md).

!!! warning "Amplifiers during start-up"
    The multi-purpose lines of the cards are pulled high while the cards are opened. Switch off the RF and gradient power amplifiers before connecting to the cards. The `nexus` service asks for confirmation before it opens the cards.
