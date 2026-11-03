# NanoRepo roadmap

## Phase 1 — Foundation
- [x] Create NanoRepo source repository
- [x] Define stable, testing, and Zen 5 channel policies
- [x] Document repository trust and release architecture
- [x] Add Zen 5 build-profile example
- [x] Add CPU Engine design specification
- [x] Add static repository validation and CI
- [ ] Audit existing NanoOS app and kernel source trees
- [ ] Add the first reviewed PKGBUILDs

## Phase 2 — Package set
- [ ] nanoos-release and base meta-package
- [ ] NanoOS GameMode package
- [ ] NanoOS Welcome package
- [ ] NanoOS Update package
- [ ] NanoOS Installer tools package
- [ ] nan package
- [ ] NanoOS Gaming kernel package and matching headers
- [ ] Hardware profiles and gaming presets

## Phase 3 — CPU Engine and Zen 5
- [ ] Read-only hardware and sysfs capability detection
- [ ] CPU profile policy and dry-run
- [ ] Reversible profile application and restore
- [ ] Telemetry and benchmark utilities
- [ ] Zen 5-specific package naming and build validation
- [ ] Zen 5 hardware testing and benchmark evidence

## Phase 4 — Repository operations
- [ ] Clean-chroot package build workers
- [ ] Testing-channel publication
- [ ] Package and database signing
- [ ] Keyring package and trust bootstrap
- [ ] HTTPS package hosting and pacman configuration
- [ ] Stable promotion and rollback procedure
- [ ] VM install/upgrade/remove tests

## Phase 5 — Release quality
- [ ] Reproducibility checks for selected packages
- [ ] Automated dependency and vulnerability review
- [ ] Release manifests and checksums
- [ ] Public package index and documentation
