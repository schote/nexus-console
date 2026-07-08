# Acquisition Manager

The `service` module provides infrastructure for running the Nexus Console as a background service, accessible to multiple client processes via Python's `multiprocessing.managers` framework.

## AcquisitionControlManager

`AcquisitionControlManager` wraps `AcquisitionControl` in a `BaseManager` subclass, exposing its methods over an inter-process communication (IPC) channel. This allows experiment scripts running in separate processes or on separate machines to submit sequence jobs and retrieve acquisition data without direct hardware access.

The `start_manager.py` entry point starts this manager and registers it with the `nexus` CLI command.

::: console.service.acquisition_manager.AcquisitionControlManager