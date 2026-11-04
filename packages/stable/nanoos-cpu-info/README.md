# nanoos-cpu-info 0.1.0-1

The first NanoRepo Stable-channel package recipe.

## Package details

- Command: `nanoos-cpu-info`
- Installed path: `/usr/bin/nanoos-cpu-info`
- Runtime dependency: `python`
- Architecture: `any`
- License: MIT
- Source: pinned to NanoRepo commit `a7e4f695e6d888cad75c3243ca827396f5382c7c`

## Safety and behavior

The utility reads CPU identification and available cpufreq policy information. It does not write sysfs, change CPU policies, alter kernel parameters, control voltage, or require root.

## Build and test

Build with Arch `makepkg --cleanbuild --syncdeps`. The PKGBUILD includes a Python bytecode compilation check. After building, install the package only in a disposable Arch/NanoOS virtual machine until the repository signing and publication process is configured.
