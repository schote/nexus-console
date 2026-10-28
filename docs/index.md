---
hide:
  - navigation
  - toc
---

# Nexus Console

--8<-- "README.md:summary"

!!! note "Who this documentation is for"

    This documentation is aimed at developers and researchers who want to build on the console software itself, e.g. to develop new sequences, acquisition workflows or hardware integrations. Using the nexus-console repository alone requires a custom set of experiments or a runner script that handles all tasks around the acquisition, such as loading a sequence, setting the acquisition parameter and saving the data.

    If you only want to execute sequences and experiments, use the [Nexus CLI](https://github.com/schote/nexus-cli) instead. It runs Pulseq `.seq` files and protocols, exports the data as ISMRMRD, manages the acquisition parameter and provides basic calibrations, without writing Python.

<div class="grid cards cards-4" markdown>

-   :material-rocket-launch:{ .lg .middle } **Setup**

    ---

    Set up the hardware, install the software and run a first acquisition.

    [:octicons-arrow-right-24: Hardware setup](setup/hardware-setup.md)

-   :material-developer-board:{ .lg .middle } **System guide**

    ---

    Hardware, wiring, configuration, and the path from sequence to data.

    [:octicons-arrow-right-24: System overview](system/overview.md)

-   :material-flask-outline:{ .lg .middle } **Examples**

    ---

    Spectroscopy, relaxometry, 3D imaging and remote acquisition.

    [:octicons-arrow-right-24: Examples](examples/index.md)

-   :material-code-braces:{ .lg .middle } **API reference**

    ---

    Reference documentation generated from the source code.

    [:octicons-arrow-right-24: API reference](reference/index.md)

</div>

--8<-- "README.md:citation"

--8<-- "README.md:acknowledgments"
