# Device Configuration

The `NexusConfiguration` Pydantic model is the validated, in-memory representation of the YAML device configuration file. It groups hardware parameters for the transmit card, receive card, and MRI system limits into three sub-models. The configuration is loaded via `load_nexus_config(path)` and injected into `AcquisitionControl`, `SequenceProvider`, `TxCard`, and `RxCard` during instantiation.

## Configuration hierarchy

```
NexusConfiguration
├── tx: TxConfiguration    (alias: TxConfiguration)
├── rx: RxConfiguration    (alias: RxConfiguration)
└── system: SystemLimits   (alias: SystemLimits)
```

Pydantic enforces type validation and raises descriptive errors if required fields are missing or of the wrong type. Unknown fields in the YAML file are silently ignored (`extra = "ignore"`), allowing the configuration file to carry additional user-defined metadata.

See [Measurement cards](../../setup/cards.md) for a full description of all fields and their physical significance.

---

::: console.interfaces.device_configuration
