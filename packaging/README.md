# Package source conventions

Each package directory contains a standard Arch PKGBUILD and any required source/patch files.

## Channel placement

- `packages/stable/<pkgname>/`
- `packages/testing/<pkgname>/`
- `packages/znver5/<pkgname>/`

A package should appear in one channel unless an intentional promotion or parallel package variant is documented.

## PKGBUILD requirements

- Follow Arch packaging standards.
- Use explicit source checksums or valid upstream signature verification.
- Declare runtime and build dependencies accurately.
- Include architecture and licensing metadata.
- Do not embed secrets or private signing keys.
- Do not use `-march=native` for distributed binaries.
- Avoid changing global makepkg configuration from package install scripts.
- Add test instructions for packaged NanoOS components.

Packages will be added only after existing NanoOS source code, actual dependencies, installation paths, and licensing have been inspected.
