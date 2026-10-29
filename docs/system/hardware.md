# Console hardware

The Nexus console utilizes PCIe measurement cards from Spectrum Instrumentation integrated in a high performance workstation. This page summarizes the requirements of the console software framework with respect to the hardware and the considerations for choosing the components. The installation is described in [Hardware setup](../setup/hardware-setup.md).

!!! note "Development setup"
    The components and the port assignment on this page describe the setup that was used for the development of the console [[1]](../references.md#ref-1). Other workstations and other cards of the same families might work as well, but have not been tested.

## Workstation

The workstation hosts both measurement cards. With the current state of the code, the complete sequence is calculated into host memory before execution. During the acquisition, the workstation streams these waveforms to the AWG, reads the gated receive data from the digitizer and processes them in parallel. The considerations below assume a sampling rate of 20 MHz as in the development setup.

!!! info "Planned improvements"
    Several improvements are planned and will be implemented in the future. This includes for instance calculating the sequence at runtime, resulting in memory requirement will then no longer scale with the sequence duration. In turn, sequence calculation, streaming and receive processing will run in parallel, which requires more CPU cores and a sequence calculation that is faster than real time. Also, the measurement cards are able to transfer data directly to a GPU using [SCAPP](https://spectrum-instrumentation.com/products/drivers_examples/scapp_cuda_interface.php). Future versions of the Nexus console will benefit from an on board GPU.

| Component | Development setup | Reasoning |
|---|---|---|
| PCIe | Supermicro X12SPL-F, 7 slots | One slot per card with 4 lanes (`-x4`). The required transfer rates of 160 MB/s for the AWG and 40 MB/s per enabled receive channel (while the gate is open) are well below the card interface rate of about 700 MB/s. Further slots are available for a GPU, NVMe storage or additional cards. |
| AWG | Spectrum M2p.6546-x4 with IO expansion module | Four 16-bit channels on one card, so RF and the three gradients can be replayed sample-synchronously from a single buffer. The output range of ±6 V into 50 Ω (±12 V into high impedance) drives the RFPA and the GPA inputs directly. 40 MS/s enable sufficient oversampling at ~2 MHz which is the Larmor frequency of the development setup. The 15th bit of channels 1–3 can be used for synchronous digital outputs X1–X3, so ADC gate, phase reference and RF unblanking are generated with the waveforms and no separate timing hardware is needed. |
| Digitizer | Spectrum M2p.5933-x4 | Eight 16-bit channels at 40 MS/s for the MR signal and for additional sensors, e.g. EMI sensing coils. The MR signal is sampled directly and demodulated digitally on the host, so no analog receive chain beyond the preamplifier is needed. The synchronously sampled digital input X2 provides a phase reference to prevent clock domain crossing due to trigger jitter. |
| RAM | 256 GB | The unrolled sequence holds 4 channels × 2 bytes (int16) per sampling clock, i.e. 160 MB/s or **9.6 GB per minute** of sequence. Averages replay the same buffer and need no additional memory. Together with about 16 GB for the operating system, the Python processes and the two 1 GiB DMA buffers, 256 GB allow sequences of roughly 25 minutes. The processed receive data are small in comparison (16 bytes per complex sample and channel, e.g. 34 MB for 128 × 128 × 128 samples), unless the raw data are kept with `run(store_unprocessed=True)`. |
| CPU | Intel Xeon Gold 6312U, 24 cores | The acquisition process runs the TX streaming and RX readout threads, which must keep up with the cards, while `num_processing_workers` processes demodulate and decimate the gates in parallel. At least 2 + `num_processing_workers` cores should therefore be available, plus one for the acquisition service. Currently, the sequence calculation runs in a single process, so the single-core performance determines the duration of `set_sequence`. Note that by future parallelization of sequence calculation and/or processing, additional cores might be required.  |
| Storage | NVMe SSD | The acquisition data is saved to disk after the acquisition, so the storage speed does not affect the acquisition itself. |
| GPU | Optional | Not required by the Nexus console by now. Can be useful for on-board AI-based processing. Future updates of the console might investigate streaming the acquired data to GPU for faster processing. |
| Operating system | AlmaLinux 9.3, Windows 10 | Both are supported by the Spectrum driver (development setup: kernel driver M2p 2.17 build 17916, library 6.05 build 21120). |

!!! note "Card requirements of the software"
    The current Nexus console implementation supports exactly one transmit and one receive card. The card families M2p.65xx (AWG) and M2p.59xx (digitizer) are checked on connection and need to match. The cards are synchronized by a cable connection as described [here](../setup/hardware-setup.md) and share the clock provided by the AWG module. Therefore, the cards must support the same sampling rate. Synchronization via a Star-Hub might be added in the future.


## Inputs and outputs

The tables list every port of the two cards as it is used in the proposed development setup. Analog channels, clock input and trigger input are SMB connectors and the multi-purpose lines X0–X3 are MMCX connectors. How to connect the ports is described in the [Connection plan](../setup/hardware-setup.md#connection-plan).

### M2p.6546-x4 AWG

| Port | Connector | Direction | Signal | Connected to |
|---|---|---|---|---|
| 0 | SMB | Analog out | RF waveform | RFPA input |
| 1 | SMB | Analog out | Gradient, physical channel 1 (bits 0–14 of channel 1) | GPA input 1 |
| 2 | SMB | Analog out | Gradient, physical channel 2 (bits 0–14 of channel 2) | GPA input 2 |
| 3 | SMB | Analog out | Gradient, physical channel 3 (bits 0–14 of channel 3) | GPA input 3 |
| Clk In | SMB | In | External sampling clock, 50 Ω termination, 1.5 V threshold | Digitizer X0 |
| Trig In | SMB | – | Not used; the card is started by a software trigger | – |
| X0 | MMCX | – | Not used | – |
| X1 | MMCX | Digital out | ADC gate, high during each ADC event (bit 15 of channel 1) | Digitizer X1 |
| X2 | MMCX | Digital out | Phase reference, square wave at a fixed frequency at the start of each gate (bit 15 of channel 2) | Digitizer X2 |
| X3 | MMCX | Digital out | RF unblanking to enable the RFPA during RF transmission (bit 15 of channel 3) | RFPA unblanking input |

### M2p.5933-x4 Digitizer

| Port | Connector | Direction | Signal | Connected to |
|---|---|---|---|---|
| 0 | SMB | Analog in | MR signal; bit 15 is replaced by the sampled X2 input | Preamplifier output |
| 1–7 | SMB | Analog in | Optional additional receive channels, e.g. for EMI sensing coils; enabled via `channel_enable` | Optional |
| Clk In | SMB | – | Not used; the card runs on its internal PLL | – |
| Trig In | SMB | – | Not used | – |
| X0 | MMCX | Clock out | Sampling clock | AWG clock input |
| X1 | MMCX | Trigger in (Ext1) | ADC gate; the card records while the gate is high | AWG X1 |
| X2 | MMCX | Digital in | Phase reference, sampled into bit 15 of channel 0 | AWG X2 |
| X3 | MMCX | – | Not used | – |

## Safety

The multi-purpose lines (X0...X3) are pulled high when the cards are opened upon establishing the card connection ([issue #54](https://github.com/schote/nexus-console/issues/54)). As X3 drives the RFPA unblanking input, this can affect the amplifier, e.g. provided that the component includes safety mechanisms that are triggered, for example, if the gate signal is too long.
