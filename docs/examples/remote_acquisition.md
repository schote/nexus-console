# Remote acquisition

The acquisition can be run in a separate service process that connects to the cards once and remains active between experiments. Experiment scripts connect to this service as clients, either on the host computer or, with an appropriate address configuration, from another computer.

## Service

Start the service on the host computer with the device configuration of the system:

```bash
nexus -d path/to/device_config.yaml
```

The service asks for confirmation that the amplifiers are switched off before the cards are opened (see [Wiring](../system/wiring.md#safety)). The available options are documented in [`start_manager.main`][console.service.start_manager.main].

## Client

The client connects with [`AcquisitionControlManager`][console.service.acquisition_manager.AcquisitionControlManager] and accesses the remote `AcquisitionControl` instance as `mngr.acquisition`. Sequence and acquisition parameters are transferred to the service, and the `AcquisitionData` is returned to the client.

```python title="examples/acquisition_manager.py"
--8<-- "examples/acquisition_manager.py"
```
