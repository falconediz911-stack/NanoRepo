# Build and release process

## Build requirements

- Build each PKGBUILD in a clean Arch chroot.
- Pin or record the base image and toolchain versions.
- Validate PKGBUILD shell syntax and generated `.SRCINFO`.
- Check dependencies and package metadata.
- Run package-specific tests after build.
- Record source commit, package version, architecture, compiler profile, and SHA-256 checksum.

## Release stages

1. Pull request validation: static repository checks and PKGBUILD syntax checks.
2. Build candidate: clean-chroot build from a reviewed commit.
3. Testing channel: signed package and signed repository metadata.
4. Verification: install/upgrade/remove tests in disposable Arch-based VMs.
5. Stable promotion: promote reviewed artifacts without rebuilding them; verify checksums match.
6. Publication: upload package files, detached signatures, and repository databases over HTTPS.

## Signing

The release process will use a dedicated NanoOS package-signing key. Only the public key may be stored in this repository. Private signing material must remain in protected release infrastructure and must never be committed, printed, or included in build logs.

The repository keyring package will be created only after the key identity, fingerprint distribution, revocation plan, and recovery process are defined.

## Current implementation status

This foundation contains documentation and static validation. It does not yet build or publish binary packages, create signing keys, or configure a hosting endpoint.
