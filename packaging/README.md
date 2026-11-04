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
- Pin external source URLs to immutable commit identifiers or release archives.
- Declare runtime and build dependencies accurately.
- Include architecture and licensing metadata, and install the license under `/usr/share/licenses/<pkgname>/`.
- Do not embed secrets or private signing keys.
- Do not use `-march=native` for distributed binaries.
- Avoid changing global makepkg configuration from package install scripts.
- Add test instructions for packaged NanoOS components.

Packages are added only after source provenance, actual dependencies, installation paths, and licensing have been inspected. Pull request CI must build each package in the disposable Arch container before the recipe is merged.
