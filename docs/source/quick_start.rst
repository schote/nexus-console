.. _quick-start:

Quick-Start Guide
=================

Follow these steps to quickly set up and test the Spectrum-Console package.
Before you start, make sure that the Spectrum-Instrumentation measurement cards are mounted properly and the driver is installed.
See Spectrum-Instrumentation `downloads <https://spectrum-instrumentation.com/support/downloads.php>`_ for further information on how to setup the measurement cards.

1. Clone the Spectrum Console GitHub Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Clone the `Spectrum-Console repository <https://github.com/schote/spectrum-console>`_ from GitHub using the following command:

.. code-block:: bash

   git clone https://github.com/schote/spectrum-console.git

Make sure, that you are in the directory where the code should be located.

2. Install uv
~~~~~~~~~~~~~
The project is managed with `uv <https://docs.astral.sh/uv/>`_, which creates the virtual environment and installs the required Python version (>= 3.13).
Follow the uv `installation guide <https://docs.astral.sh/uv/getting-started/installation/>`_, e.g.:

.. code-block:: bash

   curl -LsSf https://astral.sh/uv/install.sh | sh

3. Install the Repository Locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Navigate to the cloned repository directory and install the package with its locked dependencies:

.. code-block:: bash

   uv sync

This creates a virtual environment in ``.venv`` and installs the package in editable mode, together with the ``dev`` dependency group (includes ``test`` and ``lint``).
Additional dependency groups can be added, e.g. to build the documentation locally:

.. code-block:: bash

   uv sync --group docs

Commands are executed in the environment with ``uv run``, alternatively the environment can be activated with ``source .venv/bin/activate``.

4. Execute an Example
~~~~~~~~~~~~~~~~~~~~~
Navigate to the ``/examples`` directory and run an example script:

.. code-block:: bash

   cd examples
   uv run se_spectrum.py

Congratulations! You have successfully set up and executed an example with the Spectrum Console. For more detailed information, refer to the full documentation.


5. Implementing Your Own Experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is recommended to keep the package as it is and use a separate repository to implement custom experiments.
Experiments are user and system specific, which is why they should be managed per system and/or user.
Some example experiments are provided in the ``/examples`` folder and can be used as a starting point to build custom experiments.
When executing custom experiments, make sure that you are working within the same environment and that the package was installed successfully in that environment.
