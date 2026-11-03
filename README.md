# NanoOS Repo Extreme Ultra Pro

The official package-source and repository-infrastructure project for **NanoOS**.

> **Current status:** Foundation branch. Repository channels, package recipes, signing keys, and public package endpoints are not yet production-ready. Do not add this repository to a daily-use system yet.

## Repository goals

- Maintain a compatible generic `x86_64` package baseline.
- Separate stable, testing, and opt-in Zen 5 optimized package tracks.
- Package NanoOS system components using standard Arch `PKGBUILD` recipes.
- Build packages in clean, controlled environments.
- Validate package metadata and build scripts before release.
- Sign packages and repository databases before publication.
- Keep build recipes, release artifacts, and private signing material separate.

## Planned package channels

| Channel | Intended audience | Compatibility |
|---|---|---|
| `nanoos` | Normal NanoOS installations | Generic x86_64 baseline |
| `nanoos-testing` | Preview and candidate builds | Generic x86_64 baseline |
| `nanoos-znver5` | Explicit opt-in optimized builds | AMD Zen 5 only |

The Zen 5 channel is intentionally separate. A package built with `-march=znver5` may contain instructions unavailable on older CPUs. Pacman does not select packages by CPU capability automatically; users must opt in deliberately and the repository must document this compatibility boundary.

## Planned components

- NanoOS release metadata and meta-packages
- NanoOS GameMode, Welcome, Update, Installer tools, and `nan`
- NanoOS Gaming kernel packaging and related presets
- CPU profile engine using supported Linux CPU-frequency interfaces
- Hardware detection, telemetry, and benchmark utilities
- Build validation, clean-chroot packaging, signing, and release automation

Package names and recipes will be added only after their real source trees, dependencies, install paths, and licensing are audited.

## Layout

```text
.github/workflows/       CI validation
channels/                Channel policies and publication layout
docs/                    Architecture, security, build, and tuning docs
packaging/               PKGBUILD conventions and build profiles
packages/                Channel-specific package sources
tools/                   Repository validation and maintenance tools
```

## Development status

See [docs/REPOSITORY-ARCHITECTURE.md](docs/REPOSITORY-ARCHITECTURE.md), [docs/BUILD-AND-RELEASE.md](docs/BUILD-AND-RELEASE.md), and [docs/ROADMAP.md](docs/ROADMAP.md).

## Important

This Git repository stores source recipes and release infrastructure. The actual Pacman package repositories will be generated from validated package artifacts and published to a separately configured HTTPS endpoint. No endpoint or signing key is assumed in this foundation.
