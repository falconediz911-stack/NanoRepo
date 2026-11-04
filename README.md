# NanoOS Repo Extreme Ultra Pro

The official package-source and repository-infrastructure project for **NanoOS**.

> **Current status:** The first Stable-channel package recipe, `nanoos-cpu-info` 0.1.0-1, is merged into `main`. NanoRepo validation passed, and the pull-request Arch build produced a package archive. The extracted command was smoke-tested on a development Arch system. A Pacman-managed install/upgrade/removal test in a disposable VM is still pending. No production Pacman endpoint, signing key, or client-ready repository is active. Do not add the proposed repository URL to a daily-use system yet.

## Update architecture

NanoOS updates are split into two separate paths:

1. **Apps and system tools → Pacman.** A change in a registered source repository triggers NanoRepo. NanoRepo validates the source event, builds the matching Arch package from its PKGBUILD in a disposable Arch container, signs the package and channel database, and publishes to the configured package host. Clients then use `pacman -Syu`.
2. **ISO releases → NanoOS Update metadata.** Publishing an ISO release sends a separate event to the NanoOS website, which updates `public/releases/iso-latest.json`. An ISO is not a Pacman package. The NanoOS Update client still needs to consume this separate feed.

See [docs/SOURCE-CONNECTIONS.md](docs/SOURCE-CONNECTIONS.md).

## Pacman channels

| Pacman repository | Audience | Compatibility |
|---|---|---|
| `nanoos` | Normal NanoOS installations | Generic x86_64 baseline |
| `nanoos-testing` | Preview and candidate builds | Generic x86_64 baseline |
| `nanoos-znver5` | Explicit opt-in optimized packages | AMD Zen 5 only |

The Zen 5 channel is separate because packages built with `-march=znver5` may contain instructions unavailable on older CPUs. Pacman does not choose packages based on CPU capability automatically.

## Current components

- Read-only CPU capability inspector source: `components/nanoos-cpu-info/`
- First Stable-channel PKGBUILD: `packages/stable/nanoos-cpu-info/PKGBUILD`
- CPU-info fixture coverage for AMD, Intel, and ARM-style `/proc/cpuinfo` data
- CPU Engine design and EPP-based profile plan
- Stable, Testing, and Zen 5 channel policies
- Source-repository allowlist and dispatch validator
- Arch-container package-build workflow with pull-request artifact builds
- Conditional signed publishing workflow for Cloudflare R2
- Separate ISO release metadata workflow integrations

The CPU-info package is Python-based and marked `arch=('any')`; its runtime reads the machine it is running on rather than embedding Falcon's CPU model. The ARM/Intel test fixtures are synthetic compatibility tests, not physical-hardware certification.

A component is not ready for end-user installation until its PKGBUILD, pinned source, dependencies, install paths, license metadata, tests, signatures, and published repository database have been verified.

## Hosting and activation

GitHub stores the source code, PKGBUILDs, workflows, and release history. The binary Pacman repository is designed for Cloudflare R2 behind a public HTTPS custom domain.

The proposed client URL is documented in [docs/PACMAN-CLIENT-CONFIG.md](docs/PACMAN-CLIENT-CONFIG.md), but it is **not live yet**. Publishing remains disabled until the R2 and signing secrets are configured. A NanoOS keyring package and trust bootstrap are also still required. See [docs/R2-HOSTING.md](docs/R2-HOSTING.md).

## Layout

```text
.github/workflows/       CI, package build/publish, source event receivers
channels/                Stable, Testing, and Zen 5 channel policies
components/              NanoOS source components
config/                  Registered source repository allowlist
docs/                    Architecture, security, hosting, and integration docs
packages/                Channel-specific PKGBUILD sources
packaging/               PKGBUILD conventions and compiler profiles
tests/                   Unit tests
tools/                   Repository and source-event validation
```

## Current limitations

- The first package has a successful CI archive build and extracted-command smoke test; Pacman install/upgrade/removal validation in a disposable VM remains pending.
- Cloudflare R2 bucket, public domain, and GitHub Actions secrets still need to be configured.
- A dedicated signing key, public keyring bootstrap package, and documented fingerprint/revocation procedure are not yet available.
- External app repositories must be registered in `config/source-registry.json` and use the documented dispatch template; no separate GameMode, Welcome, Update, Installer, or kernel source repositories are currently registered.
- The ISO release hooks are merged into their repositories but have not yet been exercised by a published ISO release.
- NanoOS Update must be updated to read `iso-latest.json`.

See [docs/ACTIVATE-CONNECTIONS.md](docs/ACTIVATE-CONNECTIONS.md) for the GitHub Actions secrets, R2 setup, and activation checklist. See [docs/ROADMAP.md](docs/ROADMAP.md) for the remaining work.
