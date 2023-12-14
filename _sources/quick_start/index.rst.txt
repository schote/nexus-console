.. _quick-start:

Quick-Start Guide
=================

Follow these steps to quickly set up and run the Spectrum-Console package.
Before you start, make sure that the Spectrum-Instrumentation measurement cards are mounted properly and the driver is installed.
See Spectrum-Instrumentation `downloads <https://spectrum-instrumentation.com/support/downloads.php>`_ for further information on how to setup the measurement cards.
A reference system setup can be found here :ref:`system-setup`

1. Clone the Spectrum Console GitHub Repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Clone the `Spectrum-Console repository <https://github.com/schote/spectrum-console>`_ from GitHub using the following command:

.. code-block:: bash

   git clone https://github.com/schote/spectrum-console.git

Make sure, that you are in the directory where the code should be located.

2. Set Up a Virtual Python Environment (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This step is optional, but you might want to create a virtual environment to install the package.
Navigate to the cloned repository directory and create a virtual environment, e.g. using Conda:

.. code-block:: bash

   conda create --name console-env python=3.10
   conda activate console-env

3. Install the Repository Locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Install the cloned Spectrum-Console package locally using pip with the editable option, in case you want to modify the code.
Make sure, that the environment was activated successfully.

.. code-block:: bash

   pip install -e .

4. Execute an Example
~~~~~~~~~~~~~~~~~~~~~
Navigate to the "examples" directory and run an example script:

.. code-block:: bash

   cd examples
   python se_spectrum.py

Congratulations! You have successfully set up and executed an example with the Spectrum Console. For more detailed information, refer to the full documentation.