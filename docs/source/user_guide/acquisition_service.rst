.. _acquisition-service:

Acquisition Service
===================

The measurement cards are opened once by a long-running service.
All experiments connect to this service instead of opening the cards themselves.
This way the cards keep their state between experiments and the console can be used
interactively, for instance from a notebook or from an SSH session.

Starting the Service
--------------------

The service is started with the ``nexus`` entry point, which requires a device configuration file:

.. code-block:: bash

   nexus -d /path/to/device_config.yaml

The available arguments are:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Argument
     - Description
   * - ``-d``, ``--device_config``
     - Path to the device configuration yaml file (required).
   * - ``-f``, ``--sessions_folder``
     - Directory for logs, states and acquisition data of a session.
   * - ``--authkey-file``
     - Path to a file containing the authentication key. If omitted, a random key is
       generated for this service run.
   * - ``-n``, ``--no-verify``
     - Start without asking for confirmation that the amplifiers are turned off.

.. note::
   The arguments ``--address`` and ``--port`` no longer exist. The service is not reachable
   over the network: it listens on a unix domain socket in the runtime directory, and the
   authentication key is generated instead of being passed on the command line, where it
   would be visible to every user of the workstation via ``ps``.

Runtime Directory
-----------------

Service and clients exchange the connection details through a runtime directory,
by default ``<tempdir>/nexus``:

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - File
     - Description
   * - ``nexus.sock``
     - Unix domain socket of the acquisition service.
   * - ``authkey``
     - Authentication key of the running service, readable by every account.

Both files are removed when the service shuts down.
The directory is created with mode ``1777``, the same permissions ``/tmp`` itself uses:
every account on the workstation may use the console, so every account must be able to read
the key and open the socket. The sticky bit restricts deleting and renaming a file to the
account which owns it, so no session can remove the socket, the key or the lock of another.
There is no group to create and nothing to configure. The environment variable
``NEXUS_RUNTIME_DIR`` overrides the location and exists so that tests can isolate themselves
from a running service.

.. note::
   The authentication key is therefore readable by every account on the workstation and is
   not a secret. It replaces the key which used to be hardcoded in this repository and
   passed on the command line, and being generated per service run it keeps a client of a
   previous run from talking to the current service. It is not a barrier against a user of
   the workstation who is determined to interfere: the measurement cards themselves are
   world-accessible character devices, and a client which holds the key can make the
   service execute code on its behalf. Run the service under an ordinary operator account,
   never as root.

If the service was killed without being able to clean up, the socket file survives.
The next service start detects that nothing is listening behind it and removes it.
A second service instance started while the first one is still running aborts with an error
instead of interfering with the running acquisition.

Connecting to the Service
-------------------------

Clients resolve socket and authentication key from the runtime directory,
so the manager is constructed without arguments:

.. code-block:: python

   from console.service.acquisition_manager import AcquisitionControlManager

   with AcquisitionControlManager() as manager:
       manager.acquisition.set_sequence(sequence=seq, parameter=parameter)
       acquisition_data = manager.acquisition.run()

If the service is not running, the construction of the manager raises a
:class:`~console.utilities.exceptions.NexusNotRunningError`.

Errors
------

All errors raised deliberately by the nexus console derive from
:class:`~console.utilities.exceptions.NexusError`, so a single ``except`` clause catches them:

.. code-block:: python

   from console import NexusError

   try:
       with AcquisitionControlManager() as manager:
           ...
   except NexusError as error:
       print(error)
