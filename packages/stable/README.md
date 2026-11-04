# Stable package sources

Reviewed, generic NanoOS PKGBUILDs belong here.

## Current packages

- `nanoos-cpu-info` 0.1.0-1 — read-only CPU and cpufreq capability inspector; MIT licensed; source pinned to an immutable NanoRepo commit. Bare-metal Pacman install, run, ownership listing, and removal test passed.
- `nanoos-keyring` 20261104-1 — initial public repository keyring for the NanoOS Ed25519 signing key. Build and keyring-package tests are pending CI; it is not yet published or trusted by clients.

The Stable Pacman repository is not live. Package signatures, repository database signatures, initial trust bootstrap, and release hosting must be verified before enabling it for clients.
