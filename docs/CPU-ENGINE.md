# NanoOS CPU Engine — design specification

## Goal

Provide clear, reversible CPU performance profiles using interfaces exposed by the running Linux kernel and processor firmware.

## Initial architecture

- Hardware discovery: identify CPU vendor/model, core topology, driver, governor, and supported energy-performance preferences.
- Capability detection: inspect the actual sysfs controls available on the current machine; do not assume all AMD processors expose the same interface.
- Profile policy: map NanoOS modes to available kernel-supported preferences.
- Apply layer: make a change only after checking permissions, supported values, and current state.
- Restore layer: remember the previous values and provide an explicit restore operation.
- Telemetry: report current policy and observable CPU status without claiming that requested frequency equals guaranteed frequency.

## Planned profiles

| NanoOS profile | Intent |
|---|---|
| Ultra Power Saving | Bias toward efficiency where supported |
| Balanced | General-purpose behavior |
| Performance | Bias toward responsiveness |
| Gaming | Performance-oriented policy for interactive workloads |
| Creator | Workload-oriented policy for long-running compute tasks |

The exact EPP strings and values must be discovered from each system's exposed sysfs attributes. They must not be hard-coded as universally supported.

## Safety and correctness requirements

- No voltage control, overclocking, firmware writes, or unsupported MSR manipulation.
- No automatic permanent kernel-command-line changes.
- Do not change CPU affinity or disable cores by default.
- Preserve the previous setting and provide a restore operation.
- Refuse unsupported or malformed sysfs values.
- Require elevated privileges only for the operation that changes a setting.
- Explain that firmware, cooling, power limits, and workload affect actual performance.
- Include read-only detection and dry-run modes before adding write operations.

## Validation

Test on a disposable VM for application behavior, then test hardware-specific behavior on compatible Zen 5 hardware with before/after measurements and thermal monitoring. Never present a profile as a benchmark guarantee.
