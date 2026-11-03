# Build and release process

## Current CI behavior

The current GitHub Actions workflow builds registered PKGBUILDs in a disposable `archlinux:base-devel` job container, running `makepkg --cleanbuild --syncdeps` as an unprivileged build user.

This is a disposable containerized build environment, **not yet a devtools clean chroot per package**. Before the repository grows beyond its first packages, the builder should move to a verified clean-chroot flow using Arch devtools (or an equivalent isolated builder). Do not describe the present container job as a clean chroot.

## Build requirements

- Build only reviewed PKGBUILDs under `packages/<channel>/<package>/PKGBUILD`.
- Keep source revisions versioned or pinned so a build can be reproduced.
- Validate PKGBUILD syntax and generated package metadata.
- Use a generic baseline for Stable and Testing.
- Use `-march=znver5` only for explicitly separated Zen 5 packages.
- Record source commit, toolchain, build profile, package version, architecture, and SHA-256 checksum.
- Run package-specific tests before publication.

## Release stages

1. Pull request validation: unit tests, source-registry validation, and PKGBUILD static checks.
2. Candidate build: build registered package recipes in the disposable Arch container.
3. Testing channel: sign package archives and repository metadata; publish only after R2 and signing secrets are configured.
4. Verification: install/upgrade/remove tests in disposable NanoOS/Arch-based VMs.
5. Stable promotion: promote reviewed artifacts without rebuilding them; verify checksums match.
6. Publication: upload package files, detached signatures, and repository databases over HTTPS.
7. Rollback: retain older package objects and document a safe database rollback procedure.

## Signing

The release process uses a dedicated NanoOS package-signing key. Only the public key and its fingerprint may be distributed to clients. The private signing key is supplied to the protected GitHub Actions publishing step through repository secrets and must never be committed, printed, or included in build artifacts.

The keyring package, fingerprint distribution, revocation plan, and recovery procedure must be completed before production release.

## Publishing

The workflow publishes only from the `main` branch and only when the R2 and GPG secrets are present. It publishes to separate channel paths and deliberately does not delete old package objects during sync.

The proposed public domain and client configuration are documented in `docs/R2-HOSTING.md` and `docs/PACMAN-CLIENT-CONFIG.md`. The endpoint is not live until the R2 bucket and custom domain are configured.

## Current implementation status

- Source event validation and CI: implemented.
- Package build workflow: implemented and passed its no-PKGBUILD path.
- PKGBUILD recipes: none yet.
- Signing key and R2 credentials: not configured.
- Binary Pacman repository: not yet published.
