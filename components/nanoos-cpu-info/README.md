# nanoos-cpu-info

Initial read-only hardware discovery component for the NanoOS CPU Engine.

## Features

- Reads CPU identification from `/proc/cpuinfo`.
- Reads available CPU frequency policies from Linux sysfs.
- Reports governor, driver, EPP and available preference strings when exposed.
- Supports human-readable output and `--json`.
- Uses only the Python standard library.

## Safety

This utility does not write sysfs, change CPU policies, alter kernel parameters, control voltage, or require root. Missing kernel interfaces are reported as unavailable rather than treated as errors.

## Run from source

```sh
python nanoos_cpu_info.py
python nanoos_cpu_info.py --json
```

This component is not yet packaged as a PKGBUILD. Package metadata will be added after source layout and install paths are reviewed.
