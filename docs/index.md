---
hide:
  - navigation
  - toc
---

# Nexus Console

--8<-- "README.md:summary"

!!! info "Nexus Console or Nexus CLI?"

    This documentation is aimed at developers and researchers who want to build on the console software itself, e.g. to develop new sequences, acquisition workflows or hardware integrations. Using the nexus-console repository alone requires a custom set of experiments or a runner script that handles all tasks around the acquisition, such as loading a sequence, setting the acquisition parameter and saving the data.

    If you only want to execute sequences and experiments, use the [Nexus CLI](https://github.com/schote/nexus-cli) instead. It runs Pulseq `.seq` files and protocols, exports the data as ISMRMRD, manages the acquisition parameter and provides basic calibrations, without writing Python.

<div class="grid cards cards-3" markdown>

-   :material-rocket-launch:{ .lg .middle } **Setup**

    ---

    Connect the measurement cards, install the software and the acquisition service, and run a first acquisition.

    [:octicons-arrow-right-24: Hardware setup](setup/hardware-setup.md)

-   :material-developer-board:{ .lg .middle } **System guide**

    ---

    How the console works: hardware, configuration, sequence calculation, acquisition and postprocessing.

    [:octicons-arrow-right-24: System overview](system/overview.md)

-   :material-flask-outline:{ .lg .middle } **Examples**

    ---

    Example experiments, from spin-echo spectroscopy and T2 relaxometry to 3D imaging and remote acquisition.

    [:octicons-arrow-right-24: Examples](examples/index.md)

-   :material-code-braces:{ .lg .middle } **API reference**

    ---

    Classes and functions of the console package, generated from the docstrings of the source code.

    [:octicons-arrow-right-24: API reference](reference/index.md)

-   :material-console:{ .lg .middle } **Nexus CLI**

    ---

    Command-line client to run Pulseq sequences, edit the acquisition parameter and calibrate the system.

    [:octicons-arrow-right-24: Nexus CLI](https://github.com/schote/nexus-cli)

-   :material-chat-question-outline:{ .lg .middle } **Issues and discussions**

    ---

    Facing a problem? Check the existing issues and discussions, or open a new one if it is not covered.

    [:octicons-arrow-right-24: Issues](https://github.com/schote/nexus-console/issues) · [Discussions](https://github.com/schote/nexus-console/discussions)

</div>

--8<-- "README.md:citation"

--8<-- "README.md:acknowledgments"
