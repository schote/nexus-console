# Abstract Device (SpectrumDevice)

`SpectrumDevice` is the abstract base class for all Spectrum Instrumentation card wrappers in Nexus Console. It provides a common interface for connecting, disconnecting, error handling, and status reporting, and defines the abstract methods that `TxCard` and `RxCard` must implement.

## Connection lifecycle

```
SpectrumDevice.__init__(path)
    │
    ├── connect()       ← opens spcm_hOpen, reads card type, calls setup_card()
    │
    ├── [operation]     ← start_operation() / stop_operation()
    │
    └── disconnect()    ← M2CMD_CARD_STOP + M2CMD_CARD_RESET + spcm_vClose
```

The `connect` method opens the PCIe device at the given path (e.g., `/dev/spcm0`), reads the card type identifier, and delegates hardware-specific setup to the abstract `setup_card` method implemented by each subclass.

## Error handling

`handle_error(error_code)` checks the return value of every `spcm_dwSetParam_*` call. If the error code is not `ERR_OK`, it reads the error description from the card, logs it at CRITICAL level, stops the card, and raises a `RuntimeError`. A timeout error (`ERR_TIMEOUT`) is silently ignored, as it occurs in normal operation during polling loops.

---

::: console.spcm_control.abstract_device
