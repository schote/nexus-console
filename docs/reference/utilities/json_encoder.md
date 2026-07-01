# JSON Encoder

`JSONEncoder` extends Python's `json.JSONEncoder` to handle types that are not natively JSON-serialisable, including NumPy scalars, NumPy arrays, and Python `dataclass` instances. It is used when writing the `meta.json` file in `AcquisitionData.save()`.

---

::: console.utilities.json_encoder
