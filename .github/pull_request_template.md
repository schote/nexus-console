## Description
<!-- Briefly describe what this PR changes and why. -->


## Related issues
<!-- Link related issues. Use "Closes #123" to close an issue automatically when this PR is merged,
     or "Relates to #123" for issues that should stay open. -->
Closes #

## Hardware setup
<!-- Run the following command from the repository root on the system this PR was tested with,
     and paste its complete output between the ``` lines below:

         python tests/hardware/system_info.py

     It prints OS, Python, nexus-console version and git revision, spcm driver versions and the Spectrum card models.
     NOTE: Stop the console service first, cards that are in use cannot be read. -->

```

```

## Migration
<!-- What does someone have to do after pulling main once this PR is merged?
     Write "None" if no action is needed and delete the subsections below.
     Otherwise keep only the relevant subsections. -->

**Environment / dependencies**
<!-- e.g. new or changed dependencies (re-run `pip install -e .`), new Python version, new driver/firmware version -->

**Device configuration (YAML)**
<!-- List added, renamed or removed keys and their new defaults.
     Note: unknown keys are silently ignored, so renamed keys will NOT raise an error. -->

**Hardware / cabling**
<!-- e.g. re-cabling, changed port assignment (analog channels, X0–X3 digital lines),
     termination (50 Ω), amplifier gain or other settings that must be adjusted -->

**API / user scripts**
<!-- Breaking changes to classes, function signatures or parameters that require existing scripts or sequences to be adapted -->

**Data output**
<!-- Changes to the stored acquisition data or MRD/ISMRMRD output that affect downstream reconstruction -->

## Checklist
- [ ] Loopback hardware test passed (run `python tests/hardware/loopback.py -d <device_config.yaml>`)
- [ ] Tests added or updated (if necessary)
- [ ] Documentation updated (user guide, API docs, port tables, etc.)
- [ ] Examples updated (if necessary)